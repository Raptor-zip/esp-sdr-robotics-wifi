#!/usr/bin/env python3
"""Paired short coexistence trials with radio-off controls and reversible AP.

Unlike earlier laptop->AP->ESP32 tests, bulk travels AP PC->ESP32 (one
wireless hop). ESP-NOW and BLE use a separate pair. Keep cohorts separate.
"""
import argparse
import fcntl
import json
import os
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
from operational_traffic import PacedTraffic, OperationalHandler
from http.server import ThreadingHTTPServer
from run_two_team import ROOT, api, capture, measure_controller
from timed_capture import TimedReceiver


def nm(*args, check=True):
    return subprocess.run(['nmcli', *args], text=True, capture_output=True,
                          timeout=45, check=check)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('espnow', 'ble'))
    parser.add_argument('--pilot', action='store_true')
    parser.add_argument('--seconds', type=int, default=20)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--placement', type=Path)
    parser.add_argument('--tcp-brackets', action='store_true',
                        help='TCP-only before/on/after windows sharing one connection; separate cohort')
    args = parser.parse_args()
    assert 5 <= args.seconds <= 30 and 1 <= args.repeats <= 5
    lock = (ROOT/'evidence/acquisition.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    profile = 'sdr-bidirectional-ap'; interface = 'wlp132s0f0'
    active = nm('-t', '-f', 'NAME,DEVICE', 'con', 'show', '--active').stdout.splitlines()
    original = next(line.rsplit(':', 1)[0] for line in active if line.rsplit(':', 1)[1] == interface)
    placement = json.loads(args.placement.read_text()) if args.placement else {'source': 'previous user-confirmed placement; confirmation pending', 'pair_cm': 75, 'c5_sender_cm': 45, 'c5_echo_cm': 95}
    boards = []; receiver = node = server = None; workers = []
    cases = []
    for rep in range(1, args.repeats+1):
        states = [(0, 6)] + [(hz, ch) for hz in (100, 200) for ch in (6, 7, 11)] if args.mode == 'espnow' else [('off', 6), ('advert', 6), ('data', 6)]
        group = [(rep, load, hz, channel) for load in ('off', 'heavy') for hz, channel in states]
        random.Random(28000+rep+(100 if args.mode == 'ble' else 0)).shuffle(group)
        cases.extend(group)
    if args.pilot:
        cases = [(1, 'heavy', state, 6) for state in ((0, 100) if args.mode == 'espnow' else ('off', 'data'))]
    if args.tcp_brackets:
        assert args.mode == 'espnow' and not args.pilot
        cases = []
        for rep in range(1, args.repeats+1):
            channels = [6, 7, 11]; random.Random(31000+rep).shuffle(channels)
            for ch in channels:
                cases.extend((rep, 'heavy', hz, ch) for hz in (0, 200, 0))
    try:
        nm('con', 'delete', profile, check=False)
        nm('con', 'add', 'type', 'wifi', 'ifname', interface, 'con-name', profile,
           'ssid', 'ESP-SDR-TEAM-A', '802-11-wireless.mode', 'ap',
           '802-11-wireless.band', 'bg', '802-11-wireless.channel', '6',
           '802-11-wireless.powersave', '2', 'wifi-sec.key-mgmt', 'wpa-psk',
           'wifi-sec.psk', 'SdrLab2026TestOnly', 'ipv4.method', 'manual',
           'ipv4.addresses', '192.168.8.20/24', 'ipv4.never-default', 'yes',
           'ipv6.method', 'disabled', 'connection.autoconnect', 'no')
        nm('con', 'up', profile)
        route = subprocess.run(['ip', 'route', 'get', '1.1.1.1'], capture_output=True, text=True, check=True).stdout
        assert 'enp134s0' in route, 'Preserve wired Internet route'
        node = PacedTraffic('192.168.8.20')
        server = ThreadingHTTPServer(('192.168.8.20', 8134), OperationalHandler)
        server.daemon_threads = True; server.node = node
        server.token = (ROOT/'evidence/http-token').read_text().strip()
        for fn in (node.echo, node.sender, server.serve_forever):
            threading.Thread(target=fn, daemon=True).start()
        for port, baud in [('/dev/ttyUSB0', 115200), ('/dev/ttyUSB1', 115200), ('/dev/ttyUSB2', 460800)]:
            boards.append(Board(port, baud))
        sender, echo, wifi = boards
        # STOP on this existing Wi-Fi firmware cannot be undone by a UART
        # command; its reset pin must be pulsed once to restart the STA.
        if not wifi.state()['connected']:
            wifi.port.dtr = False; wifi.port.rts = True; time.sleep(.12)
            wifi.port.rts = False; time.sleep(2); wifi.port.reset_input_buffer()
        if args.mode == 'espnow':
            sender.command('STOP'); echo.command('STOP')
            ss = sender.state(); es = echo.state()
            assert ss['version'] == es['version'] == 2
            sender.command('PEER '+es['mac']); echo.command('PEER '+ss['mac'])
        receiver = TimedReceiver('/dev/ttyACM0')
        deadline = time.monotonic()+35
        while time.monotonic() < deadline:
            s = wifi.state()
            if s['connected'] and s['tcp_connected']:
                assert s['primary'] == 6 and s['ap_bw'] == 1
                break
            time.sleep(.3)
        else:
            raise RuntimeError('One-hop Wi-Fi receiver did not associate/connect')
        for case_index, (rep, load, radio, channel) in enumerate(cases):
            tag = f'hz{radio}-ch{channel}' if args.mode == 'espnow' else str(radio)
            name = f'{"pilot-" if args.pilot else ""}bidirectional-{args.mode}-wifi{load}-{tag}-r{rep}'
            phase = ('before', 'on', 'after')[case_index % 3] if args.tcp_brackets else None
            if args.tcp_brackets:
                name = f'tcpbracket-espnow-ch{channel}-{phase}-r{rep}'
            out = ROOT/'raw'/name
            if out.with_suffix('.json').exists():
                print('KEEP', name, flush=True); continue
            print('START', name, flush=True)
            if args.mode == 'espnow':
                sender.command('STOP'); echo.command('STOP')
                sender.command(f'CHANNEL {channel}'); echo.command(f'CHANNEL {channel}')
                sender.command('ROLE 2' if radio else 'ROLE 0')
                echo.command('ROLE 1' if radio else 'ROLE 0')
            else:
                sender.command('ROLE 0'); echo.command('ROLE 0'); time.sleep(.3)
                if radio == 'advert':
                    echo.command('ROLE 3'); sender.command('ROLE 4')
                elif radio == 'data':
                    echo.command('ROLE 1'); sender.command('ROLE 2')
                    deadline = time.monotonic()+25
                    while time.monotonic() < deadline:
                        ss = sender.state(); es = echo.state()
                        if ss['connected'] and es['connected'] and es['mtu'] >= 247:
                            break
                        time.sleep(.3)
                    else:
                        raise RuntimeError('BLE connected data / MTU setup failed')
                    sender.command(f'SUB {es["value_handle"]}'); time.sleep(.3)
                    assert echo.state()['subscribed']
            run_id = secrets.randbelow(2_000_000_000)+1
            if not args.tcp_brackets or phase == 'before':
                api('/configure', dict(run_id=run_id, level=load,
                    seconds=args.seconds*3+40 if args.tcp_brackets else args.seconds+12,
                    requested_mbps=20 if load == 'heavy' else 0, period_ms=10))
            deadline = time.monotonic()+15
            while time.monotonic() < deadline:
                source = api(); destination = wifi.state()
                if destination['tcp_connected'] and source['tcp_connected'] and source['configuration_generation'] == source['tcp_connection_generation']:
                    break
                time.sleep(.2)
            else:
                raise RuntimeError('Fresh TCP connection not established')
            time.sleep(5 if args.tcp_brackets and phase == 'before' else 2)
            if args.mode == 'ble' and radio == 'data':
                echo.command(f'LOAD 2 {args.seconds+8}')
            cx = dict(repeat=rep, wifi_load=load, radio=radio, radio_channel=channel,
                      wifi_channel=6, wifi_width_mhz=20, seconds=args.seconds,
                      wifi_hops=1, wifi_source='AP PC', wifi_destination='independent ESP32',
                      requested_mbps=20 if load == 'heavy' else 0, period_ms=10,
                      placement=placement,
                      ap_readback=subprocess.run(['iw', 'dev', interface, 'info'], capture_output=True, text=True, check=True).stdout,
                      sender_before=sender.state(), echo_before=echo.state(),
                      wifi_before=wifi.state(), source_before=api(),
                      before_ns=time.monotonic_ns())
            if args.tcp_brackets:
                cx['tcp_phase'] = phase
                cx['wifi_control_hz'] = 0
            errors = []; traces = []; anchors = []
            def record_sdr():
                try:
                    capture(receiver, out, args.seconds, 2442)
                except BaseException as error:
                    errors.append(repr(error))
            def record_espnow():
                try:
                    traces.append(collect(sender, run_id, radio, args.seconds))
                except BaseException as error:
                    errors.append(repr(error))
            workers = [threading.Thread(target=record_sdr)]
            if args.mode == 'espnow' and radio:
                workers.append(threading.Thread(target=record_espnow))
            for thread in workers:
                thread.start()
            if args.tcp_brackets:
                counter_before_start = time.monotonic_ns(); counter_before = wifi.state()
                counter_begin = time.monotonic_ns()
                time.sleep(args.seconds)
                counter_after_start = time.monotonic_ns(); counter_after = wifi.state()
                counter_end = time.monotonic_ns()
                elapsed = (counter_end-counter_begin)/1e9
                cx['tcp_measurement'] = dict(before=counter_before, after=counter_after,
                    before_start_ns=counter_before_start, before_end_ns=counter_begin,
                    after_start_ns=counter_after_start, after_end_ns=counter_end,
                    seconds=elapsed, read_uncertainty_ms=((counter_begin-counter_before_start)+(counter_end-counter_after_start))/1e6)
                result = dict(run_id=run_id, seconds=args.seconds,
                    delivered_payload_mbps=[(counter_after['rx_bytes']-counter_before['rx_bytes'])*8/elapsed/1e6, 0],
                    rtt_ms={'p99': None}, missed_deadline_pct={'20': None},
                    sent=0, received=0, loss_pct=None)
                raw = dict(host_start_ns=counter_begin)
            else:
                result, raw = measure_controller(wifi, run_id, args.seconds)
            # The firmware accumulates bulk bytes only during its actual
            # fixed-duration BENCH window, excluding warm-up and UART dumps.
            result['wifi_goodput_mbps'] = result['delivered_payload_mbps'][0]
            cx['wifi_benchmark_host_start_ns'] = int(raw['host_start_ns'])
            for thread in workers:
                thread.join(timeout=90)
            assert not any(thread.is_alive() for thread in workers)
            if errors:
                raise RuntimeError('Recording failure: '+str(errors))
            cx.update(sender_after=sender.state(), echo_after=echo.state(),
                      wifi_after=wifi.state(), source_after=api(), after_ns=time.monotonic_ns())
            assert cx['wifi_after']['primary'] == 6 and cx['wifi_after']['ap_bw'] == 1 and cx['wifi_after']['tcp_connected']
            if traces:
                trace = traces[0]
                np.savez_compressed(str(out)+'-events.npz', events=trace['events'],
                    block_received_ns=trace['block_received_ns'], block_event_counts=trace['block_event_counts'])
                assert cx['sender_after']['trace_drops'] == 0
                result['uart'] = {k: v for k, v in trace.items() if not isinstance(v, np.ndarray)}
            result.update(mode=args.mode, context=cx, sdr_errors=errors,
                          semantics='One-hop AP PC to independent ESP32 TCP plus 100 Hz UDP echo; external ESP-NOW or BLE pair; fixed benchmark-window byte counter; radio-off controls; intermittent uncalibrated C5 RF.')
            np.savez_compressed(str(out)+'-control.npz', **raw)
            temp = out.with_suffix('.json.tmp'); temp.write_text(json.dumps(result, indent=2)+'\n'); temp.replace(out.with_suffix('.json'))
            if not args.tcp_brackets or phase == 'after':
                api('/configure', dict(run_id=0, level='off', seconds=0))
            sender.command('STOP' if args.mode == 'espnow' else 'ROLE 0')
            echo.command('STOP' if args.mode == 'espnow' else 'ROLE 0')
            print('RESULT', name, 'WiFi Mbps', result['wifi_goodput_mbps'],
                  'WiFi p99', result['rtt_ms']['p99'], 'WiFi deadline20', result['missed_deadline_pct']['20'], flush=True)
    finally:
        for thread in workers:
            if thread.is_alive():
                thread.join(timeout=args.seconds+20)
        if node:
            node.stop.set()
        if server:
            server.shutdown(); server.server_close()
        for index, board in enumerate(boards):
            try:
                board.command('ROLE 0' if args.mode == 'ble' and index < 2 else 'STOP'); board.close()
            except Exception:
                pass
        if receiver:
            try:
                receiver.command('FREQ 2412'); receiver.command('BANDWIDTH 0')
                receiver.command('GAIN HARDWARE'); receiver.close()
            except Exception:
                pass
        nm('con', 'down', profile, check=False)
        restored = nm('con', 'up', original, check=False)
        nm('con', 'delete', profile, check=False)
        if restored.returncode:
            raise RuntimeError('Original Wi-Fi restore failed: '+restored.stderr)
        print('RESTORED ORIGINAL WIFI; WIRED INTERNET RETAINED', flush=True)


if __name__ == '__main__':
    main()
