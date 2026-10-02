#!/usr/bin/env python3
"""Check published measurements and recalculate delay metrics from relative times."""
import hashlib,json,re
from collections import defaultdict
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'

def main():
 manifest=json.loads((DATA/'manifest.json').read_text())
 for name,expected in manifest['files'].items():
  actual=hashlib.sha256((DATA/name).read_bytes()).hexdigest()
  if actual!=expected:raise RuntimeError(f'Dataset checksum mismatch: {name}')
 groups=defaultdict(list);sent=received=0
 for m in json.loads((DATA/'robotics/runs.json').read_text()):
  name=m['name'];q=np.load(DATA/'robotics'/f'{name}-control.npz');ok=q['received_ns']>0
  rtt=(q['received_ns'][ok]-q['sent_ns'][ok])/1e6
  loss=100*np.mean(~ok);deadline=100*np.mean(~ok | ((q['received_ns']-q['sent_ns'])>20e6))
  checks={'loss_pct':(loss,m['loss_pct']),'p99':(np.percentile(rtt,99),m['rtt_ms']['p99']),'deadline20':(deadline,m['missed_deadline_pct']['20']),'send_jitter':(np.percentile((q['sent_ns']-q['planned_ns'])/1e6,99),m['send_lateness_p99_ms'])}
  for key,(value,expected) in checks.items():
   if not np.isclose(value,expected,rtol=1e-10,atol=1e-9):raise RuntimeError(f'{name}: {key}: {value} != {expected}')
  groups[re.sub(r'-r\d+$','',name)].append((rtt,len(ok),int(ok.sum()),deadline))
  sent+=len(ok);received+=int(ok.sum())
 reference=json.loads((DATA/'robotics/summary.json').read_text());summary={}
 for name,rows in groups.items():
  rtt=np.concatenate([x[0] for x in rows]);n=sum(x[1] for x in rows)
  summary[name]={'trials':len(rows),'sent':n,'received':sum(x[2] for x in rows),'pooled_p99_ms':float(np.percentile(rtt,99)),'deadline20_pct':sum(x[1]*x[3] for x in rows)/n}
  for key in ('pooled_p99_ms','deadline20_pct'):
   if not np.isclose(summary[name][key],reference[name][key],atol=1e-9):raise RuntimeError(f'{name}: pooled {key} mismatch')
 print(json.dumps({'trials':sum(len(x) for x in groups.values()),'conditions':len(groups),'sent':sent,'received':received,'checksum_files':len(manifest['files']),'all_published_metrics_match':True},indent=2))
 return summary
if __name__=='__main__':main()
