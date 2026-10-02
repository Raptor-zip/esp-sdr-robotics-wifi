#!/usr/bin/env python3
"""Maintain metadata for the desktop-authorized temporary NM AP and restore it."""
import os,subprocess,time,signal
from pathlib import Path
ORIGINAL_WIFI=os.environ['ESP_SDR_ORIGINAL_WIFI']
R=Path(os.environ.get('ESP_SDR_OUTPUT_ROOT','/tmp/esp-sdr-acquisition'));(R/'evidence').mkdir(parents=True,exist_ok=True);C=Path('/dev/shm/robotics-wifi');C.mkdir(parents=True,exist_ok=True)
def cmd(*a,timeout=45):return subprocess.run(a,capture_output=True,text=True,timeout=timeout)
def stop(*a):(C/'network-stop').touch()
signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
try:
 (C/'network-stop').unlink(missing_ok=True);(C/'nm-ap').touch()
 p=cmd('iw','dev',os.environ.get('ESP_SDR_WIFI_IFACE','wlan0'),'info');(R/'evidence/nm-ap-state.txt').write_text(p.stdout+p.stderr)
 (C/'network-ready').write_text('NetworkManager AP ready')
 end=time.monotonic()+3600
 while not (C/'network-stop').exists() and time.monotonic()<end:
  (C/'stations.txt').write_text(cmd('iw','dev',os.environ.get('ESP_SDR_WIFI_IFACE','wlan0'),'station','dump').stdout);time.sleep(2)
finally:
 (C/'network-ready').unlink(missing_ok=True);(C/'nm-ap').unlink(missing_ok=True)
 p=cmd('nmcli','--wait','20','connection','down','sdr-robotics-ap');out=p.stdout+p.stderr
 time.sleep(5);p=cmd('nmcli','--wait','30','connection','up',os.environ['ESP_SDR_ORIGINAL_WIFI']);out+=p.stdout+p.stderr
 (R/'evidence/nm-network-restore.txt').write_text(out)
 if p.returncode==0:cmd('nmcli','connection','delete','sdr-robotics-ap')
 p=cmd('curl','--interface',os.environ.get('ESP_SDR_ETH_IFACE','eth0'),'-sSI','--max-time','10','https://www.google.com');(R/'evidence/internet-after.txt').write_text(p.stdout+p.stderr)
 print('NM cleanup completed; original Wi-Fi return code:',p.returncode,flush=True)
