#!/usr/bin/env python3
"""Continuous 10-minute ESP-NOW matrix; run only after ROS 2 and PS trials.

Requires espnow-stream v2 on the owned pair, the team-controller v1 on
the third ESP32, and operational_traffic helper v2 on the robot laptop.
The UART stream measures the complete application timeline. C5 RF capture
remains intermittent and must not be interpreted as complete RF coverage.
"""
import argparse
import fcntl
import json
from pathlib import Path
import random
import secrets
import subprocess
import sys
import threading
import time

import numpy as np

from board import Board
from espnow_stream import collect
from run_two_team import ROOT, api, capture
from timed_capture import TimedReceiver
from placement_conditions import load_placement


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--pilot', action='store_true')
    parser.add_argument('--repeat', type=int, choices=[1, 2, 3],
                        help='Acquire one complete 8-trial repetition per bounded helper session')
    parser.add_argument('--placement', type=Path,
                        help='Private, confirmed physical placement input; run only after the long fixed-layout matrix')
    parser.add_argument('--seconds', type=int); args = parser.parse_args()
    placement = load_placement(args.placement) if args.placement else None
    if args.seconds is None:
        args.seconds = 10 if placement else 600
    if placement:
        assert args.seconds == 10 and not args.pilot
    else:
        assert args.seconds in (600, 1200) or args.pilot and 1 <= args.seconds <= 30
    scripts = Path(__file__).resolve().parents[1]
    for experiment in ('qos', 'power'):
        subprocess.run([sys.executable, str(scripts/'check_ros2.py'), '--experiment', experiment,
                        '--require-complete'], check=True)
    if placement:
        public_manifest = json.loads((scripts.parents[0]/'data/manifest.json').read_text())
        gate = '--require-user-stop' if public_manifest['operational']['espnow-long'].get('status') == 'stopped_at_user_request' else '--require-complete'
        subprocess.run([sys.executable, str(scripts/'check_long_espnow.py'), gate], check=True)
    lock = (ROOT/'evidence/acquisition.lock').open('w'); fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    session_id = 'espnow-long-'+secrets.token_hex(4)
    cases = []
    for repeat in ((args.repeat,) if args.repeat is not None else (1, 2, 3)):
        group = [(repeat, hz, wifi) for hz in ((100,) if placement else (20, 50, 100, 200)) for wifi in ('off', 'heavy')]
        random.Random(19000+repeat).shuffle(group); cases.extend(group)
    if args.pilot:
        cases = [(1, 200, 'heavy')]
    boards = []; receiver = None; sdr_thread = counter_thread = None
    stop_sdr = threading.Event(); stop_counters = threading.Event()
    try:
        for port, baud in [('/dev/ttyUSB0', 115200), ('/dev/ttyUSB1', 115200), ('/dev/ttyUSB2', 460800)]:
            boards.append(Board(port, baud))
        sender, echo, wifi_receiver = boards
        sender_state = sender.state(); echo_state = echo.state(); wifi_state = wifi_receiver.state()
        assert sender_state['version'] == echo_state['version'] == 2
        assert wifi_state['version'] == 1 and wifi_state['connected'], 'Cold-start the original team-controller after the preceding STOP'
        sender.command('STOP'); echo.command('STOP')
        sender.command('CHANNEL 6'); echo.command('CHANNEL 6')
        sender.command('PEER '+echo_state['mac']); echo.command('PEER '+sender_state['mac'])
        receiver = TimedReceiver('/dev/ttyACM0')
        for repeat, hz, wifi in cases:
            name = f'{"pilot-" if args.pilot else ""}op-espnow-long-hz{hz}-wifi{wifi}-ch6-r{repeat}'
            if placement:
                name = f'op-placement-{placement["id"]}-wifi{wifi}-ch6-r{repeat}'
            out = ROOT/'raw'/name
            if out.with_suffix('.json').exists():
                existing = json.loads(out.with_suffix('.json').read_text())
                assert existing['seconds'] == args.seconds
                if placement:
                    assert existing['context']['placement'] == placement, 'Keep recorded results; do not silently replace a placement'
                print('KEEP', name, flush=True); continue
            print('START', name, flush=True)
            sender.command('ROLE 2'); echo.command('ROLE 1')
            run_id = secrets.randbelow(2_000_000_000)+1
            configured = api('/configure', dict(run_id=run_id, level=wifi, seconds=args.seconds+45))
            time.sleep(3)
            deadline = time.monotonic()+30
            while time.monotonic() < deadline:
                source = api(); destination = wifi_receiver.state()
                if source['helper_version'] == 2 and source['tcp_connected'] and destination['connected'] and destination['tcp_connected'] and source['configuration_generation'] == source['tcp_connection_generation']:
                    break
                time.sleep(.4)
            else:
                raise RuntimeError('External Wi-Fi current TCP connection was not established before the long trial')
            context = dict(repeat=repeat, hz=hz, wifi=wifi, espnow_channel=6, wifi_channel=6,
                acquisition_session_id=session_id, counter_sample_interval_seconds=2 if placement else 10,
                wifi_width_mhz=20, configured_source=configured, source_before=source, wifi_before=destination,
                sender_before=sender.state(), echo_before=echo.state(),
                before_ns=time.monotonic_ns(), wall_before_ns=time.time_ns(),
                layout=dict(description='All boards and PCs on one desk, approximately 30 cm spacing, fixed throughout this series; exact pair distances and orientations not measured',
                            source='user report', moving_people='negligible influence reported by user'))
            if placement:
                context['placement'] = placement
                context['layout'] = dict(source='user report', placement=placement,
                    description='Manually applied physical placement; measured board/case-centre distances in cm; Wi-Fi devices, sender and C5 fixed; not the unmeasured approximately 30 cm layout',
                    moving_people='intentional reported obstruction' if placement['id'] == 'obstructed' else 'no intentional obstruction')
            assert context['sender_before']['primary'] == context['echo_before']['primary'] == destination['primary'] == 6
            assert context['sender_before']['power_save'] == context['echo_before']['power_save'] == 0
            errors = []; counter_samples = []; stop_sdr.clear(); stop_counters.clear()
            def record_sdr():
                try:
                    capture(receiver, out, args.seconds, 2442, stop_event=stop_sdr)
                except BaseException as error:
                    errors.append(repr(error))
            def sample_counters():
                last_echo_messages = context['echo_before']['rx_messages']
                while not stop_counters.is_set():
                    sample = dict(host_ns=time.monotonic_ns())
                    try:
                        # This uses the echo board's separate UART. Never send
                        # STATUS to the probe while its binary trace is active.
                        sample['echo'] = echo.state()
                        current = sample['echo']['rx_messages']
                        sample['echo_received_since_previous_sample'] = current-last_echo_messages
                        last_echo_messages = current
                        sample['receiver'] = wifi_receiver.state()
                        sample['source'] = api()
                    except Exception as error:
                        sample['error'] = repr(error)
                    counter_samples.append(sample)
                    stop_counters.wait(context['counter_sample_interval_seconds'])
            sdr_thread = threading.Thread(target=record_sdr); sdr_thread.start()
            counter_thread = threading.Thread(target=sample_counters); counter_thread.start()
            trace = collect(sender, run_id, hz, args.seconds)
            np.savez_compressed(str(out)+'-events.npz', events=trace['events'],
                                block_received_ns=trace['block_received_ns'], block_event_counts=trace['block_event_counts'])
            # Preserve the measured events and pre-window evidence even if
            # post-window compression or monitoring shutdown is too slow.
            checkpoints = ROOT/'evidence/long-checkpoints'; checkpoints.mkdir(exist_ok=True)
            checkpoint = checkpoints/f'{name}-run-{run_id}.json'
            checkpoint.write_text(json.dumps(dict(run_id=run_id, seconds=args.seconds,
                context=context, counter_samples_at_checkpoint=list(counter_samples),
                uart={key:value for key,value in trace.items()
                      if key not in ('events','block_received_ns','block_event_counts')},
                complete=False, reason='Post-window workers have not yet been joined'),indent=2)+'\n')
            stop_counters.set(); counter_thread.join(timeout=45)
            # 600-second I/Q archives need more than the former short-trial
            # 15-second compression allowance. This changes only host storage
            # waiting after the same bounded RF and application windows.
            storage_wait_start=time.monotonic(); sdr_thread.join(timeout=120)
            context['sdr_storage_wait_seconds']=time.monotonic()-storage_wait_start
            if counter_thread.is_alive() or sdr_thread.is_alive() or errors:
                failure=dict(counter_thread_alive=counter_thread.is_alive(),
                    sdr_thread_alive=sdr_thread.is_alive(), errors=errors,
                    counter_samples=list(counter_samples))
                checkpoint.write_text(json.dumps(dict(run_id=run_id,seconds=args.seconds,
                    context=context,complete=False,failure=failure),indent=2)+'\n')
                raise RuntimeError('Long acquisition worker failed: '+repr(
                    {key:value for key,value in failure.items() if key != 'counter_samples'}))
            context.update(sender_after=sender.state(), echo_after=echo.state(),
                           wifi_after=wifi_receiver.state(), source_after=api(), counter_samples=counter_samples,
                           after_ns=time.monotonic_ns(), wall_after_ns=time.time_ns())
            assert context['sender_after']['done'] and not context['sender_after']['running']
            assert context['sender_after']['trace_drops'] == 0, 'Dropped UART telemetry cannot be called RF loss'
            events = trace.pop('events'); block_timing = trace.pop('block_received_ns'); block_counts = trace.pop('block_event_counts')
            assert (events[:, 0] == 1).sum() == context['sender_after']['sent_calls']
            assert (events[:, 0] == 2).sum() == context['sender_after']['reply_callbacks']
            assert events[events[:, 0] == 3, 3].sum() == context['sender_after']['skipped_schedules']
            result = dict(run_id=run_id, seconds=args.seconds, context=context, uart=trace,
                          sdr_errors=errors, semantics='Continuous ESP-NOW application echo; separate Wi-Fi TCP traffic requested; AP beacons and telemetry remain in Wi-Fi idle. MAC results are aggregates. RF sampling is intermittent.')
            temporary = out.with_suffix('.json.tmp'); temporary.write_text(json.dumps(result, indent=2)+'\n'); temporary.replace(out.with_suffix('.json'))
            checkpoint.unlink()
            api('/configure', dict(run_id=0, level='off', seconds=0))
            sender.command('STOP'); echo.command('STOP')
            print('RESULT', name, 'planned', hz*args.seconds, 'send_calls', context['sender_after']['sent_calls'],
                  'reply_callbacks', context['sender_after']['reply_callbacks'], 'CRC', True, flush=True)
    finally:
        stop_sdr.set(); stop_counters.set()
        for thread in (counter_thread, sdr_thread):
            if thread is not None and thread.is_alive():
                thread.join(timeout=30)
        try:
            api('/configure', dict(run_id=0, level='off', seconds=0))
        except Exception:
            pass
        for board in boards:
            try:
                board.command('STOP'); board.close()
            except Exception:
                pass
        if receiver:
            try:
                receiver.command('FREQ 2412'); receiver.command('BANDWIDTH 0'); receiver.command('GAIN HARDWARE'); receiver.close()
            except Exception:
                pass


if __name__ == '__main__':
    main()
