#!/usr/bin/env python3
"""Verify ROS 2 matrix, independent clocks, QoS evidence and public aggregates."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np


def q99(values):
    return float(np.percentile(values, 99)) if len(values) else None


def same(a, b):
    return a is b if a is None or b is None else bool(np.isclose(a, b, atol=1e-9))


def gap(times, seconds):
    times = np.unique(times[(times >= 0) & (times <= seconds*1e9)])
    return float(np.diff(np.r_[0, times, int(seconds*1e9)]).max()/1e6)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--require-complete', action='store_true')
    parser.add_argument('--experiment', choices=['qos', 'power'], default='qos')
    args = parser.parse_args(); root = Path(__file__).resolve().parents[1]
    mode = 'ros2' if args.experiment == 'qos' else 'power'
    target = root/'data/operational'/mode; manifest = json.loads((root/'data/manifest.json').read_text())
    assert mode in manifest.get('operational', {}), f'no {mode} matrix recorded'
    for name, digest in manifest['files'].items():
        assert hashlib.sha256((root/'data'/name).read_bytes()).hexdigest() == digest, name
    summary = json.loads((target/'summary.json').read_text()); groups = defaultdict(list)
    covered = set(); planned_total = published_total = received_total = frames_total = 0
    for file in sorted(target.glob(f'op-{mode}-*.json')):
        row = json.loads(file.read_text()); condition = row['condition']; metrics = row['control']
        control = np.load(target/(file.stem+'-control.npz')); sensors = np.load(target/(file.stem+'-sensors.npz'))
        echo = np.load(target/(file.stem+'-echo.npz')); seconds = row['seconds']
        assert seconds == 30 and len(control['sent_ns']) == 3000
        assert np.array_equal(control['planned_ns'], np.arange(3000)*10_000_000)
        published = control['sent_ns'] >= 0; received = control['received_ns'] >= 0
        assert np.all(received <= published)
        assert np.all(control['publish_start_ns'][published] >= control['sent_ns'][published])
        assert np.all(control['publish_end_ns'][published] >= control['publish_start_ns'][published])
        assert np.all(control['received_ns'][received] >= control['sent_ns'][received])
        assert np.all(control['echo_pre_publish_ns'][received] >= 0)
        assert metrics['planned'] == 3000 and metrics['published'] == published.sum()
        assert metrics['unsent_planned'] == 3000-published.sum() and metrics['unique_responses'] == received.sum()
        assert metrics['lost_published'] == (published & ~received).sum()
        rtt = (control['received_ns'][received]-control['sent_ns'][received])/1e6
        local_publish = (control['publish_end_ns'][published]-control['publish_start_ns'][published])/1e6
        lateness = (control['sent_ns'][published]-control['planned_ns'][published])/1e6
        deadlines = ~received | (control['received_ns']-control['planned_ns'] > 20_000_000)
        rtt_deadlines = ~received | (control['received_ns']-control['sent_ns'] > 20_000_000)
        for actual, recorded in [(q99(rtt), metrics['rtt_p99_ms']),
            (q99(local_publish), metrics['publication_p99_ms']), (q99(lateness), metrics['send_lateness_p99_ms']),
            (deadlines.mean()*100, metrics['planned_deadline20_pct']),
            (rtt_deadlines[published].mean()*100 if published.any() else None, metrics['published_deadline20_pct']),
            (gap(control['received_ns'][received], seconds), metrics['maximum_response_gap_ms'])]:
            assert same(actual, recorded), (file.name, actual, recorded)
        assert np.all(echo['publish_end_ns'] >= echo['publish_start_ns'])
        assert np.all(echo['publish_start_ns'] >= echo['received_ns'])
        assert set(echo['seq']).issubset(set(np.flatnonzero(published)))
        assert metrics['responses']-metrics['unique_responses'] == metrics['duplicate_responses']
        assert len(echo['seq']) == row['roles']['echo']['received'] == row['roles']['echo']['sent']
        assert row['roles']['control']['sent'] == metrics['published']
        assert row['roles']['control']['received'] == metrics['responses']
        assert condition['own_channel'] == 6 and condition['own_width_mhz'] == condition['other_width_mhz'] == 20
        assert row['experimental_route_verified'] and row['layout']['source'] == 'user report'
        assert '30 cm' in row['layout']['description']
        expected_power = 'off' if args.experiment == 'qos' else condition['power_save']
        assert row['robot_power_save']['before'] == row['robot_power_save']['after'] == expected_power
        assert row['controller_power_save'] == 'off'
        for role, status in row['roles'].items():
            assert status['done'] and status['run_id'] == row['run_id'] and status['dds_experimental_interface_only']
            assert status['rmw'] == 'rmw_cyclonedds_cpp' and status['domain_id'] == '77'
            assert status['bulk'] == condition['bulk'] and status['bulk_reliability'] == condition['reliability']
            assert status['bulk_depth'] == condition['depth']
            assert status['control_reliability'] == 'reliable' and status['control_depth'] == 10
            expected_reliability = 1 if role in ('control', 'echo') or condition['reliability'] == 'reliable' else 2
            expected_depth = 10 if role in ('control', 'echo') else condition['depth']
            for endpoints in status['endpoint_qos'].values():
                for endpoint in endpoints:
                    assert endpoint['reliability'] == expected_reliability and endpoint['depth'] == expected_depth
                    assert endpoint['history'] == 1 and endpoint['durability'] == 2
            before = row['roles_before'][role]
            assert before['ready'] and not before['done'] and before['dds_experimental_interface_only']
            if role in ('control', 'echo') or condition['bulk'] == 'heavy':
                assert all(count > 0 for values in before['counts'].values() for count in values)
                assert before['graph_publisher_qos'] and all(before['graph_publisher_qos'].values())
                for publishers in before['graph_publisher_qos'].values():
                    assert all(publisher['reliability'] == expected_reliability for publisher in publishers)
        for topic, size in [('image', 691200), ('cloud', 65536)]:
            data = row['sensors'][topic]; pubs = sensors[topic+'_published_seq']; receipts = sensors[topic+'_received_seq']
            assert len(set(pubs)) == len(pubs) and np.all((pubs >= 0) & (pubs < 300))
            assert set(receipts).issubset(set(pubs))
            assert data['planned'] == 300 and data['published'] == len(pubs) and data['unsent_planned'] == 300-len(pubs)
            assert data['received_callbacks'] == len(receipts) and data['unique_received'] == len(set(receipts))
            assert data['payload_bytes'] == size
            assert np.all(sensors[topic+'_publish_end_ns'] >= sensors[topic+'_publish_start_ns'])
            assert np.array_equal(sensors[topic+'_planned_ns'], pubs*100_000_000)
            _, unique_indexes = np.unique(receipts, return_index=True)
            receipt_times = sensors[topic+'_received_ns'][unique_indexes]
            within = (receipt_times >= 0) & (receipt_times < seconds*1e9)
            assert data['received_within_window'] == within.sum()
            assert same(within.sum()*size*8/seconds/1e6, data['delivered_payload_mbps'])
            assert same(gap(receipt_times, seconds), data['maximum_update_gap_ms'])
            if condition['bulk'] == 'off':
                assert len(pubs) == len(receipts) == 0
            assert row['roles']['bulk']['publish_calls'] == sum(row['sensors'][t]['published'] for t in ('image', 'cloud'))
            assert row['roles']['sink']['received'] == sum(row['sensors'][t]['received_callbacks'] for t in ('image', 'cloud'))
        proof = row['pre_load_peer_verification']; source = proof['transmitter']; destination = proof['receiver']
        assert source['tcp_peer_ready'] and destination['tcp_peer_ready'] and source['tcp_connected'] and destination['connected']
        assert source['tcp_nonce'] == destination['tcp_nonce'] > 0 and source['tcp_challenge'] == destination['tcp_challenge'] > 0
        assert source['primary'] == destination['primary'] == condition['other_channel']
        assert source['power_save'] == destination['power_save'] == 0
        radio = row['external_radio']; window = row['other_counter_window_seconds']
        assert row['other_load_command_ack'] == 'OK LOAD 1000 44'
        for role in ('transmitter', 'receiver'):
            for phase in ('before', 'after'):
                assert radio[role][phase]['version'] == 7
        for phase in ('before', 'after'):
            assert radio['transmitter'][phase]['load_rate_setting'] == 1000
            assert radio['transmitter'][phase]['load_remaining_ms'] > 0
        assert same((radio['receiver']['after']['rx_bytes']-radio['receiver']['before']['rx_bytes'])*8/window/1e6, row['other_delivered_mbps'])
        assert same((radio['transmitter']['after']['tx_bytes']-radio['transmitter']['before']['tx_bytes'])*8/window/1e6, row['other_socket_accepted_mbps'])
        assert row['other_send_attempts'] == radio['transmitter']['after']['send_attempts']-radio['transmitter']['before']['send_attempts']
        assert row['other_delivered_mbps'] > 0 or row['other_send_attempts'] > 0
        spectrum = np.load(target/(file.stem+'-spectrum.npz'))
        assert spectrum['power_dbfs'].shape == (row['sdr']['frames'], 1024)
        assert np.isfinite(spectrum['power_dbfs']).all() and row['sdr']['all_crcs_verified']
        covered.add((condition['repeat'], condition['bulk'], condition['reliability'], condition['depth'], condition['other_channel'])
                    if args.experiment == 'qos' else
                    (condition['repeat'], condition['bulk'], condition['power_save'], condition['other_channel']))
        groups[file.stem.rsplit('-r', 1)[0]].append((row, rtt, deadlines, local_publish, lateness))
        planned_total += 3000; published_total += int(published.sum()); received_total += int(received.sum()); frames_total += row['sdr']['frames']
    for name, trials in groups.items():
        value = summary[name]
        assert value['runs'] == len(trials)
        assert value['planned'] == sum(row['control']['planned'] for row, *_ in trials)
        assert value['published'] == sum(row['control']['published'] for row, *_ in trials)
        assert value['received'] == sum(row['control']['unique_responses'] for row, *_ in trials)
        assert same(q99(np.concatenate([rtt for _, rtt, *_ in trials])), value['pooled_rtt_p99_ms'])
        assert same(np.concatenate([deadlines for _, _, deadlines, *_ in trials]).mean()*100, value['planned_deadline20_pct'])
    expected = manifest['operational'][mode]
    assert (len(covered), planned_total, published_total, received_total, frames_total) == (
        expected['trials'], expected['control_planned'], expected['control_published'], expected['control_received'], expected['iq_snapshots_original'])
    matrix = {(rep, 'off', 'best_effort', 1, ch) for rep in (1, 2, 3) for ch in (6, 7, 11)}
    matrix |= {(rep, 'heavy', reliability, depth, ch) for rep in (1, 2, 3)
               for reliability in ('reliable', 'best_effort') for depth in (1, 10) for ch in (6, 7, 11)}
    if args.experiment == 'power':
        matrix = {(rep, bulk, power, ch) for rep in (1, 2, 3) for bulk in ('off', 'heavy')
                  for power in ('on', 'off') for ch in (6, 11)}
    if args.require_complete:
        assert covered == matrix and len(summary) == (15 if args.experiment == 'qos' else 8)
        assert all(value['runs'] == 3 for value in summary.values())
    print(mode, expected, 'complete_matrix:', covered == matrix)


if __name__ == '__main__':
    main()
