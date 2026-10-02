#!/usr/bin/env python3
"""Standard Wi-Fi burst load or an external BLE link, with UDP/TCP + real SDR."""
import argparse,fcntl,json,random,threading,time
from pathlib import Path
import numpy as np
from run_two_team import ROOT,api,capture,measure_controller
from board import Board
from timed_capture import TimedReceiver

def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['burst','ble']);p.add_argument('--pilot',action='store_true');p.add_argument('--seconds',type=float,default=30);a=p.parse_args()
 lock=(ROOT/'evidence/acquisition.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);b1=b2=b3=sdr=None
 try:
  b1=Board('/dev/ttyUSB0');b2=Board('/dev/ttyUSB1');b3=Board('/dev/ttyUSB2',460800);sdr=TimedReceiver('/dev/ttyACM0');deadline=time.monotonic()+60
  while time.monotonic()<deadline:
   try:state=b3.state()
   except TimeoutError:continue
   if state['connected'] and state['tcp_connected']:break
   time.sleep(.4)
  else:raise RuntimeError('Controller/robot link not ready')
  cases=[]
  for rep in range(1,4):
   group=[(rep,'heavy',ch) for ch in (6,7,11)] if a.mode=='burst' else [(rep,own,kind) for own in ('off','heavy') for kind in ('off','advert','data')]
   random.Random(9100+rep).shuffle(group);cases.extend(group)
  if a.pilot:cases=[(1,'off','data')]
  for idx,(rep,own,condition) in enumerate(cases):
   name=(f'team-{own}-ch{condition}-w20-b2-r{rep}' if a.mode=='burst' else f'ble-{own}-{condition}-r{rep}');name=('pilot-'+name) if a.pilot else name;out=ROOT/'raw'/name
   if Path(str(out)+'.json').exists():print('KEEP',name,flush=True);continue
   print('START',name,flush=True)
   if a.mode=='burst':
    b1.command('STOP');b2.command('STOP');b2.command(f'AP {condition} 20 76');time.sleep(.7);b1.command('STA ESP-SDR-INTERFERER SdrLab2026TestOnly 192.168.4.1 20');b1.command('PS 0');deadline=time.monotonic()+30
    while time.monotonic()<deadline:
     x=b2.state()
     if x['tcp_connected'] and x['ap_clients']:break
     time.sleep(.4)
    else:raise RuntimeError('Wi-Fi interference test pair not connected')
   else:
    b1.command('ROLE 0');b2.command('ROLE 0');time.sleep(.3)
    if condition=='advert':b2.command('ROLE 3');b1.command('ROLE 4')
    elif condition=='data':
     b2.command('ROLE 1');b1.command('ROLE 2');deadline=time.monotonic()+30
     while time.monotonic()<deadline:
      x=b2.state();y=b1.state()
      if x['connected'] and y['connected'] and x['mtu']>=247:break
      time.sleep(.4)
     else:raise RuntimeError('BLE connection/MTU not ready')
     b1.command(f'SUB {x["value_handle"]}');time.sleep(.5)
     if not b2.state()['subscribed']:raise RuntimeError('BLE notifications not subscribed')
     b2.command(f'LOAD 2 {int(a.seconds+15)}')
   run_id=300000+rep*1000+idx;api('/configure',dict(run_id=run_id,level=own,seconds=a.seconds+15));time.sleep(3)
   cx=dict(repeat=rep,own_load=own,radio_mode=a.mode,radio_condition=condition,own_channel=6,own_width_mhz=20,board1_before=b1.state(),board2_before=b2.state(),controller_before=b3.state(),robot_before=api(),board_sample_before_ns=time.monotonic_ns())
   errors=[];transitions=[];stop=threading.Event()
   def record():
    try:capture(sdr,out,a.seconds,2442)
    except BaseException as e:errors.append(repr(e))
   def pulse():
    on=True
    while not stop.is_set():
     before=time.monotonic_ns();b2.command('LOAD 1000 3' if on else 'LOAD 0 0');after=time.monotonic_ns();transitions.append(dict(on=on,before_ns=before,after_ns=after));on=not on;stop.wait(2)
    b2.command('LOAD 0 0')
   t=threading.Thread(target=record);t.start();pulses=None
   if a.mode=='burst':pulses=threading.Thread(target=pulse);pulses.start()
   result,raw=measure_controller(b3,run_id,a.seconds);t.join(timeout=15);stop.set()
   if pulses:pulses.join(timeout=8)
   cx.update(board1_after=b1.state(),board2_after=b2.state(),controller_after=b3.state(),robot_after=api(),board_sample_after_ns=time.monotonic_ns(),transitions=transitions)
   seconds=(cx['board_sample_after_ns']-cx['board_sample_before_ns'])/1e9
   result['other_delivered_mbps']=(cx['board1_after']['rx_bytes']-cx['board1_before']['rx_bytes'])*8/seconds/1e6;result['context']=cx;result['sdr_errors']=errors
   if a.mode=='ble':result['ble_advertisements_received']=cx['board1_after']['advertisements']-cx['board1_before']['advertisements']
   np.savez_compressed(str(out)+'-control.npz',**raw);Path(str(out)+'.json').write_text(json.dumps(result,indent=2)+'\n');api('/configure',dict(run_id=0,level='off',seconds=0))
   print('RESULT',name,'p99',result['rtt_ms']['p99'],'ownMbps',result['delivered_payload_mbps'][0],'otherMbps',result['other_delivered_mbps'],flush=True)
   if t.is_alive() or errors:raise RuntimeError('RF capture failed: '+str(errors))
 finally:
  try:api('/configure',dict(run_id=0,level='off',seconds=0))
  except Exception:pass
  for b in (b1,b2):
   if b:
    try:b.command('ROLE 0' if a.mode=='ble' else 'STOP');b.close()
    except Exception:pass
  if b3:b3.close()
  if sdr:
   try:sdr.command('FREQ 2412');sdr.command('BANDWIDTH 0');sdr.command('GAIN HARDWARE');sdr.close()
   except Exception:pass
if __name__=='__main__':main()
