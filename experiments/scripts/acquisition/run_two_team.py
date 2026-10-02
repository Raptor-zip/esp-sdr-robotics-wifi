#!/usr/bin/env python3
"""Two-station UDP control and TCP bulk through the Intel BE200 AP with a separately loaded Wi-Fi team.
Raw measurements and secrets stay outside the publication tree. Restore profiles
with the bounded remote wrapper; --finish requests its immediate shutdown.
"""
import argparse,json,os,random,threading,time,urllib.request,subprocess,fcntl
from pathlib import Path
import numpy as np
from board import Board
from timed_capture import TimedReceiver
import zlib
ROOT=Path(os.environ.get('TWO_TEAM_ROOT',str(Path.home()/'.local/share/esp-sdr/two-team')))
TOKEN=(ROOT/'evidence/http-token').read_text().strip()

def api(path='',data=None):
 body=json.dumps(data).encode() if data is not None else None
 req=urllib.request.Request('http://192.168.8.20:8134'+path,body,{'X-Lab-Token':TOKEN,'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=12) as r:return json.load(r)
def capture(receiver,path,seconds,lo):
 receiver.command(f'FREQ {lo}');receiver.command('BANDWIDTH 48');receiver.command('GAIN MANUAL 20')
 before=receiver.clock(16);shots=[];timing=[];until=time.monotonic()+seconds
 while time.monotonic()<until:
  x,t=receiver.take(0);shots.append(x);timing.append(t)
 meta=dict(lo_mhz=lo,sample_rate_hz=80000000,bandwidth_mhz=48,gain='MANUAL 20',frames=len(shots),samples=16380,clock_before=before,clock_after=receiver.clock(16),timing=timing,all_crcs_verified=True)
 np.savez_compressed(str(path)+'-iq.npz',iq=np.stack(shots));Path(str(path)+'-iq.json').write_text(json.dumps(meta,indent=2)+'\n')

def measure_controller(board,run_id,seconds):
 n=int(seconds*100);host_start=time.monotonic_ns();board.command(f'BENCH {run_id} {n}')
 until=time.monotonic()+seconds+8
 while time.monotonic()<until:
  state=board.state()
  if state['done']:break
  time.sleep(.3)
 else:raise RuntimeError('Controller benchmark timeout')
 header=board.command('DUMP','BIN ');_,size,crc=header.split();data=bytearray();deadline=time.monotonic()+8
 while len(data)<int(size) and time.monotonic()<deadline:data.extend(board.port.read(int(size)-len(data)))
 if len(data)!=int(size) or zlib.crc32(data)!=int(crc,16):raise RuntimeError('Controller timing dump CRC mismatch')
 rows=np.frombuffer(data,dtype='<u4').reshape(n,3).astype(np.int64)*1000
 ok=rows[:,2]>0;rtt=(rows[ok,2]-rows[ok,1])/1e6;end=int(seconds*1e9);ordered=np.sort(rows[ok & (rows[:,2]<=end),2]);gaps=np.diff(np.r_[0,ordered,end])/1e6
 result=dict(run_id=run_id,seconds=seconds,hz=100,payload_bytes=64,sent=n,received=int(ok.sum()),loss_pct=float((~ok).mean()*100),rtt_ms={f'p{q}':float(np.percentile(rtt,q)) if len(rtt) else None for q in (50,95,99)},max_rtt_ms=float(rtt.max()) if len(rtt) else None,longest_echo_gap_ms=float(gaps[gaps>=0].max()),missed_deadline_pct={str(d):float((~ok | ((rows[:,2]-rows[:,1])>d*1e6)).mean()*100) for d in (10,20,50,100)},send_lateness_p99_ms=float(np.percentile((rows[:,1]-rows[:,0])/1e6,99)),delivered_payload_mbps=[state['bench_rx_bytes']*8/seconds/1e6,0],semantics='ESP32-3 local-clock UDP application echo RTT via AP to robot laptop; paced synthetic TCP bulk in reverse; not ROS 2; host command time is an approximate SDR alignment anchor')
 raw=dict(host_start_ns=host_start,sent_ns=host_start+rows[:,1],received_ns=np.where(ok,host_start+rows[:,2],0),planned_ns=host_start+rows[:,0],bulk_records=np.zeros((0,5),dtype=np.int64))
 return result,raw

def main():
 lock_file=(ROOT/'evidence/acquisition.lock').open('w');fcntl.flock(lock_file,fcntl.LOCK_EX|fcntl.LOCK_NB)
 p=argparse.ArgumentParser();p.add_argument('--pilot',action='store_true');p.add_argument('--finish',action='store_true');p.add_argument('--seconds',type=float,default=30);p.add_argument('--repeats',type=int,default=3);a=p.parse_args()
 b1=b2=b3=sdr=None
 try:
  b1=Board('/dev/ttyUSB0');b2=Board('/dev/ttyUSB1');b3=Board('/dev/ttyUSB2',460800);sdr=TimedReceiver('/dev/ttyACM0')
  print('BOARDS READY; JOINING CONTROLLER WIFI',flush=True)
  subprocess.run(['nmcli','con','up','sdr-team-a-controller'],capture_output=True,check=True,timeout=40)
  deadline=time.monotonic()+75
  while time.monotonic()<deadline:
   state=b3.state()
   if state['connected'] and state['tcp_connected']:break
   time.sleep(1)
  else:raise RuntimeError('Controller must connect to AP and robot TCP sender')
  end=time.monotonic()+45
  while time.monotonic()<end:
   try:x=api();break
   except OSError:time.sleep(.5)
  else:raise RuntimeError('Robot helper unreachable')
  print('TWO STATIONS AND TCP/UDP READY',flush=True)
  (ROOT/'evidence/robot-diagnostics.json').write_text(json.dumps(api('/diagnostics'),indent=2))
  if a.pilot:
   cases=[(rep,level,6,20,False) for rep,level in enumerate(('off','medium','heavy'),1)]
  else:
   cases=[]
   for rep in range(1,a.repeats+1):
    group=[(rep,own,ch,20,other) for own in ('off','heavy') for ch in (6,7,11) for other in (False,True)]
    group.extend((rep,'heavy',1,w,True) for w in (20,40));random.Random(7200+rep).shuffle(group);cases.extend(group)
  for idx,(rep,own,ch,width,other) in enumerate(cases):
   name=f'{"pilot" if a.pilot else "team"}-{own}-ch{ch}-w{width}-b{int(other)}-r{rep}'
   out=ROOT/'raw'/name
   if Path(str(out)+'.json').exists():print('KEEP',name,flush=True);continue
   print('START',name,flush=True)
   b1.command('STOP');b2.command('STOP');b2.command(f'AP {ch} {width} 76');time.sleep(1)
   b1.command(f'STA ESP-SDR-INTERFERER SdrLab2026TestOnly 192.168.4.1 {width}');b1.command('PS 0')
   deadline=time.monotonic()+25
   while time.monotonic()<deadline:
    state=b2.state()
    if state['ap_clients'] and state['tcp_connected']:break
    time.sleep(.4)
   else:raise RuntimeError('Other team TCP client did not connect')
   run_id=100000+rep*1000+idx+(90000 if a.pilot else 0)
   robot_start=api('/configure',dict(run_id=run_id,level=own,seconds=a.seconds+15))
   if other:b2.command(f'LOAD 1000 {int(a.seconds+14)}')
   time.sleep(3)
   context=dict(repeat=rep,own_load=own,other_load=other,other_channel=ch,other_width_mhz=width,own_channel=6,own_width_mhz=20,requested_power_qdbm=76,board1_before=b1.state(),board2_before=b2.state(),router_before=b3.state(),robot_before=api(),board_sample_before_ns=time.monotonic_ns(),wall_before_ns=time.time_ns(),robot_start=robot_start)
   errors=[]
   def worker():
    try:capture(sdr,out,a.seconds,2427 if ch==1 else 2442)
    except BaseException as e:errors.append(repr(e))
   t=threading.Thread(target=worker);t.start();summary,raw=measure_controller(b3,run_id,a.seconds)
   t.join(timeout=15)
   if t.is_alive():raise RuntimeError('SDR capture thread did not finish')
   context.update(board1_after=b1.state(),board2_after=b2.state(),router_after=b3.state(),robot_after=api(),board_sample_after_ns=time.monotonic_ns(),wall_after_ns=time.time_ns())
   duration=(context['board_sample_after_ns']-context['board_sample_before_ns'])/1e9
   summary['other_delivered_mbps']=(context['board1_after']['rx_bytes']-context['board1_before']['rx_bytes'])*8/duration/1e6
   summary['context']=context;summary['sdr_errors']=errors
   np.savez_compressed(str(out)+'-control.npz',**raw);Path(str(out)+'.json').write_text(json.dumps(summary,indent=2)+'\n')
   api('/configure',dict(run_id=0,level='off',seconds=0));b2.command('LOAD 0 0')
   print('RESULT',name,'p99',summary['rtt_ms']['p99'],'miss20',summary['missed_deadline_pct']['20'],'ownMbps',summary['delivered_payload_mbps'],'otherMbps',summary['other_delivered_mbps'],flush=True)
   if errors:raise RuntimeError(str(errors))
 except BaseException:
  a.finish=True;raise
 finally:
  try:api('/configure',dict(run_id=0,level='off',seconds=0))
  except Exception:pass
  if a.finish:
   try:api('/stop',{})
   except Exception:pass
  for b in (b1,b2):
   if b:
    try:b.command('STOP');b.close()
    except Exception:pass
  if b3:
   if a.finish:
    try:b3.command('STOP')
    except Exception:pass
   b3.close()
  if sdr:
   try:sdr.command('FREQ 2412');sdr.command('BANDWIDTH 0');sdr.command('GAIN HARDWARE');sdr.close()
   except Exception:pass
  
  if a.finish:
   try:api('/stop',{})
   except Exception:pass

if __name__=='__main__':main()
