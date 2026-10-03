#!/usr/bin/env python3
"""Bounded, reversible robot-laptop Wi-Fi handoff. Run with NM permissions."""
import argparse,os,signal,subprocess
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--interface',required=True);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--seconds',type=int,default=3300);p.add_argument('--helper',choices=['operational_traffic.py','ros2_robot.py'],default='operational_traffic.py');a=p.parse_args()
 name='sdr-team-a-robot';child=None
 def nm(*v,check=True):return subprocess.run(['nmcli',*v],capture_output=True,text=True,timeout=40,check=check)
 active=nm('-t','-f','NAME,DEVICE','con','show','--active').stdout.splitlines()
 original=next(x.rsplit(':',1)[0] for x in active if x.rsplit(':',1)[1]==a.interface)
 power_readback=subprocess.run(['iw','dev',a.interface,'get','power_save'],capture_output=True,text=True,timeout=5)
 original_power=power_readback.stdout.strip().lower().removeprefix('power save: ').strip()
 if power_readback.returncode or original_power not in ('on','off'):original_power=None
 try:
  nm('con','delete',name,check=False)
  nm('con','add','type','wifi','ifname',a.interface,'con-name',name,'ssid','ESP-SDR-TEAM-A','wifi-sec.key-mgmt','wpa-psk','wifi-sec.psk','SdrLab2026TestOnly','ipv4.method','manual','ipv4.addresses','192.168.8.20/24','ipv4.never-default','yes','ipv6.method','disabled','connection.autoconnect','yes','connection.autoconnect-priority','999','802-11-wireless.powersave','2')
  nm('con','up',name);env=os.environ.copy();env['TEAM_LAB_TOKEN']=(a.runtime/'token').read_text().strip()
  child=subprocess.Popen(['python3',str(Path(__file__).with_name(a.helper)),'--local','192.168.8.20','--seconds',str(a.seconds)],env=env)
  def stop(*unused):
   if child and child.poll() is None:child.terminate()
  signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
  child.wait(timeout=a.seconds+30)
 finally:
  if child and child.poll() is None:
   child.terminate()
   try:child.wait(timeout=5)
   except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
  nm('con','down',name,check=False);nm('con','delete',name,check=False);restored=nm('con','up',original,check=False)
  if restored.returncode:raise RuntimeError('Original Wi-Fi restoration failed: '+restored.stderr)
  if original_power:
   subprocess.run(['iw','dev',a.interface,'set','power_save',original_power],check=True,capture_output=True,text=True,timeout=5)
  print('RESTORED ORIGINAL WIFI; ORIGINAL POWER SAVE',original_power,flush=True)

if __name__=='__main__':main()
