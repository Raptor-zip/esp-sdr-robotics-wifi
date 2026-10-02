#!/usr/bin/env python3
"""Independent recomputation of published command timing, integrity and rates."""
import hashlib,json
from collections import defaultdict
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[1];D=R/'data/two-team'
def main():
 manifest=json.loads((R/'data/manifest.json').read_text());groups=defaultdict(list);count=sent=received=0
 for name,expected in manifest['files'].items():
  if hashlib.sha256((R/'data'/name).read_bytes()).hexdigest()!=expected:raise ValueError('Checksum mismatch '+name)
 for f in sorted(D.glob('*.json')):
  if f.name=='summary.json':continue
  r=json.loads(f.read_text());a=np.load(D/(f.stem+'-control.npz'));t=a['sent_ns'];q=a['received_ns'];ok=q>=0;n=len(t);rtt=(q[ok]-t[ok])/1e6
  assert n==r['sent']==3000 and np.all(t>=0) and np.all(q[ok]>=t[ok]),f.name
  values={'loss_pct':float((~ok).mean()*100),'p99':float(np.percentile(rtt,99)),'miss20':float((~ok|((q-t)>20e6)).mean()*100),'send_lateness':float(np.percentile((t-a['planned_ns'])/1e6,99))}
  targets={'loss_pct':r['loss_pct'],'p99':r['rtt_ms']['p99'],'miss20':r['missed_deadline_pct']['20'],'send_lateness':r['send_lateness_p99_ms']}
  for k,v in values.items():assert np.isclose(v,targets[k],atol=1e-9), (f.name,k,v,targets[k])
  z=np.load(D/(f.stem+'-spectrum.npz'));assert z['power_dbfs'].shape==(r['sdr']['frames'],1024) and np.isfinite(z['power_dbfs']).all(),f.name
  if r['condition']['own_load']=='heavy':assert r['delivered_payload_mbps'][0]>0,(f.name,'No own payload')
  assert np.isclose(r['controller_after']['bench_rx_bytes']*8/r['seconds']/1e6,r['delivered_payload_mbps'][0]),f.name
  counters=r['other_receiver_counters'];assert np.isclose((counters['after']-counters['before'])*8/r['counter_window_seconds']/1e6,r['other_delivered_mbps']),f.name
  if r['condition'].get('radio_mode')=='ble':
   kind=r['condition']['radio_condition']
   if kind=='advert':assert r['ble_advertisements_received']>0,(f.name,'No advertising received')
   if kind=='data':assert r['other_delivered_mbps']>0 and r['external_transmitter_before']['subscribed'] and r['external_radio_before']['mtu']==247,(f.name,'No BLE notifications')
  groups[f.stem.rsplit('-r',1)[0]].append((rtt,n,int(ok.sum()),values['miss20']));count+=1;sent+=n;received+=int(ok.sum())
 s=json.loads((D/'summary.json').read_text())
 for key,rows in groups.items():
  assert len(rows)==s[key]['runs'],key
  assert np.isclose(np.percentile(np.concatenate([x[0] for x in rows]),99),s[key]['pooled_p99_ms'],atol=1e-9),key
  assert np.isclose(sum(x[1]*x[3] for x in rows)/sum(x[1] for x in rows),s[key]['deadline20_pct'],atol=1e-9),key
 assert count==manifest['two_team']['trials'] and sent==manifest['two_team']['control_sent'] and received==manifest['two_team']['control_received']
 print(json.dumps(dict(trials=count,conditions=len(groups),sent=sent,received=received,all_measured_timing_and_spectra_valid=True),indent=2))
if __name__=='__main__':main()
