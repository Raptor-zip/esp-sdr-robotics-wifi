#!/usr/bin/env python3
"""Autonomous laptop TCP receiver. Restores original Wi-Fi on exit/lost AP.
No Internet is needed on this laptop while attached to the ESP32 AP.
"""
import os,json,socket,subprocess,time,signal
from pathlib import Path
ORIGINAL_WIFI=os.environ['ESP_SDR_ORIGINAL_WIFI']
ROOT=Path(os.environ.get('ESP_SDR_OUTPUT_ROOT','/tmp/esp-sdr-acquisition'));(ROOT/'evidence').mkdir(parents=True,exist_ok=True)
OUT=ROOT/'evidence/interferer-client.jsonl'
profile='sdr-independent-client';wifi=os.environ.get('ESP_SDR_WIFI_IFACE','wlan0');running=True
def cmd(*args):return subprocess.run(args,text=True,capture_output=True,timeout=15)
def write(**data):
 with OUT.open('a') as f:f.write(json.dumps({'wall_ns':time.time_ns(),**data})+'\n')
def stop(*args):
 global running;running=False
signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
if cmd('nmcli','connection','show',profile).returncode:
 cmd('nmcli','connection','add','type','wifi','ifname',wifi,'con-name',profile,'ssid','ESP-SDR-INTERFERER','wifi-sec.key-mgmt','wpa-psk','wifi-sec.psk','SdrLab2026TestOnly','ipv4.method','auto','ipv6.method','disabled','connection.autoconnect','no')
deadline=time.monotonic()+1500;lost_since=time.monotonic();joined=False
try:
 while running and time.monotonic()<deadline:
  p=cmd('iw','dev',wifi,'link')
  if 'SSID: ESP-SDR-INTERFERER' not in p.stdout:
   if time.monotonic()-lost_since>35:break
   cmd('nmcli','device','wifi','rescan','ifname',wifi)
   cmd('nmcli','--wait','12','connection','up',profile);time.sleep(1);continue
  joined=True;lost_since=time.monotonic();cmd('iw','dev',wifi,'set','power_save','off')
  write(event='link',iw_info=cmd('iw','dev',wifi,'info').stdout,iw_link=p.stdout)
  total=0;start=time.monotonic();last=start;last_bytes=0
  try:
   with socket.create_connection(('192.168.4.1',5002),timeout=4) as s:
    s.settimeout(2)
    s.setsockopt(socket.SOL_SOCKET,socket.SO_KEEPALIVE,1)
    s.setsockopt(socket.IPPROTO_TCP,socket.TCP_KEEPIDLE,3)
    s.setsockopt(socket.IPPROTO_TCP,socket.TCP_KEEPINTVL,1)
    s.setsockopt(socket.IPPROTO_TCP,socket.TCP_KEEPCNT,2)
    while running and time.monotonic()<deadline:
     try:
      data=s.recv(65536)
      if not data:break
      total+=len(data);lost_since=time.monotonic()
     except socket.timeout:
      if 'SSID: ESP-SDR-INTERFERER' not in cmd('iw','dev',wifi,'link').stdout:break
      # Probe the actual TCP endpoint, not only the SSID after an AP restart.
      s.sendall(b'P')
      lost_since=time.monotonic()
     now=time.monotonic()
     if now-last>=1:
      write(event='rx',bytes=total,interval_mbps=(total-last_bytes)*8/(now-last)/1e6,elapsed=now-start)
      last=now;last_bytes=total
  except OSError as e:write(event='socket_error',error=repr(e))
  write(event='session_end',bytes=total,elapsed=time.monotonic()-start)
  time.sleep(.5)
finally:
 write(event='restore')
 cmd('nmcli','connection','down',profile);cmd('nmcli','--wait','12','connection','up',os.environ['ESP_SDR_ORIGINAL_WIFI'])
 cmd('iw','dev',wifi,'set','power_save','off')
