#!/usr/bin/env python3
"""Bounded, reversible robot-laptop Wi-Fi handoff. Run with NM permissions."""
import argparse,os,signal,subprocess
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--interface',required=True);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--seconds',type=int,default=3300);a=p.parse_args()
 name='sdr-team-a-robot';child=None
 def nm(*v,check=True):return subprocess.run(['nmcli',*v],capture_output=True,text=True,timeout=40,check=check)
 active=nm('-t','-f','NAME,DEVICE','con','show','--active').stdout.splitlines()
 original=next(x.rsplit(':',1)[0] for x in active if x.rsplit(':',1)[1]==a.interface)
 try:
  nm('con','delete',name,check=False)
  nm('con','add','type','wifi','ifname',a.interface,'con-name',name,'ssid','ESP-SDR-TEAM-A','wifi-sec.key-mgmt','wpa-psk','wifi-sec.psk','SdrLab2026TestOnly','ipv4.method','manual','ipv4.addresses','192.168.8.20/24','ipv4.never-default','yes','ipv6.method','disabled','connection.autoconnect','yes','connection.autoconnect-priority','999','802-11-wireless.powersave','2')
  nm('con','up',name);env=os.environ.copy();env['TEAM_LAB_TOKEN']=(a.runtime/'token').read_text().strip()
  child=subprocess.Popen(['python3',str(Path(__file__).with_name('team_traffic.py')),'--local','192.168.8.20','--seconds',str(a.seconds)],env=env)
  def stop(*unused):
   if child and child.poll() is None:child.terminate()
  signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
  child.wait(timeout=a.seconds+30)
 finally:
  if child and child.poll() is None:
   child.terminate()
   try:child.wait(timeout=5)
   except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
  nm('con','down',name,check=False);nm('con','delete',name,check=False);nm('con','up',original,check=False)
  print('RESTORED ORIGINAL WIFI',flush=True)

if __name__=='__main__':main()
