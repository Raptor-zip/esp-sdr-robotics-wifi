#!/usr/bin/env python3
"""Bounded autonomous UDP receiver, with per-datagram sequence evidence."""
import os,json,socket,struct,subprocess,time,signal
from pathlib import Path
ORIGINAL_WIFI=os.environ['ESP_SDR_ORIGINAL_WIFI']
ROOT=Path(os.environ.get('ESP_SDR_OUTPUT_ROOT','/tmp/esp-sdr-acquisition'));(ROOT/'evidence').mkdir(parents=True,exist_ok=True);(ROOT/'data').mkdir(exist_ok=True)
OUT=ROOT/'evidence/udp-client.jsonl';running=True
profile='sdr-independent-client';wifi=os.environ.get('ESP_SDR_WIFI_IFACE','wlan0')
def cmd(*a):return subprocess.run(a,text=True,capture_output=True,timeout=18)
def log(**x):
 with OUT.open('a') as f:f.write(json.dumps(dict(wall_ns=time.time_ns(),**x))+'\n')
def stop(*a):
 global running;running=False
signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
if cmd('nmcli','connection','show',profile).returncode:
 cmd('nmcli','connection','add','type','wifi','ifname',wifi,'con-name',profile,'ssid','ESP-SDR-INTERFERER','wifi-sec.key-mgmt','wpa-psk','wifi-sec.psk','SdrLab2026TestOnly','ipv4.method','auto','ipv6.method','disabled','connection.autoconnect','no')
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,8*1024*1024)
try:s.setsockopt(socket.SOL_SOCKET,33,8*1024*1024)
except OSError:pass
try:s.setsockopt(socket.SOL_SOCKET,40,1)
except OSError:pass
s.bind(('',5003));s.settimeout(.15)
log(event='start',rcvbuf=s.getsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF))
files={};counts={};last_link=0;last_ready=0;lost=time.monotonic();deadline=lost+1500
try:
 while running and time.monotonic()<deadline:
  now=time.monotonic()
  if now-last_link>2:
   p=cmd('iw','dev',wifi,'link');last_link=now
   if 'SSID: ESP-SDR-INTERFERER' not in p.stdout:
    if now-lost>35:break
    cmd('nmcli','device','wifi','rescan','ifname',wifi)
    cmd('nmcli','--wait','12','connection','up',profile)
    last_link=0;continue
   lost=now;cmd('iw','dev',wifi,'set','power_save','off')
   log(event='link',iw_link=p.stdout,iw_info=cmd('iw','dev',wifi,'info').stdout)
  if now-last_ready>1:
   try:s.sendto(b'C5READY',('192.168.4.1',5003))
   except OSError:pass
   last_ready=now
  try:data,anc,flags,peer=s.recvmsg(2048,256)
  except (socket.timeout,OSError):continue
  wall=time.time_ns()
  if len(data)!=1400:continue
  magic,ident,seq,device_us=struct.unpack('!IIII',data[:16])
  if magic!=0x43355246:continue
  if ident not in files:
   files[ident]=(ROOT/'data'/f'udp-rx-{ident}.bin').open('wb',buffering=1024*1024);counts[ident]=0
   log(event='first',run_id=ident,peer=peer)
  files[ident].write(struct.pack('<IIQ',seq,device_us,wall));counts[ident]+=1
  for level,typ,value in anc:
   if level==socket.SOL_SOCKET and typ==40:log(event='kernel_drop',cumulative=struct.unpack('I',value)[0])
finally:
 for f in files.values():f.close()
 log(event='finish',counts=counts)
 s.close();cmd('nmcli','connection','down',profile)
 log(event='restore',result=cmd('nmcli','--wait','20','connection','up',os.environ['ESP_SDR_ORIGINAL_WIFI']).stdout)
 cmd('iw','dev',wifi,'set','power_save','off')
