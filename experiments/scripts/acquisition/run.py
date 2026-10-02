#!/usr/bin/env python3
"""Actual UDP/TCP and CRC verified SDR experiments. Network helper owns cleanup."""
import os,datetime,json,random,subprocess,sys,threading,time,traceback
from pathlib import Path
import numpy as np
from board import Board
R=Path(os.environ.get('ESP_SDR_OUTPUT_ROOT','/tmp/esp-sdr-acquisition'));C=R/'data';C.mkdir(parents=True,exist_ok=True);(R/'evidence').mkdir(exist_ok=True)
from timed_capture import TimedReceiver
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=5','-o','ServerAliveInterval=5','-o','ServerAliveCountMax=2',os.environ.get('ESP_SDR_CLIENT_SSH','laptop2')]
DEST=os.environ.get('ESP_SDR_ARCHIVE_DEST','/tmp/esp-sdr-acquisition/data/')
SECONDS=30
b1=b2=sdr=None
OFFLINE_ARCHIVE='--offline-client' in sys.argv or not os.environ.get('ESP_SDR_ARCHIVE_DEST')
SUCCESS=False
def remote(cmd,timeout=25):
 return subprocess.run(SSH+[cmd],text=True,capture_output=True,timeout=timeout,check=True)
def archive(name):
 files=[str(p) for p in C.glob(name+'*')]
 if not OFFLINE_ARCHIVE:subprocess.run(['scp','-q','-o','BatchMode=yes','-o','ConnectTimeout=5',*files,SSH[-1]+':'+DEST],check=True,timeout=90)
 for p in C.glob(name+'*.json'):(R/'evidence'/p.name).write_text(p.read_text())
def sdr_record(name,lo=2437):
 sdr.command(f'FREQ {lo}');sdr.command('BANDWIDTH 48');sdr.command('GAIN MANUAL 20')
 clocks=sdr.clock(16);iq=[];times=[];end=time.monotonic()+SECONDS
 while time.monotonic()<end:
  x,t=sdr.take(0);iq.append(x);times.append(t)
 np.savez_compressed(C/(name+'-iq.npz'),iq=np.stack(iq))
 meta={'lo_mhz':lo,'sample_rate_hz':80000000,'bandwidth_mhz':48,'gain':'MANUAL 20','frames':len(iq),'samples':16380,'clock_before':clocks,'clock_after':sdr.clock(16),'timing':times,'all_crcs_verified':True}
 (C/(name+'-iq.json')).write_text(json.dumps(meta,indent=2))
def wait_board(b,timeout=25):
 end=time.monotonic()+timeout
 while time.monotonic()<end:
  x=b.state()
  if x['connected']:return x
  time.sleep(.5)
 raise TimeoutError('STA did not connect: '+str(x))
def esp_ip():
 if getattr(b1,'ip',None):return b1.ip
 text=Path('/dev/shm/robotics-wifi/stations.txt').read_text()
 # DHCP leases are world-readable in the helper's runtime directory.
 p=Path('/tmp/esp-sdr-dhcp.leases')
 if p.exists():
  for line in p.read_text().splitlines():
   fields=line.split()
   if fields[1].lower()==os.environ['ESP_SDR_CONTROL_MAC'].lower():return fields[2]
 raise RuntimeError('No lease for ESP32-1')
def run_one(name,host,context,video=0,lo=2437):
 if (C/(name+'.json')).exists():print('KEEP',name,flush=True);return
 print('START',name,flush=True);load=None;context=dict(context)
 context.update(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),board1_before=b1.state(),board2_before=b2.state(),board_sample_before_ns=time.monotonic_ns(),board_sample_wall_before_ns=time.time_ns())
 context['stations_before']=Path('/dev/shm/robotics-wifi/stations.txt').read_text()
 context['ap_service']='NetworkManager' if Path('/dev/shm/robotics-wifi/nm-ap').exists() else 'hostapd'
 if video:
  load=subprocess.Popen(SSH+[f'python3 /tmp/sdr-load.py --host 10.78.0.1 --seconds {SECONDS+5} --mbps {video}'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);time.sleep(2)
 worker=subprocess.Popen([sys.executable,str(Path(__file__).with_name('control.py')),'--host',host,'--seconds',str(SECONDS),'--output',str(C/name)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 error=None
 try:sdr_record(name,lo)
 except Exception as e:error=repr(e)
 out,err=worker.communicate(timeout=15)
 if worker.returncode:raise RuntimeError(err)
 result=json.loads((C/(name+'.json')).read_text());context['board1_after']=b1.state();context['board2_after']=b2.state();context['board_sample_after_ns']=time.monotonic_ns();context['board_sample_wall_after_ns']=time.time_ns()
 context['stations_after']=Path('/dev/shm/robotics-wifi/stations.txt').read_text()
 if load:
  o,e=load.communicate(timeout=20);context.update(video_stdout=o,video_stderr=e,video_returncode=load.returncode)
  if load.returncode:raise RuntimeError('video failed: '+e)
 result['context']=context;result['sdr_error']=error
 (C/(name+'.json')).write_text(json.dumps(result,indent=2)+'\n');archive(name)
 print('RESULT',name,'p99',result['rtt_ms']['p99'],'loss',result['loss_pct'],'gap',result['longest_echo_gap_ms'],flush=True)
 if error:raise RuntimeError(error)
def phase_a():
 b2.command('STOP');b1.command('STA ESP-SDR-LAB SdrLab2026TestOnly OFF 20');wait_board(b1);time.sleep(2)
 host=esp_ip()
 for rep in range(1,4):
  levels=[0,20,60];random.Random(2040+rep).shuffle(levels)
  for mbps in levels:
   b1.command('PS 0');run_one(f'sameap-load{mbps}-r{rep}',host,{'phase':'same_ap','video_requested_mbps':mbps,'repeat':rep,'esp_power_save':False},video=mbps)
 for rep in (1,2):
  b1.command('PS 1');run_one(f'sameap-ps-load20-r{rep}',host,{'phase':'same_ap_ps','video_requested_mbps':20,'repeat':rep,'esp_power_save':True},video=20)
 b1.command('PS 0');b1.command('STOP')
def phase_b():
 if OFFLINE_ARCHIVE:return phase_b_robot()
 host=remote('ip -4 -o addr show ${ESP_SDR_WIFI_IFACE:-wlan0}').stdout.split('inet ')[1].split('/')[0]
 cases=[('off',None,20,76),('ch6',6,20,76),('ch7',7,20,76),('ch11',11,20,76),('ch1w20',1,20,76),('ch1w40',1,40,76),('ch7low',7,20,8)]
 for rep in range(1,4):
  order=cases.copy();random.Random(3040+rep).shuffle(order)
  for label,ch,width,power in order:
   b1.command('STOP');b2.command('STOP');time.sleep(1)
   if ch is not None:
    b1.command(f'AP {ch} {width} {power}');time.sleep(.5)
    b2.command(f'STA ESP-SDR-INTERFERER SdrLab2026TestOnly 192.168.4.1 {width}');wait_board(b2);time.sleep(2)
    # Saturating TCP is bounded at 38 seconds; actual received rate is measured.
    b1.command(f'LOAD 1000 {SECONDS+8}');time.sleep(2)
   lo=2427 if ch==1 else 2442
   run_one(f'independent-{label}-r{rep}',host,{'phase':'independent_ap','interferer_channel':ch,'requested_width_mhz':width,'requested_power_qdbm':power,'load':'saturating TCP' if ch else 'off','repeat':rep},lo=lo)
   b1.command('LOAD 0 0');time.sleep(1)
def phase_b_robot():
 b1.command('STA ESP-SDR-LAB SdrLab2026TestOnly OFF 20');wait_board(b1);time.sleep(2);host=esp_ip()
 cases=[('ch11idle',11,20,76,False),('ch6idle',6,20,76,False),('ch7idle',7,20,76,False),('ch6',6,20,76,True),('ch7',7,20,76,True),('ch11',11,20,76,True),('ch1w20',1,20,76,True),('ch1w40',1,40,76,True),('ch7low',7,20,8,True)]
 for rep in range(1,4):
  order=cases.copy();random.Random(4040+rep).shuffle(order)
  for label,ch,width,power,loaded in order:
   b2.command('STOP');time.sleep(1);b2.command(f'AP {ch} {width} {power}')
   end=time.monotonic()+55
   while time.monotonic()<end:
    x=b2.state()
    if x['ap_clients']>=1 and x.get('tcp_connected'):break
    time.sleep(1)
   else:raise TimeoutError('Independent laptop client did not join')
   time.sleep(4)
   if loaded:
    start_bytes=b2.state()['tx_bytes'];b2.command(f'LOAD 1000 {SECONDS+8}');time.sleep(2)
    if b2.state()['tx_bytes']-start_bytes<16384:raise RuntimeError('No actual TCP load after connection handshake')
   lo=2427 if ch==1 else 2442
   run_one(f'independent-{label}-r{rep}',host,{'phase':'independent_ap_robot','interferer_channel':ch,'requested_width_mhz':width,'requested_power_qdbm':power,'load':'saturating TCP' if loaded else 'beacons only; TCP connected without application payload','traffic_verified_before':loaded,'repeat':rep,'control_receiver':'ESP32-1','interferer_ap':'ESP32-2','interferer_client':'Laptop 2'},lo=lo)
   b2.command('LOAD 0 0');time.sleep(1)
def main():
 global b1,b2,sdr,SUCCESS
 if not Path('/dev/shm/robotics-wifi/network-ready').exists():raise RuntimeError('Network helper is not ready')
 b1=Board('/dev/ttyUSB0');b2=Board('/dev/ttyUSB1');sdr=TimedReceiver('/dev/ttyACM0')
 if '--phase-b-only' not in sys.argv:phase_a()
 phase_b()
 SUCCESS=True
 print('ALL EXPERIMENTS FINISHED',flush=True)
if __name__=='__main__':
 try:main()
 except Exception:
  (R/'evidence/error.txt').write_text(traceback.format_exc());raise
 finally:
  for b in (b1,b2):
   if b:
    try:b.command('STOP');b.close()
    except Exception:pass
  if sdr:
   for c in ('FREQ 2412','BANDWIDTH 0','GAIN HARDWARE'):
    try:sdr.command(c)
    except Exception:pass
   sdr.close()
  if OFFLINE_ARCHIVE and os.environ.get('ESP_SDR_ARCHIVE_DEST'):
   # Loss of the independent AP makes its bounded client restore original Wi-Fi.
   deadline=time.monotonic()+100
   while time.monotonic()<deadline:
    try:remote('true',timeout=8);break
    except Exception:time.sleep(3)
   else:print('Client restore not yet reachable; raw remains in RAM',flush=True)
   try:
    subprocess.run(['scp','-q',*[str(p) for p in C.glob('independent-*')],SSH[-1]+':'+DEST],check=True,timeout=180)
   except Exception as e:print('Archive after client restore failed',repr(e),flush=True)
  # Keep the bounded helper alive for acquisition repair; it still has a 70 min limit.
  if SUCCESS or '--stop-network-on-error' in sys.argv:Path('/dev/shm/robotics-wifi/network-stop').touch()
