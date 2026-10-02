#!/usr/bin/env python3
"""Timestamped, CRC-verified I/Q with an explicit vendor-call uncertainty interval."""
import datetime,json,os,sys,time,zlib
from pathlib import Path
import numpy as np
from capture import Receiver
# Acquisition uses RAM by default; offline analysis selects the durable local mirror.
CACHE=Path(os.environ.get('C5_DATA', '/dev/shm/c5-characterization/data'))
CACHE.mkdir(parents=True,exist_ok=True)
class TimedReceiver(Receiver):
 def clock(self,n=32):
  out=[]
  for _ in range(n):
   a=time.monotonic_ns(); wall=time.time_ns(); d=int(self.command('CLOCK?','CLOCK ').split()[1]);b=time.monotonic_ns()
   out.append({'host_before_ns':a,'host_after_ns':b,'device_us':d,'wall_before_ns':wall})
  return out
 def take(self,rate):
  wall=time.time_ns(); iq,t=self.capture(16380,rate)
  _,a,b=self.command('CAPTIME?','CAPTIME ').split()
  t.update(device_begin_us=int(a),device_end_us=int(b),wall_before_ns=wall)
  return iq,t

def measure(r,name,*,frequency=2437,rate=0,bandwidth=48,gain='MANUAL 20',frames=150,
            schedule='immediate',period=.1024,seed=0,context=None):
 r.command(f'FREQ {frequency}');r.command(f'BANDWIDTH {bandwidth}');r.command(f'GAIN {gain}')
 before=r.clock();shots=[];timing=[];rng=np.random.default_rng(seed);due=time.monotonic()
 for i in range(frames):
  if schedule!='immediate':time.sleep(max(0,due-time.monotonic()))
  iq,t=r.take(rate);shots.append(iq);timing.append(t)
  if schedule=='fixed':due+=period
  elif schedule=='random':due+=rng.uniform(.065,2*period-.065)
 after=r.clock();fs=(80,40,20,10,8,4)[rate]*1000000
 meta={'label':name,'identity':r.identity,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'frequency_mhz':frequency,'sample_rate_hz':fs,'bandwidth_mhz':bandwidth,'gain':gain,
  'gain_state':r.command('GAIN?','GAIN '),'frames':frames,'samples':16380,'schedule':schedule,
  'period_s':period,'seed':seed,'clock_before':before,'clock_after':after,'timing':timing,
  'context':context or {},'timestamp_semantics':'vendor stock_capture call bounds; exact ADC trigger is unknown'}
 np.savez_compressed(CACHE/(name+'.npz'),iq=np.stack(shots))
 (CACHE/(name+'.json')).write_text(json.dumps(meta,indent=2)+'\n')
 print(f'SAVED {name}: {frames} snapshots',flush=True)
 return meta
