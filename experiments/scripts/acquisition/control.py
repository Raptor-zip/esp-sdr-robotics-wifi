#!/usr/bin/env python3
"""100 Hz UDP echo measurements with exact host timestamps, no one-way claim."""
import argparse,json,selectors,socket,struct,time
from pathlib import Path
import numpy as np

def run(host,seconds=40,hz=100,payload=64,port=5140):
 s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.setblocking(False)
 s.connect((host,port));sel=selectors.DefaultSelector();sel.register(s,selectors.EVENT_READ)
 n=int(seconds*hz);sent=np.zeros(n,dtype=np.int64);received=np.zeros(n,dtype=np.int64)
 planned=np.zeros(n,dtype=np.int64);duplicates=0;foreign=0;errors=[]
 start=time.monotonic_ns();period=round(1e9/hz);seq=0
 while seq<n or time.monotonic_ns()<start+int((seconds+1)*1e9):
  now=time.monotonic_ns()
  if seq<n and now>=start+seq*period:
   # One sample per planned slot; report actual send jitter. Do not hide stalls.
   planned[seq]=start+seq*period;sent[seq]=time.monotonic_ns()
   packet=struct.pack('!QQ',seq,int(sent[seq]))+bytes(payload-16)
   try:s.send(packet)
   except OSError as e:errors.append({'seq':seq,'error':str(e)})
   seq+=1
   continue
  wait=min(.02,max(0,(start+seq*period-time.monotonic_ns())/1e9)) if seq<n else .02
  for key,_ in sel.select(wait):
   while True:
    try:d=s.recv(2048)
    except BlockingIOError:break
    except OSError as e:errors.append({'receive_error':str(e)});break
    t=time.monotonic_ns()
    if len(d)!=payload:foreign+=1;continue
    i,stamp=struct.unpack('!QQ',d[:16])
    if i>=n or stamp!=sent[i]:foreign+=1;continue
    if received[i]:duplicates+=1
    else:received[i]=t
 sel.close();s.close();ok=received>0;rtt=(received[ok]-sent[ok])/1e6
 end=start+int(seconds*1e9);ordered=np.sort(received[ok & (received<=end)]);gaps=np.diff(np.r_[start,ordered,end]) /1e6
 gaps=gaps[gaps>=0];lost=~ok
 max_loss=0;streak=0
 for x in lost:streak=streak+1 if x else 0;max_loss=max(max_loss,streak)
 result={'host':host,'seconds':seconds,'hz':hz,'payload_bytes':payload,'sent':n,'received':int(ok.sum()),
  'loss_pct':100*float(lost.mean()),'rtt_ms':{f'p{q}':float(np.percentile(rtt,q)) if len(rtt) else None for q in (50,95,99)},
  'max_rtt_ms':float(rtt.max()) if len(rtt) else None,'longest_echo_gap_ms':float(gaps.max()),'max_consecutive_missing':max_loss,
  'missed_deadline_pct':{str(d):100*float((lost | ((received-sent)>d*1e6)).mean()) for d in (10,20,50,100)},
  'send_lateness_p99_ms':float(np.percentile((sent-planned)/1e6,99)),'send_lateness_max_ms':float(((sent-planned)/1e6).max()),
  'duplicates':duplicates,'foreign':foreign,'errors':errors,'host_start_ns':start,
  'semantics':'host application echo RTT; receive gaps refer to echo availability, not one-way robot updates'}
 return result,dict(sent_ns=sent,received_ns=received,planned_ns=planned)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--host',required=True);p.add_argument('--seconds',type=float,default=40);p.add_argument('--output',required=True);a=p.parse_args()
 result,raw=run(a.host,a.seconds);out=Path(a.output);out.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n');np.savez_compressed(out.with_suffix('.npz'),**raw);print(json.dumps(result),flush=True)
