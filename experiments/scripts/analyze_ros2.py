#!/usr/bin/env python3
"""Anonymize actual ROS 2 traces without subtracting the two PC clocks."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np

from signal_processing import spectra

ROOT = Path(__file__).resolve().parents[1]


def percentile(values, q=99):
    return float(np.percentile(values, q)) if len(values) else None


def maximum_gap(times_ns, seconds):
    """Gaps in the role's own observation window, including its two edges."""
    end = int(seconds*1e9)
    times = np.unique(np.asarray(times_ns, dtype=np.int64))
    times = times[(times >= 0) & (times <= end)]
    return float(np.diff(np.r_[0, times, end]).max()/1e6)


def longest_true_run(values):
    best = current = 0
    for value in values:
        current = current+1 if value else 0
        best = max(best, current)
    return best


def events(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def measurement_status(status):
    # DDS addresses and absolute clock origins stay in the private evidence.
    exclude = {'origin_ns', 'arm_ns', 'monotonic_ns', 'dds_configuration', 'graph_publisher_qos'}
    public = {key: value for key, value in status.items() if key not in exclude}
    public['graph_publisher_qos'] = {name.rsplit('/', 1)[-1]: value
                                   for name, value in status['graph_publisher_qos'].items()}
    local = '192.168.8.1' if status['role'] in ('control', 'sink') else '192.168.8.20'
    peer = '192.168.8.20' if status['role'] in ('control', 'sink') else '192.168.8.1'
    public['dds_experimental_interface_only'] = (
        f'<NetworkInterface address="{local}"/>' in status['dds_configuration']
        and f'<Peer address="{peer}"/>' in status['dds_configuration']
        and '<AllowMulticast>false</AllowMulticast>' in status['dds_configuration']
        and status['dds_configuration'].count('<NetworkInterface ') == 1)
    public['role_lifetime_seconds'] = (status['monotonic_ns']-status['origin_ns'])/1e9
    return public


def summarize_control(trace, status, seconds):
    planned = int(round(seconds*100))
    arm = status['arm_ns']
    assert arm is not None
    sent = {event['seq']: event for event in trace if event['kind'] == 'command_sent'}
    assert len(sent) == sum(event['kind'] == 'command_sent' for event in trace)
    responses = [event for event in trace if event['kind'] == 'response_received']
    first = {}
    for event in responses:
        assert event['seq'] in sent
        assert event['command_sent_ns'] == sent[event['seq']]['sent_ns']
        first.setdefault(event['seq'], event)
    arrays = {key: np.full(planned, -1, dtype=np.int64) for key in
              ('planned_ns', 'sent_ns', 'publish_start_ns', 'publish_end_ns', 'received_ns', 'echo_pre_publish_ns')}
    arrays['planned_ns'] = np.arange(planned, dtype=np.int64)*10_000_000
    for seq, event in sent.items():
        assert 0 <= seq < planned
        assert event['planned_ns']-arm == arrays['planned_ns'][seq]
        for key in ('sent_ns', 'publish_start_ns', 'publish_end_ns'):
            arrays[key][seq] = event[key]-arm
    for seq, event in first.items():
        arrays['received_ns'][seq] = event['received_ns']-arm
        arrays['echo_pre_publish_ns'][seq] = event['echo_pre_publish_ns']
    published = arrays['sent_ns'] >= 0
    received = arrays['received_ns'] >= 0
    assert np.all(received <= published)
    rtt = (arrays['received_ns'][received]-arrays['sent_ns'][received])/1e6
    publication = (arrays['publish_end_ns'][published]-arrays['publish_start_ns'][published])/1e6
    lateness = (arrays['sent_ns'][published]-arrays['planned_ns'][published])/1e6
    deadline = ~received | (arrays['received_ns']-arrays['sent_ns'] > 20_000_000)
    scheduled_deadline = ~received | (arrays['received_ns']-arrays['planned_ns'] > 20_000_000)
    return arrays, dict(planned=planned, published=int(published.sum()),
        unsent_planned=int((~published).sum()), responses=len(responses),
        unique_responses=int(received.sum()), duplicate_responses=len(responses)-int(received.sum()),
        lost_published=int((published & ~received).sum()),
        rtt_p99_ms=percentile(rtt), publication_p99_ms=percentile(publication),
        send_lateness_p99_ms=percentile(lateness),
        echo_pre_publish_p99_ms=percentile(arrays['echo_pre_publish_ns'][received]/1e6),
        published_deadline20_pct=float(deadline[published].mean()*100) if published.any() else None,
        planned_deadline20_pct=float(scheduled_deadline.mean()*100),
        longest_planned_deadline20_run=longest_true_run(scheduled_deadline),
        maximum_response_gap_ms=maximum_gap(arrays['received_ns'][received], seconds))


def summarize_sensors(source, sink, statuses, seconds):
    result = {}; arrays = {}
    for topic, payload in [('image', 691200), ('cloud', 65536)]:
        published = [event for event in source if event['kind'] == 'sensor_published' and event['topic'] == topic]
        received = [event for event in sink if event['kind'] == 'sensor_received' and event['topic'] == topic]
        known = {event['seq']: event for event in published}
        assert len(known) == len(published)
        assert all(event['seq'] in known and event['payload_bytes'] == payload for event in received)
        first = {}
        for event in received:
            first.setdefault(event['seq'], event)
        pub_arm = statuses['bulk']['arm_ns']; rx_arm = statuses['sink']['arm_ns']
        planned = int(round(seconds*10))
        assert all(0 <= seq < planned for seq in known)
        for key, value in {
            'published_seq': [event['seq'] for event in published],
            'planned_ns': [event['planned_ns']-pub_arm for event in published],
            'publish_start_ns': [event['publish_start_ns']-pub_arm for event in published],
            'publish_end_ns': [event['publish_end_ns']-pub_arm for event in published],
            'received_seq': [event['seq'] for event in received],
            'received_ns': [event['received_ns']-rx_arm for event in received],
        }.items():
            arrays[topic+'_'+key] = np.array(value, dtype=np.int64)
        relative_receipt = np.array([event['received_ns']-rx_arm for event in first.values()], dtype=np.int64)
        within = (relative_receipt >= 0) & (relative_receipt < seconds*1e9)
        publication = (arrays[topic+'_publish_end_ns']-arrays[topic+'_publish_start_ns'])/1e6
        result[topic] = dict(planned=planned, published=len(published),
            unsent_planned=planned-len(published), received_callbacks=len(received),
            unique_received=len(first), duplicate_received=len(received)-len(first),
            received_within_window=int(within.sum()), payload_bytes=payload,
            delivered_payload_mbps=float(within.sum()*payload*8/seconds/1e6),
            delivered_including_grace=len(first),
            publication_p99_ms=percentile(publication),
            maximum_update_gap_ms=maximum_gap(relative_receipt, seconds))
    return arrays, result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw', type=Path, default=Path.home()/'.local/share/esp-sdr/two-team/raw')
    parser.add_argument('--experiment', choices=['qos', 'power'], default='qos')
    args = parser.parse_args()
    mode = 'ros2' if args.experiment == 'qos' else 'power'
    target = ROOT/'data/operational'/mode
    target.mkdir(parents=True, exist_ok=True)
    groups = defaultdict(list); frames = 0
    for file in sorted(args.raw.glob(f'op-{mode}-*.json')):
        if file.stem.endswith('-iq'):
            continue
        raw = json.loads(file.read_text()); context = raw['context']; name = file.stem
        assert not raw['sdr_errors']
        assert raw.get('trace_download_complete', True), f'{name}: robot trace download is incomplete'
        directory = Path(context['role_directory'])
        role_paths = {role: directory/('robot' if role in ('echo', 'bulk') else '') for role in ('control', 'sink', 'echo', 'bulk')}
        statuses = {role: json.loads((path/(role+'.json')).read_text()) for role, path in role_paths.items()}
        traces = {role: events(path/(role+'.ndjson')) for role, path in role_paths.items()}
        control, metrics = summarize_control(traces['control'], statuses['control'], raw['seconds'])
        sensors, sensor_metrics = summarize_sensors(traces['bulk'], traces['sink'], statuses, raw['seconds'])
        np.savez_compressed(target/(name+'-control.npz'), **control)
        np.savez_compressed(target/(name+'-sensors.npz'), **sensors)
        # Robot echo timings are explicitly relative to the robot clock only.
        echo = [event for event in traces['echo'] if event['kind'] == 'command_echoed']
        np.savez_compressed(target/(name+'-echo.npz'), seq=np.array([event['seq'] for event in echo], dtype=np.int64),
            **{key: np.array([event[key]-statuses['echo']['arm_ns'] for event in echo], dtype=np.int64)
               for key in ('received_ns', 'publish_start_ns', 'publish_end_ns')})
        meta = json.loads((args.raw/(name+'-iq.json')).read_text()); assert meta['all_crcs_verified']
        iq = np.load(args.raw/(name+'-iq.npz'))['iq']; frequency, power = spectra(iq, 80000000, 1024)
        start = np.array([item['host_start_monotonic'] for item in meta['timing']]); end = np.array([item['host_end_monotonic'] for item in meta['timing']])
        np.savez_compressed(target/(name+'-spectrum.npz'), frequency_mhz=frequency/1e6+meta['lo_mhz'],
            power_dbfs=(10*np.log10(np.maximum(power, 1e-16))).astype(np.float32),
            capture_start_s=start-statuses['control']['arm_ns']/1e9,
            capture_end_s=end-statuses['control']['arm_ns']/1e9)
        elapsed = (context['after_ns']-context['before_ns'])/1e9
        setup = context['setup_history'][-1][-1]
        row = dict(run_id=raw['run_id'], seconds=raw['seconds'],
            acquisition_segment=context.get('acquisition_session_id','ros2-qos-initial'),
            trace_download_transport=raw.get('trace_download_transport','verified SSH after measurement'),
            condition={key: context[key] for key in ('repeat', 'bulk', 'reliability', 'depth', 'own_channel', 'own_width_mhz', 'other_channel', 'other_width_mhz')},
            robot_power_save={phase: context['robot_power_'+phase]['state'] for phase in ('before', 'after')},
            controller_power_save=context['controller_power_readback'].strip().lower().removeprefix('power save: ').strip(),
            layout=context['layout'], pre_measurement_setup_attempts=context['setup_attempts'],
            pre_load_peer_verification={role: setup[role] for role in ('receiver', 'transmitter')},
            external_radio={role: {phase: {key: value for key, value in context[f'board{number}_{phase}'].items() if key not in ('mac', 'peer')}
                                   for phase in ('before', 'after')} for role, number in [('receiver', 1), ('transmitter', 2)]},
            other_load_command_ack=context['other_load_ack'], other_counter_window_seconds=elapsed,
            other_delivered_mbps=raw['other_delivered_mbps'],
            other_socket_accepted_mbps=(context['board2_after']['tx_bytes']-context['board2_before']['tx_bytes'])*8/elapsed/1e6,
            other_send_attempts=context['board2_after']['send_attempts']-context['board2_before']['send_attempts'],
            roles={role: measurement_status(status) for role, status in statuses.items()},
            roles_before={role: measurement_status(context['local_roles_before'][role]['measurement']
                          if role in ('control', 'sink') else context['robot_before']['roles'][role]['measurement'])
                          for role in statuses},
            experimental_route_verified=('dev wlp132s0f0' in context['route_to_robot'] and '192.168.8.1' in context['route_to_robot']),
            control=metrics, sensors=sensor_metrics,
            sdr=dict(frames=len(iq), samples=16380, sample_rate_hz=80000000, lo_mhz=meta['lo_mhz'],
                bandwidth_mhz=48, gain='MANUAL 20', fft_length=1024, all_crcs_verified=True,
                nominal_observation_pct=len(iq)*16380/80000000/(end[-1]-start[0])*100),
            clock_semantics='Control and RTT use only the controller clock. Echo processing and sensor generation use only the robot clock. Sensor receipt gaps use only the sink clock. No cross-PC one-way latency or sensor age is inferred.',
            topology='Controller and sink on the PC AP; echo and synthetic sensor source on the robot STA. Control and bulk run in separate processes. This differs from the STA-AP-STA UDP/TCP topology.')
        if args.experiment == 'power':
            row['condition']['power_save'] = context['power_save']
        (target/(name+'.json')).write_text(json.dumps(row, ensure_ascii=False, indent=2)+'\n')
        groups[name.rsplit('-r', 1)[0]].append((row, control)); frames += len(iq)
    summary = {}
    for name, trials in groups.items():
        received_rtt = []; deadlines = []; publication = []; lateness = []
        for row, control in trials:
            published = control['sent_ns'] >= 0; received = control['received_ns'] >= 0
            received_rtt.extend((control['received_ns'][received]-control['sent_ns'][received])/1e6)
            deadlines.extend(~received | (control['received_ns']-control['planned_ns'] > 20_000_000))
            publication.extend((control['publish_end_ns'][published]-control['publish_start_ns'][published])/1e6)
            lateness.extend((control['sent_ns'][published]-control['planned_ns'][published])/1e6)
        summary[name] = dict(condition={key: value for key, value in trials[0][0]['condition'].items() if key != 'repeat'},
            runs=len(trials), planned=sum(row['control']['planned'] for row, _ in trials),
            published=sum(row['control']['published'] for row, _ in trials),
            received=sum(row['control']['unique_responses'] for row, _ in trials),
            pooled_rtt_p99_ms=percentile(received_rtt), planned_deadline20_pct=float(np.mean(deadlines)*100),
            pooled_publication_p99_ms=percentile(publication), pooled_send_lateness_p99_ms=percentile(lateness),
            run_control=[row['control'] for row, _ in trials],
            run_sensors=[row['sensors'] for row, _ in trials],
            delivered_other_mbps=[row['other_delivered_mbps'] for row, _ in trials])
    (target/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    manifest_path = ROOT/'data/manifest.json'; manifest = json.loads(manifest_path.read_text())
    manifest.setdefault('operational', {})[mode] = dict(trials=sum(value['runs'] for value in summary.values()),
        conditions=len(summary), control_planned=sum(value['planned'] for value in summary.values()),
        control_published=sum(value['published'] for value in summary.values()),
        control_received=sum(value['received'] for value in summary.values()), iq_snapshots_original=frames)
    for file in sorted(target.iterdir()):
        manifest['files'][str(file.relative_to(ROOT/'data'))] = hashlib.sha256(file.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    print(manifest['operational'][mode])


if __name__ == '__main__':
    main()
