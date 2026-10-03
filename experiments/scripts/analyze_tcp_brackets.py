#!/usr/bin/env python3
"""Same-connection TCP-only stopped/on/stopped control blocks."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from analyze_long_espnow import public_radio, source_counters, summarize_events
from signal_processing import spectra

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'data/coexistence'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--raw',type=Path,default=Path.home()/'.local/share/esp-sdr/two-team/raw')
    parser.add_argument('--preview',action='store_true');args=parser.parse_args()
    TARGET.mkdir(parents=True,exist_ok=True);rows=[];blocks=[]
    for rep in (1,2,3):
        for channel in (6,7,11):
            block=[]
            for phase in ('before','on','after'):
                name=f'tcpbracket-espnow-ch{channel}-{phase}-r{rep}';path=args.raw/(name+'.json')
                if not path.exists():
                    assert args.preview,(name,'missing');break
                raw=json.loads(path.read_text());cx=raw['context'];counter=cx['tcp_measurement'];assert raw['sdr_errors']==[]
                assert raw['seconds']==cx['seconds']==10 and cx['wifi_control_hz']==0
                assert cx['radio']==(200 if phase=='on' else 0) and cx['radio_channel']==channel
                for state in (counter['before'],counter['after']):
                    assert state['connected'] and state['tcp_connected'] and state['primary']==6 and state['ap_bw']==1 and not state['running']
                elapsed=(counter['after_end_ns']-counter['before_end_ns'])/1e9
                assert abs(elapsed-counter['seconds'])<1e-9
                rate=(counter['after']['rx_bytes']-counter['before']['rx_bytes'])*8/elapsed/1e6
                np.testing.assert_allclose(rate,raw['wifi_goodput_mbps'])
                assert rate>0
                generation=cx['source_before']['configuration_generation']
                assert generation==cx['source_after']['configuration_generation']==cx['source_before']['tcp_connection_generation']==cx['source_after']['tcp_connection_generation']
                row=dict(name=name,run_id=raw['run_id'],condition=dict(repeat=rep,channel=channel,phase=phase,hz=200 if phase=='on' else 0,wifi_control_hz=0,wifi_hops=1),
                    nominal_seconds=10,counter_seconds=elapsed,counter_uncertainty_ms=counter['read_uncertainty_ms'],
                    wifi_goodput_mbps=rate,receiver={p:public_radio(counter[p]) for p in ('before','after')},
                    source={p:source_counters(cx['source_'+p]) for p in ('before','after')},
                    placement={k:v for k,v in cx['placement'].items() if k!='confirmation_utc'},
                    semantics='TCP-only one-hop cohort; no UDP probe; same connection within before/on/after block. Each block is one repetition, not three independent repetitions.')
                if phase=='on':
                    trace=np.load(args.raw/(name+'-events.npz'));events=trace['events']
                    assert raw['uart']['all_crcs_verified'] and len(events)==trace['block_event_counts'].sum()
                    assert cx['sender_after']['trace_drops']==0 and events[-1,3]==raw['run_id']
                    arrays,stats,timeline=summarize_events(events,200,10)
                    assert stats['send_calls']==cx['sender_after']['sent_calls'] and stats['reply_callbacks']==cx['sender_after']['reply_callbacks']
                    row['espnow']=stats
                    np.savez_compressed(TARGET/(name+'-espnow.npz'),**arrays)
                    np.savez_compressed(TARGET/(name+'-events.npz'),events=events,block_received_ns=trace['block_received_ns'],block_event_counts=trace['block_event_counts'])
                meta=json.loads((args.raw/(name+'-iq.json')).read_text());assert meta['all_crcs_verified']
                row['sdr']={k:meta[k] for k in ('lo_mhz','samples','sample_rate_hz','bandwidth_mhz','gain','frames','all_crcs_verified')}
                assert (meta['lo_mhz'],meta['sample_rate_hz'],meta['bandwidth_mhz'],meta['gain'])==(2442,80000000,48,'MANUAL 20')
                if not args.preview:
                    iq=np.load(args.raw/(name+'-iq.npz'))['iq'];assert iq.shape==(meta['frames'],16380,2)
                    frequency,power=spectra(iq,80000000,1024)
                    np.savez_compressed(TARGET/(name+'-spectrum.npz'),frequency_mhz=frequency/1e6+2442,power_dbfs=(10*np.log10(np.maximum(power,1e-16))).astype(np.float32))
                    (TARGET/(name+'.json')).write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n')
                block.append((row,generation,counter));rows.append(row)
            if len(block)!=3:
                continue
            assert len({r[1] for r in block})==1,'Fresh TCP connection cannot be mixed into a bracket'
            for previous,current in zip(block,block[1:]):
                assert current[2]['before']['rx_bytes']>=previous[2]['after']['rx_bytes']
                assert current[0]['source']['before']['sent_payload_bytes'][0]>=previous[0]['source']['after']['sent_payload_bytes'][0]
            before,on,after=[r[0]['wifi_goodput_mbps'] for r in block];reference=(before+after)/2
            blocks.append(dict(repeat=rep,channel=channel,before_mbps=before,on_mbps=on,after_mbps=after,
                reference_mbps=reference,reduction_pct=100*(1-on/reference),
                return_change_pct=100*(after/before-1),counter_uncertainty_ms=[r[0]['counter_uncertainty_ms'] for r in block],
                espnow=block[1][0]['espnow']))
    if not args.preview:
        assert len(blocks)==9 and len(rows)==27
        summary={str(channel):dict(blocks=[b for b in blocks if b['channel']==channel],
            mean_reduction_pct=float(np.mean([b['reduction_pct'] for b in blocks if b['channel']==channel]))) for channel in (6,7,11)}
        (TARGET/'tcp-bracket-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
        path=ROOT/'data/manifest.json';manifest=json.loads(path.read_text())
        manifest['tcp_brackets']=dict(blocks=9,windows=27,seconds_per_window=10,wifi_control_hz=0,
            espnow_control_planned=sum(b['espnow']['planned'] for b in blocks),
            espnow_control_received=sum(b['espnow']['unique_replies'] for b in blocks),
            iq_snapshots_original=sum(r['sdr']['frames'] for r in rows),status='complete')
        for file in TARGET.iterdir():
            manifest['files'][str(file.relative_to(ROOT/'data'))]=hashlib.sha256(file.read_bytes()).hexdigest()
        path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    for b in blocks:
        print('Ch',b['channel'],'r',b['repeat'],'before/on/after',round(b['before_mbps'],3),round(b['on_mbps'],3),round(b['after_mbps'],3),'reduction',round(b['reduction_pct'],1),'return',round(b['return_change_pct'],1))


if __name__=='__main__':
    main()
