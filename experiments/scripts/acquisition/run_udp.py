#!/usr/bin/env python3
"""Robot-control comparisons under a common offered UDP application load."""
import os,json,random,time,subprocess,sys,traceback
from pathlib import Path
import run as lab
from board import Board
SUCCESS=False
try:
 if not Path('/dev/shm/robotics-wifi/network-ready').exists():raise RuntimeError('AP not ready')
 lab.OFFLINE_ARCHIVE=True
 lab.b1=Board('/dev/ttyUSB0');lab.b2=Board('/dev/ttyUSB1');lab.sdr=lab.TimedReceiver('/dev/ttyACM0')
 lab.b1.command('STA ESP-SDR-LAB SdrLab2026TestOnly OFF 20');lab.wait_board(lab.b1);time.sleep(2);host=lab.esp_ip()
 cases=[('ch11idle',11,20,0),('ch6',6,20,20),('ch7',7,20,20),('ch11',11,20,20),('ch1w20',1,20,20),('ch1w40',1,40,20)]
 for rep in range(1,4):
  order=list(enumerate(cases));random.Random(5040+rep).shuffle(order)
  for idx,(label,ch,width,rate) in order:
   name=f'udp20-{label}-r{rep}';ident=30000+rep*100+idx
   existing=lab.C/(name+'.json')
   if existing.exists():
    saved=json.loads(existing.read_text())
    if 'udp_whole_packets' in saved.get('context',{}):
     print('KEEP COMPLETE',name,flush=True);continue
    for p in lab.C.glob(name+'*'):p.rename(p.with_name('pilot-disk-full-'+p.name))
   lab.b2.command('STOP');time.sleep(1);lab.b2.command(f'AP {ch} {width} 76')
   end=time.monotonic()+55
   while time.monotonic()<end:
    x=lab.b2.state()
    if x['ap_clients'] and x['udp_ready']:break
    time.sleep(1)
   else:raise TimeoutError('UDP client readiness not confirmed')
   time.sleep(3);before=lab.b2.state();started=time.time_ns()
   if rate:
    lab.b2.command(f'UDPLOAD {rate} 40 {ident}');time.sleep(2)
    if lab.b2.state()['udp_tx_bytes']-before['udp_tx_bytes']<16384:raise RuntimeError('UDP load absent')
   context=dict(phase='independent_ap_udp',repeat=rep,interferer_channel=ch,requested_width_mhz=width,offered_mbps=rate,udp_run_id=ident,load_started_wall_ns=started,load='UDP offered 20 Mbps' if rate else 'beacons only',traffic_verified_before=bool(rate))
   lab.run_one(name,host,context,lo=2427 if ch==1 else 2442)
   lab.b2.command('UDPLOAD 0 0 0');stopped=time.time_ns();time.sleep(1);after=lab.b2.state()
   p=lab.C/(name+'.json');m=json.loads(p.read_text());m['context'].update(load_stopped_wall_ns=stopped,udp_whole_packets=after['udp_tx_packets']-before['udp_tx_packets'],udp_whole_bytes=after['udp_tx_bytes']-before['udp_tx_bytes']);p.write_text(json.dumps(m,indent=2)+'\n');lab.archive(name)
 SUCCESS=True;print('UDP MATRIX COMPLETE',flush=True)
except Exception:
 (lab.R/'evidence/udp-error.txt').write_text(traceback.format_exc());raise
finally:
 for b in (lab.b1,lab.b2):
  if b:
   try:b.command('STOP');b.close()
   except Exception:pass
 if lab.sdr:
  for c in ('FREQ 2412','BANDWIDTH 0','GAIN HARDWARE'):
   try:lab.sdr.command(c)
   except Exception:pass
  lab.sdr.close()
 end=time.monotonic()+100
 while time.monotonic()<end:
  try:lab.remote('true',timeout=8);break
  except Exception:time.sleep(3)
 try:
  subprocess.run(['scp','-q',*[str(p) for p in lab.C.glob('udp20-*')],lab.SSH[-1]+':'+lab.DEST],check=True,timeout=180)
  subprocess.run(['scp','-q',lab.SSH[-1]+':'+lab.DEST+'udp-rx-*.bin',str(lab.C)],check=True,timeout=60)
 except Exception as e:print('Archive pending',repr(e),flush=True)
 if SUCCESS:Path('/dev/shm/robotics-wifi/network-stop').touch()
