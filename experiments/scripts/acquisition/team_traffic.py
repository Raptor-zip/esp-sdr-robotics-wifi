#!/usr/bin/env python3
"""Bounded robot-side UDP echo + camera/cloud-sized TCP traffic through the AP.
This is an application-load emulator, not ROS 2 or a real sensor stream.
"""
import argparse,json,os,select,socket,subprocess,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
class Traffic:
 def __init__(self,local):
  self.local=local;self.stop=threading.Event();self.lock=threading.Lock();self.run_id=0;self.level='off';self.until=0;self.start=0;self.bytes=0;self.frames=0;self.connected=False;self.echoes=0
 def configure(self,run_id,level,seconds):
  if level not in ('off','medium','heavy'):raise ValueError('invalid load')
  with self.lock:self.run_id=int(run_id);self.level=level;self.until=time.monotonic()+seconds;self.start=time.monotonic();self.bytes=0;self.frames=0
  return self.snapshot()
 def snapshot(self):
  with self.lock:return dict(run_id=self.run_id,level=self.level,sent_payload_bytes=[self.bytes,0],sent_messages=[self.frames,0],tcp_connected=self.connected,echoes=self.echoes,monotonic_ns=time.monotonic_ns(),wall_ns=time.time_ns(),semantics='UDP echo and paced synthetic TCP payload; not ROS 2')
 def echo(self):
  s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.bind((self.local,5140));s.settimeout(.2)
  while not self.stop.is_set():
   try:data,peer=s.recvfrom(2048);s.sendto(data,peer);self.echoes+=1
   except socket.timeout:pass
  s.close()
 def sender(self):
  listener=socket.socket();listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);listener.bind((self.local,5003));listener.listen(1);listener.settimeout(.3);payload=bytes([0x5a])*8192
  while not self.stop.is_set():
   try:s,_=listener.accept()
   except socket.timeout:continue
   s.setblocking(False);s.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1);s.setsockopt(socket.SOL_SOCKET,socket.SO_SNDBUF,32768);self.connected=True
   try:
    while not self.stop.is_set():
     with self.lock:
      now=time.monotonic();frame={'off':0,'medium':98304,'heavy':196608}[self.level] if now<self.until else 0
      budget=max(0,int((now-self.start)*10+1)*frame-self.bytes)
      generation=self.run_id
     if budget:
      if not select.select([], [s], [], .01)[1]:continue
      try:n=s.send(payload[:min(budget,len(payload))])
      except BlockingIOError:continue
      with self.lock:
       if generation==self.run_id:self.bytes+=n;self.frames=self.bytes//max(1,frame)
     else:time.sleep(.001)
   except OSError:pass
   finally:self.connected=False;s.close()
  listener.close()
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def respond(self,x,status=200):
  b=json.dumps(x).encode();self.send_response(status);self.send_header('Content-Length',str(len(b)));self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b)
 def auth(self):return self.headers.get('X-Lab-Token')==self.server.token
 def do_GET(self):
  if not self.auth():self.respond({'error':'unauthorized'},403);return
  if self.path=='/diagnostics':self.respond({k:subprocess.run(cmd,capture_output=True,text=True,timeout=3).stdout for k,cmd in {'power_save':['iw','dev','wlp2s0','get','power_save'],'link':['iw','dev','wlp2s0','link']}.items()})
  else:self.respond(self.server.node.snapshot())
 def do_POST(self):
  if not self.auth():self.respond({'error':'unauthorized'},403);return
  try:
   a=json.loads(self.rfile.read(min(4096,int(self.headers.get('Content-Length','0')))))
   if self.path=='/configure':self.respond(self.server.node.configure(a['run_id'],a['level'],max(0,min(float(a['seconds']),90))))
   elif self.path=='/stop':self.respond({'stopping':True});self.server.node.stop.set()
   else:self.respond({'error':'unknown request'},404)
  except Exception as e:self.respond({'error':repr(e)},400)
def main():
 p=argparse.ArgumentParser();p.add_argument('--local',default='192.168.8.20');p.add_argument('--seconds',type=float,default=3300);a=p.parse_args();n=Traffic(a.local)
 server=ThreadingHTTPServer((a.local,8134),Handler);server.daemon_threads=True;server.node=n;server.token=os.environ['TEAM_LAB_TOKEN']
 for target in (n.echo,n.sender,server.serve_forever):threading.Thread(target=target,daemon=True).start()
 print('READY UDP/TCP ROBOT',flush=True);n.stop.wait(a.seconds);n.stop.set();server.shutdown();server.server_close()
if __name__=='__main__':main()
