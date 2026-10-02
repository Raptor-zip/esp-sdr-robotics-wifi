#!/usr/bin/env python3
"""Parse classic PCAP/radiotap headers without inventing missing RF timestamps."""
import collections,struct
from pathlib import Path
# alignment,size for defined fields through timestamp; unknown fields stop parsing.
FIELDS={0:(8,8),1:(1,1),2:(1,1),3:(2,4),4:(2,2),5:(1,1),6:(1,1),7:(2,2),8:(2,2),9:(2,2),10:(1,1),11:(1,1),12:(1,1),13:(1,1),14:(2,2),15:(2,2),16:(1,1),17:(1,1),18:(4,8),19:(1,3),20:(4,8),21:(2,12),22:(8,12),23:(2,12),24:(2,12),26:(1,1),27:(2,4)}
def read(path):
 rows=[]
 with Path(path).open('rb') as f:
  h=f.read(24)
  if len(h)!=24:return rows
  magic=h[:4];order='<' if magic in (b'\xd4\xc3\xb2\xa1',b'\x4d\x3c\xb2\xa1') else '>'
  scale=1e9 if magic in (b'\x4d\x3c\xb2\xa1',b'\xa1\xb2\x3c\x4d') else 1e6
  link=struct.unpack(order+'I',h[20:24])[0]
  if link!=127:raise ValueError(f'Expected radiotap, got PCAP link type {link}')
  while True:
   h=f.read(16)
   if len(h)<16:break
   sec,frac,size,wire=struct.unpack(order+'IIII',h);p=f.read(size)
   if len(p)<size:break
   if len(p)<8:continue
   length=struct.unpack_from('<H',p,2)[0];offset=4;present=[]
   while True:
    if offset+4>length:break
    word=struct.unpack_from('<I',p,offset)[0];present.append(word);offset+=4
    if not word&(1<<31):break
   r={'epoch':sec+frac/scale,'wire_length':wire,'type':None,'tsft_us':None,'radiotap_timestamp':None,'rate_mbps':None,'signal_dbm':None,'tx':False,'bssid':None,'beacon_tsf_us':None,'frequency_mhz':None}
   for k in range(29):
    if not present or not(present[0]&(1<<k)):continue
    if k not in FIELDS:break
    align,n=FIELDS[k];offset=(offset+align-1)//align*align
    if offset+n>length:break
    if k==0:r['tsft_us']=struct.unpack_from('<Q',p,offset)[0]
    elif k==2:r['rate_mbps']=p[offset]/2
    elif k==3:r['frequency_mhz']=struct.unpack_from('<H',p,offset)[0]
    elif k==5:r['signal_dbm']=struct.unpack_from('b',p,offset)[0]
    elif k==15:r['tx']=True
    elif k==22:r['radiotap_timestamp']=struct.unpack_from('<QHBB',p,offset)
    offset+=n
   packet=p[length:]
   if len(packet)>=2:
    fc=struct.unpack_from('<H',packet)[0];r['type']=(fc>>2)&3;r['subtype']=(fc>>4)&15
    if len(packet)>=24:
     r['addr1']=packet[4:10].hex(':');r['addr2']=packet[10:16].hex(':');r['addr3']=packet[16:22].hex(':')
     if r['type']==0:r['bssid']=r['addr3']
     if r['type']==0 and r['subtype']==8 and len(packet)>=36:
      r['beacon_tsf_us']=struct.unpack_from('<Q',packet,24)[0];r['beacon_tu']=struct.unpack_from('<H',packet,32)[0]
   rows.append(r)
 return rows
if __name__=='__main__':
 import sys,json
 r=read(sys.argv[1]);print(json.dumps({'packets':len(r),'types':dict(collections.Counter(f"{x.get('type')}/{x.get('subtype')}" for x in r)),'tsft':sum(x['tsft_us'] is not None for x in r),'tx':sum(x['tx'] for x in r),'examples':r[:3]},default=str,indent=2))
