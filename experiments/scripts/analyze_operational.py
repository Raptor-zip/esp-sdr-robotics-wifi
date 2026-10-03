#!/usr/bin/env python3
"""Anonymize rate/shape measurements; preserve private I/Q separately."""
import argparse,hashlib,json
from collections import defaultdict
from pathlib import Path
import numpy as np
from signal_processing import spectra
R=Path(__file__).resolve().parents[1];D=R/'data/operational'
def q99(values):return float(np.percentile(values,99)) if len(values) else None

def main():
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['limit','shape'],required=True);p.add_argument('--raw',type=Path,default=Path.home()/'.local/share/esp-sdr/two-team/raw');a=p.parse_args();target=D/a.mode;target.mkdir(parents=True,exist_ok=True);groups=defaultdict(list);shots=0
 sessions=defaultdict(list)
 for f in sorted(a.raw.glob(f'op-{a.mode}-*.json')):
  if f.stem.endswith('-iq'):continue
  name=f.stem;row=json.loads(f.read_text());cx=row.pop('context');assert not row.pop('sdr_errors');q=np.load(a.raw/(name+'-control.npz'));origin=int(q['host_start_ns']);ok=q['received_ns']>0
  assert len(ok)==row['sent']==3000
  np.savez_compressed(target/(name+'-control.npz'),sent_ns=q['sent_ns']-origin,received_ns=np.where(ok,q['received_ns']-origin,-1),planned_ns=q['planned_ns']-origin)
  meta=json.loads((a.raw/(name+'-iq.json')).read_text());assert meta['all_crcs_verified'];iq=np.load(a.raw/(name+'-iq.npz'))['iq'];freq,power=spectra(iq,80000000,1024)
  start=np.array([x['host_start_monotonic'] for x in meta['timing']]);end=np.array([x['host_end_monotonic'] for x in meta['timing']]);shots+=len(iq)
  np.savez_compressed(target/(name+'-spectrum.npz'),frequency_mhz=freq/1e6+meta['lo_mhz'],power_dbfs=(10*np.log10(np.maximum(power,1e-16))).astype(np.float32),capture_start_s=start-origin/1e9,capture_end_s=end-origin/1e9)
  row['condition']={k:cx[k] for k in ('repeat','mode','requested_mbps','generation_period_ms','other_channel','other_width_mhz','own_channel','own_width_mhz')}
  row['layout']=cx['layout']
  row['pre_measurement_setup_attempts']=cx.get('setup_attempts',1)
  row['acquisition_segment']=cx['acquisition_session_id'];sessions[row['acquisition_segment']].append(name)
  setup=cx['setup_history'][-1][-1]
  row['pre_load_peer_verification']={role:setup[role] for role in ('receiver','transmitter')}
  row['counter_window_seconds']=(cx['after_ns']-cx['before_ns'])/1e9
  row['other_socket_accepted_mbps']=(cx['board2_after']['tx_bytes']-cx['board2_before']['tx_bytes'])*8/row['counter_window_seconds']/1e6
  row['other_load_policy']='Unpaced saturated TCP requested; socket acceptance and receiver delivery are distinct from RF airtime'
  row['other_load_command_ack']=cx.get('other_load_ack')
  row['other_send_attempts']=cx['board2_after']['send_attempts']-cx['board2_before']['send_attempts']
  row['other_send_eagain']=cx['board2_after']['send_eagain']-cx['board2_before']['send_eagain']
  row['other_data_path_outcome']=('receiver_delivery_observed' if row['other_delivered_mbps']>0 else 'ap_socket_accepted_payload_but_no_receiver_delivery' if row['other_socket_accepted_mbps']>0 else 'send_attempts_without_payload_progress' if row['other_send_attempts']>0 else 'no_data_path_activity_in_window')
  row['controller_radio']={phase:cx['controller_'+phase] for phase in ('before','after')}
  row['external_radio']={role:{phase:{k:v for k,v in cx[f'board{n}_{phase}'].items() if k not in ('mac','peer')} for phase in ('before','after')} for role,n in [('receiver',1),('transmitter',2)]}
  row['source_counters']={phase:{k:cx['robot_'+phase][k] for k in ('helper_version','configuration_generation','tcp_connection_generation','requested_mbps','period_ms','sent_payload_bytes','generated_payload_bytes','pending_application_bytes','tcp_connected')} for phase in ('before','after')}
  row['sdr']=dict(frames=len(iq),samples=16380,sample_rate_hz=80000000,lo_mhz=meta['lo_mhz'],bandwidth_mhz=48,gain='MANUAL 20',fft_length=1024,all_crcs_verified=True,nominal_observation_pct=len(iq)*16380/80000000/(end[-1]-start[0])*100,rail_pct=float(np.mean((iq==-128)|(iq==127))*100))
  (target/(name+'.json')).write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n');groups[name.rsplit('-r',1)[0]].append((row,(q['received_ns'][ok]-q['sent_ns'][ok])/1e6))
 summary={}
 for k,rows in groups.items():
  n=sum(m['sent'] for m,t in rows);received=sum(m['received'] for m,t in rows)
  summary[k]=dict(condition={x:v for x,v in rows[0][0]['condition'].items() if x!='repeat'},runs=len(rows),sent=n,received=received,loss_pct=(n-received)/n*100,pooled_p99_ms=q99(np.concatenate([t for m,t in rows])),run_p99_ms=[m['rtt_ms']['p99'] for m,t in rows],deadline20_pct=sum(m['sent']*m['missed_deadline_pct']['20'] for m,t in rows)/n,run_deadline20_pct=[m['missed_deadline_pct']['20'] for m,t in rows],delivered_own_mbps=[m['delivered_payload_mbps'][0] for m,t in rows],delivered_other_mbps=[m['other_delivered_mbps'] for m,t in rows],send_lateness_p99_ms=[m['send_lateness_p99_ms'] for m,t in rows],longest_echo_gap_ms=max(m['longest_echo_gap_ms'] for m,t in rows),application_pending_bytes=[m['source_counters']['after']['pending_application_bytes'] for m,t in rows])
  summary[k]['other_socket_accepted_mbps']=[m['other_socket_accepted_mbps'] for m,t in rows]
  summary[k]['other_zero_delivery_runs']=[m['condition']['repeat'] for m,t in rows if m['other_delivered_mbps']==0]
  observed=[(m,t) for m,t in rows if m['other_delivered_mbps']>0]
  summary[k]['receiver_delivery_observed_subset']=dict(runs=len(observed),pooled_p99_ms=q99(np.concatenate([t for m,t in observed])),deadline20_pct=sum(m['sent']*m['missed_deadline_pct']['20'] for m,t in observed)/sum(m['sent'] for m,t in observed)) if observed else None
 (target/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 (target/'acquisition-provenance.json').write_text(json.dumps(dict(firmware_version=7,loaded_results_retried=False,layout_changed=False,session_trials=dict(sessions),note='Current peers confirmed by STA nonce, new AP challenge and STA response before requesting unpaced TCP; delivered payload, socket acceptance and send attempts are distinct from RF airtime'),ensure_ascii=False,indent=2)+'\n')
 m=json.loads((R/'data/manifest.json').read_text());m.setdefault('operational',{})[a.mode]=dict(trials=sum(v['runs'] for v in summary.values()),conditions=len(summary),control_sent=sum(v['sent'] for v in summary.values()),control_received=sum(v['received'] for v in summary.values()),iq_snapshots_original=shots)
 for f in sorted(target.iterdir()):m['files'][str(f.relative_to(R/'data'))]=hashlib.sha256(f.read_bytes()).hexdigest()
 (R/'data/manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n');print(m['operational'][a.mode])
if __name__=='__main__':main()
