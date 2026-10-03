#!/usr/bin/env python3
"""Continuous ESP-NOW application timelines, independently of intermittent RF."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np

from signal_processing import spectra
from acquisition.placement_conditions import validate_fields

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT/'data/operational/espnow-long'


def q99(values):
    return float(np.percentile(values, 99)) if len(values) else None


def longest_run(mask):
    boundaries = np.diff(np.r_[False, mask, False].astype(np.int8))
    starts = np.flatnonzero(boundaries == 1); ends = np.flatnonzero(boundaries == -1)
    return int(np.max(ends-starts)) if len(starts) else 0


def maximum_gap(times_ns, seconds):
    end = int(seconds*1e9)
    times = np.unique(np.asarray(times_ns, dtype=np.int64))
    times = times[(times >= 0) & (times <= end)]
    return float(np.diff(np.r_[0, times, end]).max()/1e6)


def summarize_events(events, hz, seconds):
    """Complete planned timeline, including scheduling skips and API errors."""
    planned = hz*seconds; period_ns = 1_000_000_000//hz
    arrays = dict(planned_ns=np.arange(planned, dtype=np.int64)*period_ns,
                  sent_ns=np.full(planned, -1, dtype=np.int64),
                  received_ns=np.full(planned, -1, dtype=np.int64),
                  api_error=np.full(planned, -1, dtype=np.int64))
    calls = events[events[:, 0] == 1]; replies = events[events[:, 0] == 2]
    assert len(np.unique(calls[:, 1])) == len(calls)
    assert np.all(calls[:, 1] < planned) and np.all(replies[:, 1] < planned)
    arrays['sent_ns'][calls[:, 1]] = calls[:, 2].astype(np.int64)*1000
    arrays['api_error'][calls[:, 1]] = calls[:, 3].astype(np.int64)
    assert np.all(arrays['sent_ns'][calls[:, 1]] >= arrays['planned_ns'][calls[:, 1]])
    for _, sequence, timestamp, original_sent in replies:
        assert arrays['sent_ns'][sequence] == int(original_sent)*1000
        assert timestamp >= original_sent
        if arrays['received_ns'][sequence] < 0:
            arrays['received_ns'][sequence] = int(timestamp)*1000
    called = arrays['sent_ns'] >= 0; received = arrays['received_ns'] >= 0
    assert np.all(received <= called)
    skipped = np.zeros(planned, dtype=bool)
    for _, sequence, _, count in events[events[:, 0] == 3]:
        sequence = int(sequence); count = int(count)
        assert 0 < count and sequence+count <= planned
        assert not skipped[sequence:sequence+count].any()
        skipped[sequence:sequence+count] = True
    assert np.array_equal(skipped, ~called), 'Missing UART events cannot be treated as local skips'
    error = called & (arrays['api_error'] != 0); accepted = called & ~error
    rtt = (arrays['received_ns'][received]-arrays['sent_ns'][received])/1e6
    lateness = (arrays['sent_ns'][called]-arrays['planned_ns'][called])/1e6
    scheduled_deadline = ~received | (arrays['received_ns']-arrays['planned_ns'] > 20_000_000)
    send_deadline = ~received | (arrays['received_ns']-arrays['sent_ns'] > 20_000_000)
    fresh = []; greatest_sequence = -1; stale = 0
    for sequence in np.flatnonzero(received)[np.argsort(arrays['received_ns'][received], kind='stable')]:
        if sequence > greatest_sequence:
            greatest_sequence = int(sequence); fresh.append(arrays['received_ns'][sequence])
        else:
            stale += 1
    metrics = dict(planned=planned, send_calls=int(called.sum()), unsent_planned=int(skipped.sum()),
        api_errors=int(error.sum()), api_accepted=int(accepted.sum()), reply_callbacks=len(replies),
        unique_replies=int(received.sum()), duplicate_replies=len(replies)-int(received.sum()),
        replies_after_api_error=int((received & error).sum()),
        api_accepted_without_reply=int((accepted & ~received).sum()),
        loss_from_planned_pct=float((~received).mean()*100), rtt_p99_ms=q99(rtt),
        send_lateness_p99_ms=q99(lateness),
        planned_deadline20_pct=float(scheduled_deadline.mean()*100),
        called_deadline20_pct=float(send_deadline[called].mean()*100) if called.any() else None,
        longest_missing_reply_run=longest_run(~received),
        longest_planned_deadline20_run=longest_run(scheduled_deadline),
        maximum_reply_gap_ms=maximum_gap(arrays['received_ns'][received], seconds),
        maximum_increasing_sequence_gap_ms=maximum_gap(fresh, seconds),
        out_of_order_first_replies=stale)
    timeline = []
    for start in range(0, seconds, 10):
        end = min(start+10, seconds); selection = (arrays['planned_ns'] >= start*1e9) & (arrays['planned_ns'] < end*1e9)
        ok = selection & received; emitted = selection & called
        timeline.append(dict(start_s=start, end_s=end, planned=int(selection.sum()),
            send_calls=int(emitted.sum()), api_errors=int((selection & error).sum()), replies=int(ok.sum()),
            planned_deadline20_pct=float(scheduled_deadline[selection].mean()*100),
            rtt_p99_ms=q99((arrays['received_ns'][ok]-arrays['sent_ns'][ok])/1e6),
            send_lateness_p99_ms=q99((arrays['sent_ns'][emitted]-arrays['planned_ns'][emitted])/1e6)))
    return arrays, metrics, timeline


def public_radio(state):
    return {key: value for key, value in state.items() if key not in ('mac', 'peer')}


def source_counters(state):
    return {key: state[key] for key in ('helper_version', 'configuration_generation', 'tcp_connection_generation',
            'run_id', 'requested_mbps', 'period_ms', 'sent_payload_bytes', 'generated_payload_bytes',
            'pending_application_bytes', 'tcp_connected')}


def main():
    global TARGET
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw', type=Path, default=Path.home()/'.local/share/esp-sdr/two-team/raw')
    parser.add_argument('--experiment', choices=['long', 'placement'], default='long')
    parser.add_argument('--stop-record', type=Path,
        default=Path.home()/'.local/share/esp-sdr/two-team/evidence/espnow-long-user-stop.json')
    args = parser.parse_args()
    mode = 'espnow-long' if args.experiment == 'long' else 'placement'
    TARGET = ROOT/'data/operational'/mode; TARGET.mkdir(parents=True, exist_ok=True)
    groups = defaultdict(list); frames = 0
    for file in sorted(args.raw.glob(f'op-{mode}-*.json')):
        if file.stem.endswith('-iq'):
            continue
        raw = json.loads(file.read_text()); context = raw['context']; name = file.stem
        assert not raw['sdr_errors'] and raw['uart']['all_crcs_verified']
        trace = np.load(args.raw/(name+'-events.npz'))
        events = trace['events']; seconds = raw['seconds']; hz = context['hz']
        arrays, metrics, timeline = summarize_events(events, hz, seconds)
        np.savez_compressed(TARGET/(name+'-control.npz'), **arrays)
        np.savez_compressed(TARGET/(name+'-events.npz'), events=events,
                            block_received_ns=trace['block_received_ns'], block_event_counts=trace['block_event_counts'])
        samples = []
        for sample in context['counter_samples']:
            public = dict(relative_s=(sample['host_ns']-context['before_ns'])/1e9,
                          read_failed='error' in sample)
            if 'receiver' in sample:
                public['receiver'] = public_radio(sample['receiver'])
            if 'echo' in sample:
                public['echo'] = public_radio(sample['echo'])
                public['echo_received_since_previous_sample'] = sample['echo_received_since_previous_sample']
            if 'source' in sample:
                public['source'] = source_counters(sample['source'])
            samples.append(public)
        window = (context['after_ns']-context['before_ns'])/1e9
        meta = json.loads((args.raw/(name+'-iq.json')).read_text()); assert meta['all_crcs_verified']
        assert (meta['lo_mhz'], meta['sample_rate_hz'], meta['bandwidth_mhz'], meta['gain'], meta['samples']) == (
            2442, 80000000, 48, 'MANUAL 20', 16380), 'Do not mix different SDR settings into the fixed-layout comparison'
        iq = np.load(args.raw/(name+'-iq.npz'))['iq']
        assert iq.shape == (meta['frames'], 16380, 2) and len(meta['timing']) == meta['frames'] > 0
        frequency, power = spectra(iq, 80000000, 1024)
        start = np.array([item['host_start_monotonic'] for item in meta['timing']]); end = np.array([item['host_end_monotonic'] for item in meta['timing']])
        np.savez_compressed(TARGET/(name+'-spectrum.npz'), frequency_mhz=frequency/1e6+meta['lo_mhz'],
            power_dbfs=(10*np.log10(np.maximum(power, 1e-16))).astype(np.float32),
            capture_start_s=start-raw['uart']['host_start_ns']/1e9,
            capture_end_s=end-raw['uart']['host_start_ns']/1e9)
        row = dict(run_id=raw['run_id'], seconds=seconds,
            acquisition_segment=context.get('acquisition_session_id','espnow-long-initial'),
            condition={key: context[key] for key in ('repeat', 'hz', 'wifi', 'espnow_channel', 'wifi_channel', 'wifi_width_mhz')},
            layout=context['layout'], application=metrics, timeline=timeline,
            radio={role: {phase: public_radio(context[role+'_'+phase]) for phase in ('before', 'after')}
                   for role in ('sender', 'echo', 'wifi')},
            source={phase: source_counters(context['source_'+phase]) for phase in ('before', 'after')},
            wifi_counter_window_seconds=window,
            wifi_delivered_mbps=(context['wifi_after']['rx_bytes']-context['wifi_before']['rx_bytes'])*8/window/1e6,
            counter_samples=samples,
            counter_sample_interval_seconds=context.get('counter_sample_interval_seconds', 10),
            uart=dict(all_crcs_verified=True, blocks=len(trace['block_event_counts']),
                      event_count=len(events), host_window_seconds=(raw['uart']['host_end_ns']-raw['uart']['host_start_ns'])/1e9),
            sdr=dict(frames=len(iq), samples=16380, sample_rate_hz=80000000, lo_mhz=meta['lo_mhz'],
                     bandwidth_mhz=48, gain='MANUAL 20', fft_length=1024, all_crcs_verified=True,
                     nominal_observation_pct=len(iq)*16380/80000000/(end[-1]-start[0])*100),
            semantics='Complete ESP-NOW application timeline from the sender clock; configured 1 Mbps long-preamble unencrypted unicast. MAC results are aggregates. Echo RSSI is the latest received packet, not an interval mean; zero new messages gives no fresh RSSI evidence. Wi-Fi idle includes AP beacons and telemetry. C5 RF capture is intermittent and uncalibrated.')
        if args.experiment == 'placement':
            placement = validate_fields(context['placement'])
            assert seconds == 10 and hz == 100
            row['condition']['placement_id'] = placement['id']
            assert row['layout']['placement'] == placement
        (TARGET/(name+'.json')).write_text(json.dumps(row, ensure_ascii=False, indent=2)+'\n')
        groups[name.rsplit('-r', 1)[0]].append((row, arrays)); frames += len(iq)
    summary = {}
    for name, trials in groups.items():
        rtt = []; deadlines = []
        for row, arrays in trials:
            received = arrays['received_ns'] >= 0
            rtt.extend((arrays['received_ns'][received]-arrays['sent_ns'][received])/1e6)
            deadlines.extend(~received | (arrays['received_ns']-arrays['planned_ns'] > 20_000_000))
        summary[name] = dict(condition={key: value for key, value in trials[0][0]['condition'].items() if key != 'repeat'},
            runs=len(trials), seconds=[row['seconds'] for row, _ in trials],
            planned=sum(row['application']['planned'] for row, _ in trials),
            send_calls=sum(row['application']['send_calls'] for row, _ in trials),
            replies=sum(row['application']['unique_replies'] for row, _ in trials),
            pooled_rtt_p99_ms=q99(rtt), planned_deadline20_pct=float(np.mean(deadlines)*100),
            run_application=[row['application'] for row, _ in trials],
            wifi_delivered_mbps=[row['wifi_delivered_mbps'] for row, _ in trials])
    (TARGET/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    path = ROOT/'data/manifest.json'; manifest = json.loads(path.read_text())
    manifest.setdefault('operational', {})[mode] = dict(trials=sum(value['runs'] for value in summary.values()),
        conditions=len(summary), control_planned=sum(value['planned'] for value in summary.values()),
        control_send_calls=sum(value['send_calls'] for value in summary.values()),
        control_received=sum(value['replies'] for value in summary.values()), iq_snapshots_original=frames)
    if args.experiment == 'long':
        metadata = manifest['operational'][mode]
        metadata['planned_trials'] = 24
        metadata['status'] = 'complete' if metadata['trials'] == 24 else 'in_progress'
        if args.stop_record.exists() and metadata['trials'] < 24:
            stopped = json.loads(args.stop_record.read_text())
            assert stopped['decision_source'] == 'user request' and stopped['current_trial_complete'] is True
            assert stopped['planned_trials'] == 24 and (TARGET/(stopped['final_trial']+'.json')).exists()
            metadata.update(status='stopped_at_user_request', stop_after_trial=stopped['final_trial'],
                scope_note='The user requested to finish soon. Retain all saved trials; omit the remaining long trials and disclose unequal repetitions. Not a complete 24-trial matrix.')
    for file in sorted(TARGET.iterdir()):
        manifest['files'][str(file.relative_to(ROOT/'data'))] = hashlib.sha256(file.read_bytes()).hexdigest()
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    print(manifest['operational'][mode])


if __name__ == '__main__':
    main()
