#!/usr/bin/env python3
"""ESP-NOW application echo, independent Wi-Fi TCP and CRC-verified SDR."""
import argparse,fcntl,json,random,threading,time
from pathlib import Path
import numpy as np
from run_two_team import ROOT,api,capture,measure_controller
from board import Board
from timed_capture import TimedReceiver

def main():
 p=argparse.ArgumentParser();p.add_argument('--pilot',action='store_true');a=p.parse_args();lock=(ROOT/'evidence/acquisition.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);boards=[];sdr=None
 try:
  for port,baud in [('/dev/ttyUSB0',115200),('/dev/ttyUSB1',115200),('/dev/ttyUSB2',460800)]:boards.append(Board(port,baud))
  sender,echo,wifi=boards;sdr=TimedReceiver('/dev/ttyACM0');s=sender.state();e=echo.state();sender.command('PEER '+e['mac']);echo.command('PEER '+s['mac']);echo.command('ROLE 1');sender.command('ROLE 2');api('/configure',dict(run_id=0,level='heavy',seconds=4));deadline=time.monotonic()+60
  while time.monotonic()<deadline:
   try:s=wifi.state()
   except TimeoutError:continue
   if s['connected'] and s['tcp_connected']:break
   time.sleep(.4)
  else:raise RuntimeError('Independent Wi-Fi bulk receiver is not connected')
  api('/configure',dict(run_id=0,level='off',seconds=0))
  cases=[]
  for rep in range(1,4):
   group=[(rep,level,ch) for level in ('off','heavy') for ch in (6,7,11)];random.Random(12000+rep).shuffle(group);cases.extend(group)
  if a.pilot:cases=[(1,'off',6)]
  for i,(rep,level,ch) in enumerate(cases):
   name=f'{"pilot-" if a.pilot else ""}espnow-{level}-ch{ch}-r{rep}';out=ROOT/'raw'/name
   if Path(str(out)+'.json').exists():print('KEEP',name,flush=True);continue
   print('START',name,flush=True);sender.command(f'CHANNEL {ch}');echo.command(f'CHANNEL {ch}');run_id=500000+rep*1000+i;api('/configure',dict(run_id=run_id,level=level,seconds=45));time.sleep(3)
   cx=dict(repeat=rep,wifi_load=level,espnow_channel=ch,wifi_channel=6,wifi_width_mhz=20,phy_rate_mbps=1,encrypted=False,sender_before=sender.state(),echo_before=echo.state(),wifi_before=wifi.state(),robot_before=api(),before_ns=time.monotonic_ns());errors=[]
   def record():
    try:capture(sdr,out,30,2442)
    except BaseException as e:errors.append(repr(e))
   t=threading.Thread(target=record);t.start();result,raw=measure_controller(sender,run_id,30,transport='espnow');t.join(timeout=15)
   cx.update(sender_after=sender.state(),echo_after=echo.state(),wifi_after=wifi.state(),robot_after=api(),after_ns=time.monotonic_ns());elapsed=(cx['after_ns']-cx['before_ns'])/1e9
   result['wifi_delivered_mbps']=(cx['wifi_after']['rx_bytes']-cx['wifi_before']['rx_bytes'])*8/elapsed/1e6;result['counter_window_seconds']=elapsed;result['context']=cx;result['sdr_errors']=errors
   np.savez_compressed(str(out)+'-control.npz',**raw);Path(str(out)+'.json').write_text(json.dumps(result,indent=2)+'\n');api('/configure',dict(run_id=0,level='off',seconds=0))
   print('RESULT',name,'p99',result['rtt_ms']['p99'],'miss20',result['missed_deadline_pct']['20'],'loss',result['loss_pct'],'WiFiMbps',result['wifi_delivered_mbps'],flush=True)
   if t.is_alive() or errors:raise RuntimeError('SDR capture failed: '+str(errors))
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
