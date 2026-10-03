#!/usr/bin/env python3
"""Verify timing, rate readback, achieved payload, conditions and matrix coverage."""
import argparse,hashlib,json
from collections import defaultdict
from pathlib import Path
import numpy as np
def q99(values):return float(np.percentile(values,99)) if len(values) else None
def close_or_none(a,b):return a is b if a is None or b is None else bool(np.isclose(a,b,atol=1e-9))
p=argparse.ArgumentParser();p.add_argument('--require-complete',choices=['limit','shape'],action='append',default=[]);args=p.parse_args()
R=Path(__file__).resolve().parents[1];D=R/'data/operational';m=json.loads((R/'data/manifest.json').read_text())
for mode in args.require_complete:assert mode in m.get('operational',{}),f'{mode}: no recorded matrix'
for name,sha in m['files'].items():assert hashlib.sha256((R/'data'/name).read_bytes()).hexdigest()==sha,name
for mode,expected in m.get('operational',{}).items():
 if mode not in ('limit','shape'):continue
 target=D/mode;groups=defaultdict(list);sent=received=frames=0;covered=set()
 provenance=json.loads((target/'acquisition-provenance.json').read_text());assert provenance['firmware_version']==7 and not provenance['loaded_results_retried'] and not provenance['layout_changed']
 for f in sorted(target.glob('op-*.json')):
  r=json.loads(f.read_text());c=r['condition'];q=np.load(target/(f.stem+'-control.npz'));ok=q['received_ns']>=0;n=len(ok);dt=(q['received_ns'][ok]-q['sent_ns'][ok])/1e6
  assert n==r['sent']==3000 and ok.sum()==r['received']
  assert np.all(q['received_ns'][ok]>=q['sent_ns'][ok]) and np.all(q['sent_ns']>=0)
  for x,y in [(q99(dt),r['rtt_ms']['p99']),((~ok).mean()*100,r['loss_pct']),((~ok | (q['received_ns']-q['sent_ns']>20e6)).mean()*100,r['missed_deadline_pct']['20']),(np.percentile((q['sent_ns']-q['planned_ns'])/1e6,99),r['send_lateness_p99_ms'])]:assert close_or_none(x,y),f.name
  assert c['own_channel']==6 and c['own_width_mhz']==20 and c['other_width_mhz']==20
  assert r['controller_radio']['before']['primary']==6 and r['controller_radio']['after']['primary']==6
  radio=r['external_radio'];assert radio['transmitter']['before']['primary']==c['other_channel'] and radio['receiver']['before']['primary']==c['other_channel']
  for role in ('transmitter','receiver'):
   for phase in ('before','after'):assert radio[role][phase]['version']==7
  assert r['layout']['source']=='user report' and '30 cm' in r['layout']['description']
  assert r['pre_measurement_setup_attempts'] in (1,2)
  assert f.stem in provenance['session_trials'][r['acquisition_segment']]
  proof=r['pre_load_peer_verification'];source=proof['transmitter'];destination=proof['receiver']
  assert source['version']==destination['version']==7 and source['active'] and destination['active']
  assert source['tcp_peer_ready'] and destination['tcp_peer_ready'] and source['tcp_connected'] and destination['connected']
  assert source['tcp_nonce']==destination['tcp_nonce']>0 and source['tcp_challenge']==destination['tcp_challenge']>0
  assert source['primary']==destination['primary']==c['other_channel'] and source['power_save']==destination['power_save']==0
  # The driver requires an established other-team TCP connection before LOAD.
  # These readbacks occur AFTER load warmup: a disconnection caused by the
  # loaded condition is an outcome, not grounds for dropping a bad trial.
  assert radio['receiver']['before']['connected'] and r['controller_radio']['before']['tcp_connected']
  assert np.isclose(r['controller_radio']['after']['bench_rx_bytes']*8/r['seconds']/1e6,r['delivered_payload_mbps'][0])
  assert np.isclose((radio['receiver']['after']['rx_bytes']-radio['receiver']['before']['rx_bytes'])*8/r['counter_window_seconds']/1e6,r['other_delivered_mbps']) and r['other_delivered_mbps']>=0
  assert np.isclose((radio['transmitter']['after']['tx_bytes']-radio['transmitter']['before']['tx_bytes'])*8/r['counter_window_seconds']/1e6,r['other_socket_accepted_mbps']) and r['other_socket_accepted_mbps']>=0
  assert r['other_send_attempts']==radio['transmitter']['after']['send_attempts']-radio['transmitter']['before']['send_attempts'] and r['other_send_attempts']>=0
  assert r['other_send_eagain']==radio['transmitter']['after']['send_eagain']-radio['transmitter']['before']['send_eagain'] and 0<=r['other_send_eagain']<=r['other_send_attempts']
  assert r['other_delivered_mbps']>0 or r['other_send_attempts']>0,f'{f.stem}: no receiver delivery or generator activity in window'
  assert r['other_data_path_outcome']==('receiver_delivery_observed' if r['other_delivered_mbps']>0 else 'ap_socket_accepted_payload_but_no_receiver_delivery' if r['other_socket_accepted_mbps']>0 else 'send_attempts_without_payload_progress')
  assert r['other_load_command_ack']==f'OK LOAD 1000 {r["seconds"]+14}'
  for phase in ('before','after'):assert radio['transmitter'][phase]['load_rate_setting']==1000 and radio['transmitter'][phase]['load_remaining_ms']>0
  for phase in ('before','after'):
   source=r['source_counters'][phase];assert source['requested_mbps']==c['requested_mbps'] and source['period_ms']==c['generation_period_ms']
   assert source['helper_version']==2 and source['configuration_generation']==source['tcp_connection_generation']
   assert source['pending_application_bytes']==max(0,source['generated_payload_bytes']-source['sent_payload_bytes'][0])
  if c['requested_mbps']>0:assert r['delivered_payload_mbps'][0]>0
  z=np.load(target/(f.stem+'-spectrum.npz'));assert z['power_dbfs'].shape==(r['sdr']['frames'],1024) and np.isfinite(z['power_dbfs']).all() and r['sdr']['all_crcs_verified']
  covered.add((c['repeat'],c['requested_mbps'],c['generation_period_ms'],c['other_channel']));groups[f.stem.rsplit('-r',1)[0]].append((r,dt));sent+=n;received+=int(ok.sum());frames+=r['sdr']['frames']
 summary=json.loads((target/'summary.json').read_text())
 for k,rows in groups.items():
  s=summary[k];n=sum(r['sent'] for r,t in rows);got=sum(r['received'] for r,t in rows)
  assert len(rows)==s['runs'] and n==s['sent'] and got==s['received']
  assert close_or_none(q99(np.concatenate([t for r,t in rows])),s['pooled_p99_ms'])
  assert np.isclose(sum(r['missed_deadline_pct']['20']*r['sent'] for r,t in rows)/n,s['deadline20_pct'])
  observed=[(r,t) for r,t in rows if r['other_delivered_mbps']>0];subset=s['receiver_delivery_observed_subset']
  assert s['other_zero_delivery_runs']==[r['condition']['repeat'] for r,t in rows if r['other_delivered_mbps']==0]
  if observed:
   assert subset['runs']==len(observed) and close_or_none(subset['pooled_p99_ms'],q99(np.concatenate([t for r,t in observed])))
   assert np.isclose(subset['deadline20_pct'],sum(r['sent']*r['missed_deadline_pct']['20'] for r,t in observed)/sum(r['sent'] for r,t in observed))
  else:assert subset is None
 assert (len(covered),sent,received,frames)==(expected['trials'],expected['control_sent'],expected['control_received'],expected['iq_snapshots_original'])
 # A partial analysis is useful while running, but never satisfies completion.
 matrix={(rep,rate,period,ch) for rep in (1,2,3) for rate in ((0,.25,.5,1,2) if mode=='limit' else (.5,1)) for period in ((100,) if mode=='limit' else (10,100)) for ch in (6,7,11)}
 print(mode,expected,'complete_matrix:',covered==matrix)
 if expected['trials']==len(matrix) or mode in args.require_complete:assert covered==matrix,f'{mode}: incomplete condition/repeat coverage'
 if mode in args.require_complete:
  assert len(summary)==(15 if mode=='limit' else 12) and all(s['runs']==3 for s in summary.values())
