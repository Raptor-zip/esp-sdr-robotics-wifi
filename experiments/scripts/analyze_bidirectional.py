#!/usr/bin/env python3
"""Export new one-hop controls and derive repetition-matched effects."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

import numpy as np

from analyze_long_espnow import summarize_events, public_radio, source_counters
from signal_processing import spectra

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT/'data/coexistence'


def analyze(raw_root, mode, rf=True):
    rows = []
    for path in sorted(raw_root.glob(f'bidirectional-{mode}-*.json')):
        if path.name.endswith('-iq.json'):
            continue
        raw = json.loads(path.read_text()); cx = raw['context']; name = path.stem
        assert raw['sdr_errors'] == [] and cx['wifi_hops'] == 1
        assert cx['seconds'] == raw['seconds'] == 20
        assert cx['requested_mbps'] == (20 if cx['wifi_load'] == 'heavy' else 0)
        for phase in ('before', 'after'):
            state = cx['wifi_'+phase]
            assert state['connected'] and state['tcp_connected'] and state['primary'] == 6 and state['ap_bw'] == 1
        assert 'channel 6 (2437 MHz), width: 20 MHz' in cx['ap_readback']
        assert cx['source_before']['configuration_generation'] == cx['source_before']['tcp_connection_generation']
        assert cx['source_after']['configuration_generation'] == cx['source_before']['configuration_generation']
        assert cx['source_after']['tcp_connected'] and cx['source_after']['sent_payload_bytes'][0] >= cx['source_before']['sent_payload_bytes'][0]
        wifi = np.load(raw_root/(name+'-control.npz'))
        arrays = {key: wifi[key].copy() for key in wifi.files}
        start = int(arrays.pop('host_start_ns'))
        arrays['sent_ns'] -= start; arrays['planned_ns'] -= start
        arrays['received_ns'] = np.where(arrays['received_ns'] > 0, arrays['received_ns']-start, 0)
        np.savez_compressed(TARGET/(name+'-wifi.npz'), **arrays)
        received = arrays['received_ns'] > 0
        rtt = (arrays['received_ns'][received]-arrays['sent_ns'][received])/1e6
        assert int(received.sum()) == raw['received']
        np.testing.assert_allclose(np.percentile(rtt,99),raw['rtt_ms']['p99'])
        deadline = ~received | (arrays['received_ns']-arrays['sent_ns'] > 20_000_000)
        np.testing.assert_allclose(deadline.mean()*100,raw['missed_deadline_pct']['20'])
        goodput = cx['wifi_after']['bench_rx_bytes']*8/raw['seconds']/1e6
        np.testing.assert_allclose(goodput,raw['wifi_goodput_mbps'])
        row = dict(name=name, run_id=raw['run_id'], seconds=raw['seconds'], mode=mode,
            condition={key: cx[key] for key in ('repeat','wifi_load','radio','radio_channel','wifi_channel','wifi_width_mhz','wifi_hops','requested_mbps','period_ms')},
            placement=cx['placement'], wifi=dict(goodput_mbps=goodput,
                rtt_p99_ms=raw['rtt_ms']['p99'], deadline20_pct=raw['missed_deadline_pct']['20'],
                sent=raw['sent'], received=raw['received'], loss_pct=raw['loss_pct'],
                benchmark_rx_bytes=cx['wifi_after']['bench_rx_bytes']),
            radio={key: {phase: public_radio(cx[key+'_'+phase]) for phase in ('before','after')}
                   for key in ('sender','echo','wifi')},
            source={phase: source_counters(cx['source_'+phase]) for phase in ('before','after')},
            wifi_uart_crc_verified=True,
            semantics='Separate one-hop cohort; AP PC->ESP32 TCP plus 100 Hz UDP echo; fixed 20 s receiver counter. Radio stop means no intentional external-pair transmission, not a shielded RF environment.')
        confirmation = raw_root.parent/'evidence/bidirectional-placement.json'
        if confirmation.exists():
            confirmed = json.loads(confirmation.read_text())
            assert all(cx['placement'][k] == confirmed[k] for k in ('pair_cm','c5_sender_cm','c5_echo_cm'))
            row['placement'] = {k:v for k,v in confirmed.items() if k != 'confirmation_utc'}
        if mode == 'espnow' and cx['radio']:
            trace = np.load(raw_root/(name+'-events.npz')); events = trace['events']
            assert raw['uart']['all_crcs_verified']
            assert len(events) == trace['block_event_counts'].sum()
            assert events[-1,0] == 4 and events[-1,3] == raw['run_id']
            control, stats, timeline = summarize_events(events, cx['radio'], raw['seconds'])
            after = cx['sender_after']
            assert after['done'] and not after['running'] and after['trace_drops'] == 0
            assert stats['send_calls'] == after['sent_calls'] and stats['reply_callbacks'] == after['reply_callbacks']
            assert stats['unsent_planned'] == after['skipped_schedules']
            assert cx['sender_before']['primary'] == cx['echo_before']['primary'] == cx['radio_channel']
            np.savez_compressed(TARGET/(name+'-espnow.npz'), **control)
            np.savez_compressed(TARGET/(name+'-events.npz'), events=events,
                block_received_ns=trace['block_received_ns'], block_event_counts=trace['block_event_counts'])
            row.update(espnow=stats, timeline=timeline,
                uart=dict(all_crcs_verified=True, blocks=len(trace['block_event_counts']), event_count=len(events)),
                wifi_minus_espnow_start_ms=(cx['wifi_benchmark_host_start_ns']-raw['uart']['host_start_ns'])/1e6)
        elif mode == 'espnow':
            assert cx['sender_before']['role'] == cx['echo_before']['role'] == 0
        else:
            before, after = cx['sender_before'], cx['sender_after']
            window = (cx['after_ns']-cx['before_ns'])/1e9
            row['ble'] = dict(received_bytes=after['rx_bytes']-before['rx_bytes'],
                received_notifications=after['rx_messages']-before['rx_messages'],
                decoded_advertisements=after['advertisements']-before['advertisements'],
                counter_window_seconds=window,
                goodput_mbps=(after['rx_bytes']-before['rx_bytes'])*8/window/1e6)
            if cx['radio'] == 'data':
                assert before['connected'] and after['connected'] and cx['echo_before']['subscribed']
                assert before['mtu'] >= 247
            elif cx['radio'] == 'off':
                assert before['role'] == cx['echo_before']['role'] == 0
        meta = json.loads((raw_root/(name+'-iq.json')).read_text())
        assert meta['all_crcs_verified'] and (meta['lo_mhz'],meta['samples'],meta['sample_rate_hz'],meta['bandwidth_mhz'],meta['gain']) == (2442,16380,80000000,48,'MANUAL 20')
        row['sdr'] = {key: meta[key] for key in ('lo_mhz','samples','sample_rate_hz','bandwidth_mhz','gain','frames','all_crcs_verified')}
        if rf:
            iq = np.load(raw_root/(name+'-iq.npz'))['iq']
            assert iq.shape == (meta['frames'],16380,2)
            frequency, power = spectra(iq,80000000,1024)
            starts = np.array([t['host_start_monotonic'] for t in meta['timing']])
            ends = np.array([t['host_end_monotonic'] for t in meta['timing']])
            np.savez_compressed(TARGET/(name+'-spectrum.npz'), frequency_mhz=frequency/1e6+2442,
                power_dbfs=(10*np.log10(np.maximum(power,1e-16))).astype(np.float32),
                capture_start_s=starts-start/1e9,capture_end_s=ends-start/1e9)
            row['sdr']['observation_pct'] = len(iq)*16380/80000000/(ends[-1]-starts[0])*100
        else:
            # Numerical preview must not overwrite an exported RF row.
            existing = TARGET/(name+'.json')
            if existing.exists():
                row['sdr'] = json.loads(existing.read_text())['sdr']
        (TARGET/(name+'.json')).write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n')
        rows.append(row)
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['name'].rsplit('-r',1)[0]].append(row)
    controls = {(r['condition']['repeat'],r['condition']['wifi_load']):r for r in rows
                if r['condition']['radio'] == (0 if mode == 'espnow' else 'off')}
    summaries = {}
    for name, values in grouped.items():
        effects = []
        for row in values:
            condition = row['condition']
            reference = controls.get((condition['repeat'],condition['wifi_load']))
            if condition['wifi_load'] == 'heavy' and reference:
                baseline = reference['wifi']['goodput_mbps']
                assert baseline > 0
                effects.append(100*(1-row['wifi']['goodput_mbps']/baseline))
        summary = dict(condition={k:v for k,v in values[0]['condition'].items() if k != 'repeat'},
            runs=len(values), repetitions=[r['condition']['repeat'] for r in values],
            wifi_goodput_mbps=[r['wifi']['goodput_mbps'] for r in values],
            wifi_p99_ms=[r['wifi']['rtt_p99_ms'] for r in values],
            wifi_deadline20_pct=[r['wifi']['deadline20_pct'] for r in values],
            matched_wifi_reduction_pct=effects,
            matched_wifi_reduction_mean_pct=float(np.mean(effects)) if effects else None)
        if mode == 'espnow' and values[0]['condition']['radio']:
            summary['espnow'] = [r['espnow'] for r in values]
        elif mode == 'ble':
            summary['ble_goodput_mbps'] = [r['ble']['goodput_mbps'] for r in values]
            summary['advertisements'] = [r['ble']['decoded_advertisements'] for r in values]
        summaries[name] = summary
    (TARGET/(mode+'-summary.json')).write_text(json.dumps(summaries,ensure_ascii=False,indent=2)+'\n')
    return rows, summaries


def main():
    parser = argparse.ArgumentParser();parser.add_argument('--raw',type=Path,default=Path.home()/'.local/share/esp-sdr/two-team/raw')
    parser.add_argument('--mode',choices=('espnow','ble','all'),default='all')
    parser.add_argument('--preview',action='store_true');parser.add_argument('--no-rf',action='store_true')
    args=parser.parse_args();TARGET.mkdir(parents=True,exist_ok=True)
    total=[]
    for mode in (('espnow','ble') if args.mode=='all' else (args.mode,)):
        rows, summaries=analyze(args.raw,mode,rf=not args.no_rf)
        if not args.preview:
            expected=42 if mode=='espnow' else 18
            assert len(rows)==expected and all(v['runs']==3 for v in summaries.values()),(mode,len(rows))
        total.extend(rows)
        print(mode,len(rows),'trials')
        for name,value in summaries.items():
            if value['condition']['wifi_load']=='heavy':
                print(name,'Mbps',np.round(value['wifi_goodput_mbps'],3).tolist(),'reduction %',np.round(value['matched_wifi_reduction_pct'],1).tolist())
    if args.preview:
        return
    path=ROOT/'data/manifest.json';manifest=json.loads(path.read_text())
    all_rows=[json.loads(p.read_text()) for p in TARGET.glob('bidirectional-*.json')]
    manifest['coexistence']=dict(trials=len(all_rows),wifi_control_sent=sum(r['wifi']['sent'] for r in all_rows),
        wifi_control_received=sum(r['wifi']['received'] for r in all_rows),
        espnow_control_planned=sum(r.get('espnow',{}).get('planned',0) for r in all_rows),
        espnow_control_received=sum(r.get('espnow',{}).get('unique_replies',0) for r in all_rows),
        iq_snapshots_original=sum(r['sdr']['frames'] for r in all_rows),
        wifi_hops=1,status='complete' if len(all_rows)==60 else 'in_progress')
    for file in TARGET.iterdir():
        manifest['files'][str(file.relative_to(ROOT/'data'))]=hashlib.sha256(file.read_bytes()).hexdigest()
    path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(manifest['coexistence'])


if __name__=='__main__':
    main()
