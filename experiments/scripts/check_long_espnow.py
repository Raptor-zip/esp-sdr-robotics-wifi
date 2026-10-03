#!/usr/bin/env python3
"""Audit continuous windows, telemetry integrity and all condition repetitions."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np
from acquisition.placement_conditions import PLACEMENT_IDS, validate_fields


def q99(values):
    return float(np.percentile(values, 99)) if len(values) else None


def same(a, b):
    return a is b if a is None or b is None else bool(np.isclose(a, b, atol=1e-9))


def gap(times, seconds):
    selected = np.unique(times[(times >= 0) & (times <= seconds*1e9)])
    return float(np.diff(np.r_[0, selected, int(seconds*1e9)]).max()/1e6)


def missing_run(received):
    received_indexes = np.r_[-1, np.flatnonzero(received), len(received)]
    return int(np.max(np.diff(received_indexes))-1)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--require-complete', action='store_true')
    parser.add_argument('--require-user-stop', action='store_true',
        help='Verify all acquired trials and at least two full repetitions after an explicitly recorded user stop')
    parser.add_argument('--require-declared-scope', action='store_true',
        help='Require the complete planned matrix or the explicitly declared user-requested stop scope')
    parser.add_argument('--experiment', choices=['long', 'placement'], default='long')
    args = parser.parse_args(); root = Path(__file__).resolve().parents[1]
    mode = 'espnow-long' if args.experiment == 'long' else 'placement'
    target = root/'data/operational'/mode; manifest = json.loads((root/'data/manifest.json').read_text())
    assert mode in manifest.get('operational', {}), f'no {mode} trials recorded'
    for name, digest in manifest['files'].items():
        assert hashlib.sha256((root/'data'/name).read_bytes()).hexdigest() == digest, name
    covered = set(); groups = defaultdict(list); planned_total = sent_total = received_total = frame_total = 0
    placements = {}
    for file in sorted(target.glob(f'op-{mode}-*.json')):
        row = json.loads(file.read_text()); condition = row['condition']; stats = row['application']
        seconds = row['seconds']; hz = condition['hz']; count = seconds*hz
        if args.experiment == 'long':
            assert seconds in (600, 1200) and hz in (20, 50, 100, 200)
        else:
            assert seconds == 10 and hz == 100
            placement = validate_fields(row['layout']['placement'])
            assert placement['id'] == condition['placement_id']
            if placement['id'] in placements:
                assert placement == placements[placement['id']]
            placements[placement['id']] = placement
        assert condition['espnow_channel'] == condition['wifi_channel'] == 6 and condition['wifi_width_mhz'] == 20
        # NPZ lookup decompresses a member on every access. Cache columns
        # before the per-sequence audit; otherwise it becomes quadratic.
        with np.load(target/(file.stem+'-control.npz')) as archive:
            arrays = {key: archive[key] for key in archive.files}
        trace = np.load(target/(file.stem+'-events.npz'))
        events = trace['events']; kinds = events[:, 0]; calls = events[kinds == 1]; replies = events[kinds == 2]
        finish = events[kinds == 4]
        assert len(finish) == 1 and kinds[-1] == 4 and finish[0, 1] == count and finish[0, 3] == row['run_id']
        assert (seconds+2)*1e6 <= finish[0, 2] < (seconds+8)*1e6
        assert trace['block_event_counts'].sum() == len(events) == row['uart']['event_count']
        assert len(trace['block_event_counts']) == row['uart']['blocks'] and row['uart']['all_crcs_verified']
        assert np.array_equal(arrays['planned_ns'], np.arange(count, dtype=np.int64)*(1_000_000_000//hz))
        assert len(np.unique(calls[:, 1])) == len(calls) and np.all(calls[:, 1] < count)
        assert np.all(replies[:, 1] < count)
        emitted = arrays['sent_ns'] >= 0; received = arrays['received_ns'] >= 0
        assert np.all(received <= emitted) and emitted.sum() == len(calls)
        assert np.array_equal(arrays['sent_ns'][calls[:, 1]], calls[:, 2].astype(np.int64)*1000)
        assert np.array_equal(arrays['api_error'][calls[:, 1]], calls[:, 3])
        assert np.all(arrays['sent_ns'][emitted] >= arrays['planned_ns'][emitted])
        skipped_indexes = []
        for _, sequence, _, skipped in events[kinds == 3]:
            skipped_indexes.extend(range(int(sequence), int(sequence)+int(skipped)))
        assert len(set(skipped_indexes)) == len(skipped_indexes)
        assert set(skipped_indexes) == set(np.flatnonzero(~emitted))
        first_replies = {}
        for _, sequence, timestamp, original in replies:
            assert arrays['sent_ns'][sequence] == int(original)*1000 and timestamp >= original
            first_replies.setdefault(int(sequence), int(timestamp)*1000)
        assert set(first_replies) == set(np.flatnonzero(received))
        assert all(arrays['received_ns'][sequence] == timestamp for sequence, timestamp in first_replies.items())
        error = emitted & (arrays['api_error'] != 0); accepted = emitted & ~error
        rtt = (arrays['received_ns'][received]-arrays['sent_ns'][received])/1e6
        lateness = (arrays['sent_ns'][emitted]-arrays['planned_ns'][emitted])/1e6
        deadline = ~received | (arrays['received_ns']-arrays['planned_ns'] > 20_000_000)
        called_deadline = ~received | (arrays['received_ns']-arrays['sent_ns'] > 20_000_000)
        assert (stats['planned'], stats['send_calls'], stats['unsent_planned'], stats['unique_replies']) == (count, emitted.sum(), (~emitted).sum(), received.sum())
        assert stats['api_errors'] == error.sum() and stats['api_accepted'] == accepted.sum()
        assert stats['api_accepted_without_reply'] == (accepted & ~received).sum()
        assert stats['replies_after_api_error'] == (received & error).sum()
        assert stats['reply_callbacks'] == len(replies) and stats['duplicate_replies'] == len(replies)-received.sum()
        assert same(q99(rtt), stats['rtt_p99_ms']) and same(q99(lateness), stats['send_lateness_p99_ms'])
        assert same(deadline.mean()*100, stats['planned_deadline20_pct'])
        assert same(called_deadline[emitted].mean()*100 if emitted.any() else None, stats['called_deadline20_pct'])
        assert stats['longest_missing_reply_run'] == missing_run(received)
        assert stats['longest_planned_deadline20_run'] == missing_run(~deadline)
        assert same(gap(arrays['received_ns'][received], seconds), stats['maximum_reply_gap_ms'])
        latest = -1; fresh_times = []; stale = 0
        for sequence, timestamp in sorted(first_replies.items(), key=lambda item: item[1]):
            if sequence > latest:
                latest = sequence; fresh_times.append(timestamp)
            else:
                stale += 1
        assert stale == stats['out_of_order_first_replies']
        assert same(gap(np.asarray(fresh_times, dtype=np.int64), seconds), stats['maximum_increasing_sequence_gap_ms'])
        assert len(row['timeline']) == seconds//10
        for index, window in enumerate(row['timeline']):
            selected = (arrays['planned_ns'] >= index*10e9) & (arrays['planned_ns'] < (index+1)*10e9)
            ok = selected & received
            assert window['start_s'] == index*10 and window['end_s'] == (index+1)*10
            assert window['planned'] == hz*10 and window['send_calls'] == (selected & emitted).sum()
            assert window['replies'] == ok.sum() and window['api_errors'] == (selected & error).sum()
            assert same(deadline[selected].mean()*100, window['planned_deadline20_pct'])
            assert same(q99((arrays['received_ns'][ok]-arrays['sent_ns'][ok])/1e6), window['rtt_p99_ms'])
        radio = row['radio']
        for role, expected_role in [('sender', 2), ('echo', 1)]:
            for phase in ('before', 'after'):
                state = radio[role][phase]
                assert state['version'] == 2 and state['role'] == expected_role and state['paired']
                assert state['primary'] == 6 and state['power_save'] == 0 and state['trace_drops'] == 0
        after = radio['sender']['after']
        assert after['done'] and not after['running'] and after['run_id'] == row['run_id']
        assert (after['planned'], after['hz'], after['seconds']) == (count, hz, seconds)
        assert after['sent_calls'] == len(calls) and after['reply_callbacks'] == len(replies)
        assert after['skipped_schedules'] == len(skipped_indexes) and after['tx_api_errors'] == error.sum()
        before = radio['wifi']['before']; after_wifi = radio['wifi']['after']
        assert before['version'] == after_wifi['version'] == 1 and before['connected'] and before['tcp_connected'] and before['primary'] == 6
        assert same((after_wifi['rx_bytes']-before['rx_bytes'])*8/row['wifi_counter_window_seconds']/1e6, row['wifi_delivered_mbps'])
        requested = 0 if condition['wifi'] == 'off' else 15.72864
        for phase in ('before', 'after'):
            source = row['source'][phase]
            assert source['helper_version'] == 2 and source['run_id'] == row['run_id'] and source['requested_mbps'] == requested
            assert source['pending_application_bytes'] == max(0, source['generated_payload_bytes']-source['sent_payload_bytes'][0])
        assert row['source']['before']['tcp_connected']
        assert row['source']['before']['configuration_generation'] == row['source']['before']['tcp_connection_generation']
        cadence = row['counter_sample_interval_seconds']
        assert cadence == (2 if args.experiment == 'placement' else 10)
        assert len(row['counter_samples']) >= max(1, seconds//cadence-2), 'Periodic Wi-Fi activity observation is incomplete'
        previous_echo = radio['echo']['before']['rx_messages']
        for sample in row['counter_samples']:
            if 'echo' not in sample:
                continue
            echo = sample['echo']
            assert echo['version'] == 2 and echo['role'] == 1 and echo['primary'] == 6 and echo['power_save'] == 0
            assert echo['rx_messages'] >= previous_echo
            assert sample['echo_received_since_previous_sample'] == echo['rx_messages']-previous_echo
            previous_echo = echo['rx_messages']
        successful = [sample for sample in row['counter_samples'] if not sample['read_failed']]
        for sample in successful:
            source = sample['source']
            assert source['helper_version'] == 2 and source['run_id'] == row['run_id'] and source['requested_mbps'] == requested
            assert sample['receiver']['version'] == 1
        spectrum = np.load(target/(file.stem+'-spectrum.npz'))
        assert (row['sdr']['lo_mhz'], row['sdr']['sample_rate_hz'], row['sdr']['bandwidth_mhz'],
                row['sdr']['gain'], row['sdr']['samples'], row['sdr']['fft_length']) == (
            2442, 80000000, 48, 'MANUAL 20', 16380, 1024)
        assert spectrum['power_dbfs'].shape == (row['sdr']['frames'], 1024) and np.isfinite(spectrum['power_dbfs']).all()
        assert row['sdr']['all_crcs_verified']
        if args.experiment == 'long':
            assert '30 cm' in row['layout']['description']
        covered.add((condition['repeat'], hz if args.experiment == 'long' else condition['placement_id'], condition['wifi']))
        groups[file.stem.rsplit('-r', 1)[0]].append((row, rtt, deadline))
        planned_total += count; sent_total += len(calls); received_total += int(received.sum()); frame_total += row['sdr']['frames']
    summary = json.loads((target/'summary.json').read_text())
    for name, trials in groups.items():
        value = summary[name]
        assert value['runs'] == len(trials) and value['planned'] == sum(row['application']['planned'] for row, *_ in trials)
        assert value['send_calls'] == sum(row['application']['send_calls'] for row, *_ in trials)
        assert value['replies'] == sum(row['application']['unique_replies'] for row, *_ in trials)
        assert same(q99(np.concatenate([rtt for _, rtt, _ in trials])), value['pooled_rtt_p99_ms'])
        assert same(np.concatenate([deadline for _, _, deadline in trials]).mean()*100, value['planned_deadline20_pct'])
    expected = manifest['operational'][mode]
    if args.require_declared_scope:
        assert not args.require_complete and not args.require_user_stop
        if args.experiment == 'long' and expected.get('status') == 'stopped_at_user_request':
            args.require_user_stop = True
        else:
            args.require_complete = True
    assert (len(covered), planned_total, sent_total, received_total, frame_total) == (
        expected['trials'], expected['control_planned'], expected['control_send_calls'], expected['control_received'], expected['iq_snapshots_original'])
    matrix = {(repeat, hz, wifi) for repeat in (1, 2, 3) for hz in (20, 50, 100, 200) for wifi in ('off', 'heavy')}
    if args.experiment == 'placement':
        matrix = {(repeat, position, wifi) for repeat in (1, 2, 3) for position in PLACEMENT_IDS for wifi in ('off', 'heavy')}
    if args.require_complete:
        assert covered == matrix and len(summary) == (8 if args.experiment == 'long' else 10)
        assert all(value['runs'] == 3 for value in summary.values())
        if args.experiment == 'placement':
            assert placements['farther']['distances_cm']['sender_echo'] > placements['baseline-before']['distances_cm']['sender_echo']
    if args.require_user_stop:
        assert args.experiment == 'long' and not args.require_complete
        assert expected['status'] == 'stopped_at_user_request' and expected['planned_trials'] == 24
        assert 16 <= expected['trials'] < 24 and covered < matrix
        assert {(repeat, hz, wifi) for repeat in (1, 2) for hz in (20, 50, 100, 200)
                for wifi in ('off', 'heavy')} <= covered
        assert len(summary) == 8 and all(2 <= value['runs'] <= 3 for value in summary.values())
        assert (target/(expected['stop_after_trial']+'.json')).exists()
    print(mode, expected, 'complete_matrix:', covered == matrix)


if __name__ == '__main__':
    main()
