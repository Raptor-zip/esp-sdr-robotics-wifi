"""UART command transport; pyserial DTR/RTS held low to avoid unintended reset."""
import json,time,serial
class Board:
 def __init__(self,port,baudrate=115200):
  self.port=serial.Serial();self.port.port=port;self.port.baudrate=baudrate;self.port.timeout=.1;self.port.dtr=False;self.port.rts=False;self.port.open()
  # Some USB bridges reset on open even with explicit DTR/RTS. Wait for boot.
  time.sleep(1.5);self.port.reset_input_buffer()
 def command(self,text,prefix='OK',timeout=8):
  self.port.write((text+'\n').encode());end=time.monotonic()+timeout;seen=[]
  while time.monotonic()<end:
   line=self.port.readline().decode(errors='replace').strip()
   if line.startswith('IP '):self.ip=line.split()[1]
   if line:seen.append(line)
   if line.startswith(prefix):return line
   # ROM boot output can use a different baud rate and lack a final newline.
   # Accept a complete response following those non-text boot bytes.
   offset=line.find(prefix)
   if offset>0 and (line[:offset]=='x' or any(c=='\ufffd' or ord(c)<32 for c in line[:offset])):return line[offset:]
  raise TimeoutError(f'{text}: {seen}')
 def state(self):return json.loads(self.command('STATUS','STATE ').split(' ',1)[1])
 def close(self):self.port.close()
