#!/usr/bin/env python3
"""Rate-limit and payload-shaping matrices using the existing two-team topology."""
import argparse,fcntl,json,random,secrets,threading,time
from pathlib import Path
import numpy as np
from run_two_team import ROOT,api,capture,measure_controller
from board import Board
from timed_capture import TimedReceiver

def connect_other_pair(client,other,ch,name):
 """Retry only pre-measurement setup; never retry or discard a loaded result."""
 histories=[]
 for attempt in (1,2):
  client.command('STOP');other.command('STOP');other.command(f'AP {ch} 20 76');time.sleep(.7)
  client.command('STA ESP-SDR-INTERFERER SdrLab2026TestOnly 192.168.4.1 20');client.command('PS 0')
  deadline=time.monotonic()+35;history=[]
  while time.monotonic()<deadline:
   transmitter=other.state();receiver=client.state()
   history.append(dict(monotonic_ns=time.monotonic_ns(),transmitter=transmitter,receiver=receiver))
   if transmitter['ap_clients'] and transmitter['tcp_connected'] and receiver['connected'] and receiver['primary']==ch and transmitter['tcp_peer_ready'] and receiver['tcp_peer_ready'] and transmitter['tcp_nonce']==receiver['tcp_nonce'] and transmitter['tcp_challenge']==receiver['tcp_challenge'] and transmitter['tcp_nonce'] and transmitter['tcp_challenge']:
    histories.append(history);return histories
   time.sleep(.4)
  histories.append(history)
  (ROOT/'evidence'/f'{name}-setup-attempt-{attempt}.json').write_text(json.dumps(dict(channel=ch,attempt=attempt,samples=history),indent=2)+'\n')
  print('SETUP RETRY',name,attempt,flush=True);time.sleep(1)
 raise RuntimeError('Other team not associated and TCP-connected after two recorded setup attempts')

def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['limit','shape']);p.add_argument('--pilot',action='store_true');p.add_argument('--seconds',type=int,default=30);a=p.parse_args()
 lock=(ROOT/'evidence/acquisition.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 boards=[];sdr=None;cases=[];session_id=f'{a.mode}-v7-{secrets.token_hex(4)}'
 for rep in range(1,4):
  rates=(0,.25,.5,1,2) if a.mode=='limit' else (.5,1)
  periods=(100,) if a.mode=='limit' else (10,100)
  group=[(rep,rate,period,ch) for rate in rates for period in periods for ch in (6,7,11)]
  random.Random((14000 if a.mode=='limit' else 15000)+rep).shuffle(group);cases.extend(group)
 if a.pilot:cases=[(1,.5,100,7)]
 try:
  for port,baud in [('/dev/ttyUSB0',115200),('/dev/ttyUSB1',115200),('/dev/ttyUSB2',460800)]:boards.append(Board(port,baud))
  client,other,controller=boards;sdr=TimedReceiver('/dev/ttyACM0')
  api('/configure',dict(run_id=0,level='heavy',seconds=4));deadline=time.monotonic()+75
  while time.monotonic()<deadline:
   x=controller.state()
   if x['connected'] and x['tcp_connected']:break
   time.sleep(.4)
  else:raise RuntimeError('Control station and TCP peer not connected')
  api('/configure',dict(run_id=0,level='off',seconds=0))
  for i,(rep,rate,period,ch) in enumerate(cases):
   rate_name=str(rate).replace('.','p');name=f'{"pilot-" if a.pilot else ""}op-{a.mode}-m{rate_name}-p{period}-ch{ch}-r{rep}';out=ROOT/'raw'/name
   if Path(str(out)+'.json').exists():print('KEEP',name,flush=True);continue
   print('START',name,flush=True)
   setup_history=connect_other_pair(client,other,ch,name)
   run_id=600000+(0 if a.mode=='limit' else 100000)+rep*1000+i
   configured=api('/configure',dict(run_id=run_id,level='off',requested_mbps=rate,period_ms=period,seconds=a.seconds+15))
   assert configured['requested_mbps']==rate and configured['period_ms']==period
   other_load_ack=other.command(f'LOAD 1000 {a.seconds+14}');time.sleep(3)
   cx=dict(repeat=rep,mode=a.mode,requested_mbps=rate,generation_period_ms=period,other_channel=ch,other_width_mhz=20,own_channel=6,own_width_mhz=20,layout=dict(description='All boards and PCs on one desk, approximately 30 cm spacing, fixed throughout this series; exact pair distances and orientations not measured',source='user report',moving_people='negligible influence reported by user'),board1_before=client.state(),board2_before=other.state(),controller_before=controller.state(),robot_before=api(),before_ns=time.monotonic_ns(),wall_before_ns=time.time_ns())
   assert cx['board1_before']['version']==7 and cx['board2_before']['version']==7
   cx['setup_attempts']=len(setup_history);cx['setup_history']=setup_history
   cx['other_load_ack']=other_load_ack
   cx['acquisition_session_id']=session_id
   assert cx['robot_before']['helper_version']==2 and cx['robot_before']['tcp_connected'] and cx['robot_before']['configuration_generation']==cx['robot_before']['tcp_connection_generation']
   assert cx['controller_before']['primary']==6 and cx['board2_before']['primary']==ch
   errors=[]
   def record():
    try:capture(sdr,out,a.seconds,2442)
    except BaseException as e:errors.append(repr(e))
   t=threading.Thread(target=record);t.start();result,raw=measure_controller(controller,run_id,a.seconds);t.join(timeout=15)
   if t.is_alive() or errors:raise RuntimeError('SDR capture failed: '+repr(errors))
   cx.update(board1_after=client.state(),board2_after=other.state(),controller_after=controller.state(),robot_after=api(),after_ns=time.monotonic_ns(),wall_after_ns=time.time_ns())
   elapsed=(cx['after_ns']-cx['before_ns'])/1e9
   result['other_delivered_mbps']=(cx['board1_after']['rx_bytes']-cx['board1_before']['rx_bytes'])*8/elapsed/1e6
   result['semantics']='ESP32-3 UDP application echo via Ch6 AP to robot laptop; rate-limited periodically generated TCP in reverse; other team saturating TCP; not ROS 2'
   result['context']=cx;result['sdr_errors']=errors;np.savez_compressed(str(out)+'-control.npz',**raw)
   Path(str(out)+'.json').write_text(json.dumps(result,indent=2)+'\n')
   api('/configure',dict(run_id=0,level='off',seconds=0));other.command('LOAD 0 0')
   print('RESULT',name,'p99',result['rtt_ms']['p99'],'miss20',result['missed_deadline_pct']['20'],'ownMbps',result['delivered_payload_mbps'][0],'otherMbps',result['other_delivered_mbps'],flush=True)
 finally:
  try:api('/configure',dict(run_id=0,level='off',seconds=0))
  except Exception:pass
  for b in boards[:2]:
   try:b.command('STOP')
   except Exception:pass
  for b in boards:b.close()
  if sdr:
   try:sdr.command('FREQ 2412');sdr.command('BANDWIDTH 0');sdr.command('GAIN HARDWARE');sdr.close()
   except Exception:pass
if __name__=='__main__':main()
