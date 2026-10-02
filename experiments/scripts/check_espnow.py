#!/usr/bin/env python3
"""Recalculate application results and verify achieved Wi-Fi load and RF readback."""
import hashlib,json
from collections import defaultdict
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[1];D=R/'data/espnow'
m=json.loads((R/'data/manifest.json').read_text());groups=defaultdict(list)
for name,sha in m['files'].items():assert hashlib.sha256((R/'data'/name).read_bytes()).hexdigest()==sha,name
for f in sorted(D.glob('espnow-*.json')):
 r=json.loads(f.read_text());q=np.load(D/(f.stem+'-control.npz'));ok=q['received_ns']>=0;n=len(ok);dt=(q['received_ns'][ok]-q['sent_ns'][ok])/1e6
 assert n==r['sent']==3000 and ok.sum()==r['received']
 assert np.all(q['received_ns'][ok]>=q['sent_ns'][ok])
 for actual,expected in [(np.percentile(dt,99),r['rtt_ms']['p99']),((~ok).mean()*100,r['loss_pct']),((~ok | (q['received_ns']-q['sent_ns']>20e6)).mean()*100,r['missed_deadline_pct']['20'])]:assert np.isclose(actual,expected,atol=1e-9),f.name
 wifi=r['radio']['wifi'];assert np.isclose((wifi['after']['rx_bytes']-wifi['before']['rx_bytes'])*8/r['counter_window_seconds']/1e6,r['wifi_delivered_mbps'])
 if r['condition']['wifi_load']=='heavy':assert r['wifi_delivered_mbps']>0,f.name
 for role in ('sender','echo'):
  radio=r['radio'][role];assert radio['after']['primary']==r['condition']['espnow_channel'] and radio['after']['rx_rate']==0 and radio['after']['rx_sig_mode']==0,f.name
  assert radio['after']['queue_drops']==radio['before']['queue_drops'],f.name
 spectrum=np.load(D/(f.stem+'-spectrum.npz'));assert spectrum['power_dbfs'].shape==(r['sdr']['frames'],1024) and np.isfinite(spectrum['power_dbfs']).all()
 groups[f.stem.rsplit('-r',1)[0]].append(dt)
s=json.loads((D/'summary.json').read_text())
for k,rows in groups.items():assert len(rows)==s[k]['runs'] and np.isclose(np.percentile(np.concatenate(rows),99),s[k]['pooled_p99_ms'])
assert len(list(D.glob('espnow-*.json')))==m['espnow']['trials'];print('ESP-NOW verified:',m['espnow'])
