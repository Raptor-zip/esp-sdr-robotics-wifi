#!/usr/bin/env python3
"""Publish relative command timing and measured FFT; keep private raw I/Q intact."""
import argparse,hashlib,json,sys
from collections import defaultdict
from pathlib import Path
import numpy as np
from signal_processing import spectra
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data/two-team'

def main():
 p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,default=Path.home()/'.local/share/esp-sdr/two-team/raw');a=p.parse_args();DATA.mkdir(parents=True,exist_ok=True);groups=defaultdict(list);rtt_groups=defaultdict(list);total_shots=0
 for f in sorted(list(a.raw.glob('team-*.json'))+list(a.raw.glob('ble-*.json'))):
  if f.stem.endswith('-iq'):continue
  name=f.stem;row=json.loads(f.read_text());cx=row['context'];k=name.rsplit('-r',1)[0];ctl=np.load(a.raw/(name+'-control.npz'));origin=int(ctl['host_start_ns']);sent=ctl['sent_ns'];recv=ctl['received_ns'];n=len(sent);ok=recv>0;rtt=(recv[ok]-sent[ok])/1e6
  if row['sdr_errors']:raise ValueError(f'SDR errors in {name}')
  if n!=3000 or (sent==0).any() or (recv[ok]<sent[ok]).any():raise ValueError(f'Invalid control timestamps in {name}')
  bulk=ctl['bulk_records'].copy();bulk[:,3]-=origin
  # Remote monotonic timestamps are not synchronized; only differences on the
  # robot's own clock are useful. Never subtract a robot stamp from host time.
  if len(bulk):bulk[:,2]-=bulk[0,2]
  np.savez_compressed(DATA/(name+'-control.npz'),sent_ns=sent-origin,received_ns=np.where(ok,recv-origin,-1),planned_ns=ctl['planned_ns']-origin,bulk_records=bulk)
  meta=json.loads((a.raw/(name+'-iq.json')).read_text());iq=np.load(a.raw/(name+'-iq.npz'))['iq'];freq,power=spectra(iq,meta['sample_rate_hz'],1024);z=(10*np.log10(np.maximum(power,1e-16))).astype(np.float32)
  capture_start=np.array([t['host_start_monotonic'] for t in meta['timing']]);capture_end=np.array([t['host_end_monotonic'] for t in meta['timing']]);elapsed=float(capture_end[-1]-capture_start[0]);duty=len(iq)*16380/80000000/elapsed*100;total_shots+=len(iq)
  np.savez_compressed(DATA/(name+'-spectrum.npz'),frequency_mhz=freq/1e6+meta['lo_mhz'],power_dbfs=z,capture_start_s=capture_start-origin/1e9,capture_end_s=capture_end-origin/1e9)
  public={x:y for x,y in row.items() if x not in ('context','sdr_errors')}
  duration=(cx['board_sample_after_ns']-cx['board_sample_before_ns'])/1e9
  public['counter_window_seconds']=duration
  public['controller_after']=cx.get('controller_after',cx.get('router_after'))
  public['other_receiver_counters']={phase:cx['board1_'+phase]['rx_bytes'] for phase in ('before','after')}
  public['source_counters']={phase:cx['robot_'+phase]['sent_payload_bytes'] for phase in ('before','after')}
  if 'radio_mode' in cx:
   public['condition']={x:cx[x] for x in ('repeat','own_load','radio_mode','radio_condition','own_channel','own_width_mhz')}
   public['controller_radio']=cx['controller_before']
   public['external_radio_before']={k:v for k,v in cx['board1_before'].items()};public['external_radio_after']=cx['board1_after']
   public['external_transmitter_before']=cx['board2_before'];public['external_transmitter_after']=cx['board2_after']
   public['load_transitions']=[dict(on=x['on'],before_s=(x['before_ns']-origin)/1e9,after_s=(x['after_ns']-origin)/1e9) for x in cx.get('transitions',[])]
  else:
   public['condition']={x:cx[x] for x in ('repeat','own_load','other_load','other_channel','other_width_mhz','own_channel','own_width_mhz','requested_power_qdbm')}
   public['actual_radio']={x:cx['board2_before'][x] for x in ('primary','secondary','configured_bw','ap_bw','tx_qdbm')}
   public['controller_radio']=cx['router_before'];public['other_station_radio']={k:cx['board1_before'][k] for k in ('primary','secondary','ap_bw','rssi')}
  public['source_payload_mbps']=[(cx['robot_after']['sent_payload_bytes'][i]-cx['robot_before']['sent_payload_bytes'][i])*8/duration/1e6 for i in (0,1)]
  public['sdr']=dict(frames=len(iq),samples=16380,sample_rate_hz=80000000,lo_mhz=meta['lo_mhz'],bandwidth_mhz=48,gain='MANUAL 20',fft_length=1024,all_crcs_verified=True,nominal_observation_pct=duty,rail_pct=float(np.mean((iq==-128)|(iq==127))*100))
  (DATA/(name+'.json')).write_text(json.dumps(public,ensure_ascii=False,indent=2)+'\n');groups[k].append(public);rtt_groups[k].append(rtt)
 summary={}
 for k,runs in groups.items():
  n=sum(r['sent'] for r in runs);received=sum(r['received'] for r in runs);rtt=np.concatenate(rtt_groups[k]);summary[k]=dict(runs=len(runs),sent=n,received=received,loss_pct=(n-received)/n*100,pooled_p99_ms=float(np.percentile(rtt,99)),run_p99_ms=[r['rtt_ms']['p99'] for r in runs],deadline20_pct=sum(r['missed_deadline_pct']['20']*r['sent'] for r in runs)/n,run_deadline20_pct=[r['missed_deadline_pct']['20'] for r in runs],delivered_own_mbps=[sum(r['delivered_payload_mbps']) for r in runs],source_own_mbps=[sum(r['source_payload_mbps']) for r in runs],delivered_other_mbps=[r['other_delivered_mbps'] for r in runs],send_lateness_p99_ms=[r['send_lateness_p99_ms'] for r in runs],longest_echo_gap_ms=max(r['longest_echo_gap_ms'] for r in runs))
 (DATA/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 manifest=json.loads((ROOT/'data/manifest.json').read_text());manifest['two_team']=dict(core_trials=sum(len(v) for k,v in groups.items() if k.startswith('team-') and not k.endswith('b2')),burst_trials=sum(len(v) for k,v in groups.items() if k.endswith('b2')),ble_trials=sum(len(v) for k,v in groups.items() if k.startswith('ble-')),trials=sum(len(x) for x in groups.values()),control_sent=sum(r['sent'] for v in groups.values() for r in v),control_received=sum(r['received'] for v in groups.values() for r in v),iq_snapshots_original=total_shots)
 for f in sorted(DATA.iterdir()):
  if f.is_file():manifest['files'][str(f.relative_to(ROOT/'data'))]=hashlib.sha256(f.read_bytes()).hexdigest()
 (ROOT/'data/manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print('Published',manifest['two_team'])

if __name__=='__main__':main()
