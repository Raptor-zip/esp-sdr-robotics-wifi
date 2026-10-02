#!/usr/bin/env python3
"""Real blue/green SDR panels and compact robot communication figures."""
import json,os,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
R=Path(__file__).resolve().parents[1];C=R/'data/robotics';F=R/'figures/robotics';F.mkdir(parents=True,exist_ok=True)
S=json.loads((C/'summary.json').read_text())
plt.rcParams.update({'font.family':'Noto Sans CJK JP','font.size':10,'axes.titlesize':12,'pdf.fonttype':42})
CM=LinearSegmentedColormap.from_list('sdr_blue_green',['#071321','#092c70','#075bcc','#008abb','#00bd89','#64ed69'])
def save(fig,name):
 fig.savefig(F/(name+'.pdf'),bbox_inches='tight');fig.savefig(F/(name+'.png'),dpi=220,bbox_inches='tight');plt.close(fig)
def measured(name):
 a=np.load(C/(name+'-spectrum.npz'));m=json.loads((C/(name+'.json')).read_text())
 return a['frequency_mhz'],a['power_dbfs'],m
def panels(cases,name,xlim):
 fig=plt.figure(figsize=(12,6.7),layout='constrained');gs=fig.add_gridspec(3,len(cases),height_ratios=[.5,3,1])
 axes=[]
 for i,(group,label) in enumerate(cases):
  freq,z,a=measured(group+'-r1');m=S[group];run=json.loads((C/(group+'-r1.json')).read_text())
  cx=run['context'];delta=(cx['board_sample_after_ns']-cx['board_sample_before_ns'])/1e9
  field='udp_tx_bytes' if group.startswith('udp20-') else 'tx_bytes';rate=(cx['board2_after'][field]-cx['board2_before'][field])*8/delta/1e6
  top=fig.add_subplot(gs[0,i]);top.axis('off');top.text(.5,.8,label,ha='center',va='center',fontsize=15,weight='bold')
  top.text(.5,.15,f'画像の負荷 {rate:.1f} Mbps / 3反復RTT p99 {m["pooled_p99_ms"]:.1f} ms',ha='center',fontsize=10)
  ax=fig.add_subplot(gs[1,i]);axes.append(ax)
  im=ax.imshow(z,origin='upper',aspect='auto',extent=(freq[0],freq[-1],len(z),0),cmap=CM,vmin=-90,vmax=-45,rasterized=True)
  ax.set(xlim=xlim,ylabel='取得順（各行は約205 µsの間欠取得）' if i==0 else '',xlabel='周波数 [MHz]')
  for edge in (2427,2447):ax.axvline(edge,color='white',ls='--',lw=1,alpha=.85)
  ax.set_xticks(np.arange(xlim[0],xlim[1]+1,20))
  spec=fig.add_subplot(gs[2,i]);spec.plot(freq,10*np.log10(np.maximum(np.mean(10**(z/10),axis=0),1e-16)),color='#167bce')
  spec.axvspan(2427,2447,color='#29b75d',alpha=.12)
  spec.set(xlim=xlim,ylim=(-90,-40),xlabel='周波数 [MHz]',ylabel='平均FFT [dBFS]' if i==0 else '');spec.grid(alpha=.2)
 fig.colorbar(im,ax=axes,shrink=.85,label='FFT bin power [dBFS]：全パネル共通尺度')
 fig.suptitle('操縦リンクはCh6・20 MHzに固定｜白点線はその名目帯域',fontsize=15)
 save(fig,name)
prefix='independent-'
panels([(prefix+'ch6','同一：別AP Ch6'),(prefix+'ch7','隣接：別AP Ch7'),(prefix+'ch11','分離：別AP Ch11')],'robotics-blue-green',(2410,2480))
panels([(prefix+'ch1w20','別AP Ch1：20 MHz'),(prefix+'ch1w40','別AP Ch1：40 MHz')],'robotics-width-blue-green',(2390,2460))
if 'udp20-ch6' in S:
 panels([('udp20-ch6','UDP要求20：別AP Ch6'),('udp20-ch7','UDP要求20：別AP Ch7'),('udp20-ch11','UDP要求20：別AP Ch11')],'robotics-udp-blue-green',(2410,2480))
# Same run choice (r1) and fixed scale for visuals; numerical annotations pool 3 repeats.
for names,labels,name in [(['sameap-load0','sameap-load20','sameap-load60'],['待機','実測20 Mbps','実測38–41 Mbps'],'robotics-control'),([prefix+'ch6',prefix+'ch7',prefix+'ch11',prefix+'ch1w20',prefix+'ch1w40'],['同一Ch6','隣接Ch7','分離Ch11','Ch1/20','Ch1/40'],'robotics-channel-metrics')]:
 fig,ax=plt.subplots(2,1,figsize=(3.65,2.65),layout='constrained',sharex=True)
 for i,n in enumerate(names):
  ax[0].scatter([i]*S[n]['runs'],S[n]['run_p99_ms'],s=16,color='#167bce');ax[0].scatter(i,S[n]['pooled_p99_ms'],marker='_',s=90,color='#d44726')
 ax[0].set(ylabel='RTT p99 [ms]');ax[0].grid(axis='y',alpha=.2)
 ax[1].bar(range(len(names)),[S[n]['deadline20_pct'] for n in names],color='#159b73')
 ax[1].set(ylabel='20 ms超過 [%]');ax[1].set_xticks(range(len(names)),labels,fontsize=8);ax[1].grid(axis='y',alpha=.2)
 save(fig,name)
print('Blue/green panels rendered from measured FFT power; r1 images, pooled metrics.')
