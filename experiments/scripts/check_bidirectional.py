#!/usr/bin/env python3
"""Independent complete-matrix, timeline, byte-counter and reference audit."""
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/coexistence'


def app_check(row,name):
    trace=np.load(DATA/(name+'-events.npz'));events=trace['events']
    a=np.load(DATA/(name+'-espnow.npz'));stats=row['espnow']
    received=a['received_ns']>=0;called=a['sent_ns']>=0
    assert received.sum()==stats['unique_replies'] and called.sum()==stats['send_calls']
    calls=events[events[:,0]==1];replies=events[events[:,0]==2];end=events[events[:,0]==4]
    assert len(calls)==called.sum() and len(np.unique(calls[:,1]))==len(calls)
    assert len(end)==1 and events[-1,0]==4 and end[0,1]==len(received) and end[0,3]==row['run_id']
    assert np.array_equal(a['sent_ns'][calls[:,1]],calls[:,2].astype(np.int64)*1000)
    first={}
    for _,seq,t,s in replies:
        assert a['sent_ns'][seq]==int(s)*1000 and t>=s
        first.setdefault(int(seq),int(t)*1000)
    assert set(first)==set(np.flatnonzero(received))
    assert all(int(a['received_ns'][seq])==t for seq,t in first.items())
    skipped=[]
    for _,seq,_,count in events[events[:,0]==3]:
        skipped.extend(range(int(seq),int(seq)+int(count)))
    assert set(skipped)==set(np.flatnonzero(~called)) and len(skipped)==len(set(skipped))
    np.testing.assert_allclose(np.percentile((a['received_ns'][received]-a['sent_ns'][received])/1e6,99),stats['rtt_p99_ms'])
    d=~received | (a['received_ns']-a['planned_ns']>20_000_000)
    np.testing.assert_allclose(d.mean()*100,stats['planned_deadline20_pct'])
    assert trace['block_event_counts'].sum()==len(events)


def main():
    manifest=json.loads((ROOT/'data/manifest.json').read_text())
    for file,digest in manifest['files'].items():
        if file.startswith('coexistence/'):
            assert hashlib.sha256((ROOT/'data'/file).read_bytes()).hexdigest()==digest,file
    for mode,expected in [('espnow',42),('ble',18)]:
        paths=sorted(DATA.glob(f'bidirectional-{mode}-*.json'))
        assert len(paths)==expected
        observed=set();rows={}
        for path in paths:
            row=json.loads(path.read_text());c=row['condition'];rows[path.stem]=row
            observed.add((c['repeat'],c['wifi_load'],c['radio'],c['radio_channel']))
            assert row['seconds']==20 and c['wifi_hops']==1 and row['wifi_uart_crc_verified']
            assert row['sdr']['all_crcs_verified'] and row['sdr']['frames']>0
            assert row['placement']['pair_cm']==75 and row['placement']['c5_sender_cm']==45 and row['placement']['c5_echo_cm']==95
            with np.load(DATA/(path.stem+'-wifi.npz')) as z:
                sent=z['sent_ns'];received=z['received_ns'];valid=received>0
                assert len(sent)==row['wifi']['sent']==2000 and valid.sum()==row['wifi']['received']
                rtt=(received[valid]-sent[valid])/1e6
                np.testing.assert_allclose(np.percentile(rtt,99),row['wifi']['rtt_p99_ms'])
                np.testing.assert_allclose((~valid | (received-sent>20_000_000)).mean()*100,row['wifi']['deadline20_pct'])
            np.testing.assert_allclose(row['wifi']['benchmark_rx_bytes']*8/20/1e6,row['wifi']['goodput_mbps'])
            if 'espnow' in row:
                app_check(row,path.stem)
            if mode=='ble':
                a=row['radio']['sender']['after'];b=row['radio']['sender']['before'];ble=row['ble']
                assert ble['received_bytes']==a['rx_bytes']-b['rx_bytes']
                np.testing.assert_allclose(ble['received_bytes']*8/ble['counter_window_seconds']/1e6,ble['goodput_mbps'])
            with np.load(DATA/(path.stem+'-spectrum.npz')) as z:
                assert z['power_dbfs'].shape==(row['sdr']['frames'],1024) and np.isfinite(z['power_dbfs']).all()
        states=[(0,6)]+[(hz,ch) for hz in (100,200) for ch in (6,7,11)] if mode=='espnow' else [(state,6) for state in ('off','advert','data')]
        assert observed=={(rep,load,state,ch) for rep in (1,2,3) for load in ('off','heavy') for state,ch in states}
        s=json.loads((DATA/(mode+'-summary.json')).read_text())
        for name,summary in s.items():
            assert summary['runs']==3 and summary['repetitions']==[1,2,3]
            group=[rows[name+f'-r{rep}'] for rep in (1,2,3)]
            np.testing.assert_allclose([r['wifi']['goodput_mbps'] for r in group],summary['wifi_goodput_mbps'])
            if summary['condition']['wifi_load']=='heavy':
                prefix='bidirectional-espnow-wifiheavy-hz0-ch6' if mode=='espnow' else 'bidirectional-ble-wifiheavy-off'
                effects=[100*(1-r['wifi']['goodput_mbps']/rows[prefix+f'-r{rep}']['wifi']['goodput_mbps']) for rep,r in zip((1,2,3),group)]
                np.testing.assert_allclose(effects,summary['matched_wifi_reduction_pct'])
                np.testing.assert_allclose(np.mean(effects),summary['matched_wifi_reduction_mean_pct'])
    s=json.loads((DATA/'tcp-bracket-summary.json').read_text())
    for ch in (6,7,11):
        assert len(s[str(ch)]['blocks'])==3
        for block in s[str(ch)]['blocks']:
            rows=[json.loads((DATA/f'tcpbracket-espnow-ch{ch}-{phase}-r{block["repeat"]}.json').read_text()) for phase in ('before','on','after')]
            assert len({row['source']['before']['configuration_generation'] for row in rows})==1
            rates=[]
            for row,phase in zip(rows,('before','on','after')):
                a=row['receiver']['after'];b=row['receiver']['before']
                assert not a['running'] and row['condition']['wifi_control_hz']==0
                rate=(a['rx_bytes']-b['rx_bytes'])*8/row['counter_seconds']/1e6
                np.testing.assert_allclose(rate,row['wifi_goodput_mbps']);rates.append(rate)
                if phase=='on':
                    app_check(row,row['name'])
            np.testing.assert_allclose(rates,[block['before_mbps'],block['on_mbps'],block['after_mbps']])
            np.testing.assert_allclose(100*(1-rates[1]/((rates[0]+rates[2])/2)),block['reduction_pct'])
            np.testing.assert_allclose(100*(rates[2]/rates[0]-1),block['return_change_pct'])
        np.testing.assert_allclose(np.mean([b['reduction_pct'] for b in s[str(ch)]['blocks']]),s[str(ch)]['mean_reduction_pct'])
    assert manifest['coexistence']['trials']==60 and manifest['coexistence']['status']=='complete'
    assert manifest['tcp_brackets']['blocks']==9 and manifest['tcp_brackets']['windows']==27
    print('Verified 60 bidirectional trials and 9 same-connection TCP blocks: CRC traces, counters, controls, matrices and hashes.')


if __name__=='__main__':
    main()
