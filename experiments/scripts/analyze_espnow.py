#!/usr/bin/env python3
"""Publish anonymous ESP-NOW application timing and real FFT measurements."""
import argparse,hashlib,json
from collections import defaultdict
from pathlib import Path
import numpy as np
from signal_processing import spectra
R=Path(__file__).resolve().parents[1];D=R/'data/espnow'
def main():
 p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,default=Path.home()/'.local/share/esp-sdr/two-team/raw');a=p.parse_args();D.mkdir(exist_ok=True);groups=defaultdict(list);shots=0
 for f in sorted(a.raw.glob('espnow-*.json')):
  if f.stem.endswith('-iq'):continue
  name=f.stem;r=json.loads(f.read_text());cx=r.pop('context');assert not r.pop('sdr_errors');r.pop('delivered_payload_mbps');q=np.load(a.raw/(name+'-control.npz'));origin=int(q['host_start_ns']);ok=q['received_ns']>0
  np.savez_compressed(D/(name+'-control.npz'),sent_ns=q['sent_ns']-origin,received_ns=np.where(ok,q['received_ns']-origin,-1),planned_ns=q['planned_ns']-origin)
  m=json.loads((a.raw/(name+'-iq.json')).read_text());iq=np.load(a.raw/(name+'-iq.npz'))['iq'];freq,power=spectra(iq,80000000,1024);tim=m['timing'];start=np.array([x['host_start_monotonic'] for x in tim]);end=np.array([x['host_end_monotonic'] for x in tim]);shots+=len(iq)
  np.savez_compressed(D/(name+'-spectrum.npz'),frequency_mhz=freq/1e6+m['lo_mhz'],power_dbfs=(10*np.log10(np.maximum(power,1e-16))).astype(np.float32),capture_start_s=start-origin/1e9,capture_end_s=end-origin/1e9)
  r['condition']={k:cx[k] for k in ('repeat','wifi_load','espnow_channel','wifi_channel','wifi_width_mhz','phy_rate_mbps','encrypted')}
  r['radio']={role:{phase:{k:v for k,v in cx[role+'_'+phase].items() if k not in ('mac','peer')} for phase in ('before','after')} for role in ('sender','echo','wifi')}
  r['sdr']=dict(frames=len(iq),sample_rate_hz=80000000,samples=16380,lo_mhz=m['lo_mhz'],bandwidth_mhz=48,gain='MANUAL 20',fft_length=1024,all_crcs_verified=True,rail_pct=float(np.mean((iq==-128)|(iq==127))*100),nominal_observation_pct=len(iq)*16380/80000000/(end[-1]-start[0])*100)
  (D/(name+'.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');groups[name.rsplit('-r',1)[0]].append((r,(q['received_ns'][ok]-q['sent_ns'][ok])/1e6))
 s={}
 for k,rows in groups.items():
  n=sum(x['sent'] for x,t in rows);got=sum(x['received'] for x,t in rows);s[k]=dict(runs=len(rows),sent=n,received=got,loss_pct=(n-got)/n*100,pooled_p99_ms=float(np.percentile(np.concatenate([t for x,t in rows]),99)),run_p99_ms=[x['rtt_ms']['p99'] for x,t in rows],deadline20_pct=sum(x['sent']*x['missed_deadline_pct']['20'] for x,t in rows)/n,wifi_mbps=[x['wifi_delivered_mbps'] for x,t in rows],longest_echo_gap_ms=max(x['longest_echo_gap_ms'] for x,t in rows))
 (D/'summary.json').write_text(json.dumps(s,indent=2)+'\n');m=json.loads((R/'data/manifest.json').read_text());m['espnow']=dict(trials=sum(v['runs'] for v in s.values()),conditions=len(s),control_sent=sum(v['sent'] for v in s.values()),control_received=sum(v['received'] for v in s.values()),iq_snapshots_original=shots)
 for f in sorted(D.iterdir()):m['files'][str(f.relative_to(R/'data'))]=hashlib.sha256(f.read_bytes()).hexdigest()
 (R/'data/manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n');print(m['espnow'])
if __name__=='__main__':main()
