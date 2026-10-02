#!/usr/bin/env python3
"""ESP-NOW/Wi-Fi channel comparison using captured FFT power."""
import json
from pathlib import Path
import numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
R=Path(__file__).resolve().parents[1];D=R/'data/espnow';F=R/'figures/espnow';F.mkdir(exist_ok=True);S=json.loads((D/'summary.json').read_text())
plt.rcParams.update({'font.family':'Noto Sans CJK JP','font.size':10,'pdf.fonttype':42})
CM=LinearSegmentedColormap.from_list('sdr_blue_green',['#071321','#092c70','#075bcc','#008abb','#00bd89','#64ed69'])
def plot(cases,name,size):
 fig,axs=plt.subplots(1,len(cases),figsize=size,layout='constrained')
 for i,(k,label) in enumerate(cases):
  run=k if k.endswith(('-r1','-r2','-r3')) else k+'-r1'
  group=run.rsplit('-r',1)[0]
  z=np.load(D/(run+'-spectrum.npz'));f=z['frequency_mhz'];p=z['power_dbfs'];ax=axs[i];s=S[group]
  im=ax.imshow(p,origin='upper',aspect='auto',extent=(f[0],f[-1],len(p),0),cmap=CM,vmin=-90,vmax=-45,rasterized=True)
  ax.set(xlim=(2410,2480),title=label,xlabel='周波数 [MHz]',ylabel='間欠取得順' if i==0 else '');ax.set_xticks([2420,2440,2460,2480])
  for edge in (2427,2447):ax.axvline(edge,color='white',ls='--',lw=.8)
  if len(cases)>2:ax.text(.5,-.17,f'RTT p99 {s["pooled_p99_ms"]:.1f} ms\n20 ms超過 {s["deadline20_pct"]:.1f}%（{s["runs"]}反復）',ha='center',va='top',transform=ax.transAxes,fontsize=9)
 fig.colorbar(im,ax=axs,label='dBFS',shrink=.85)
 if len(cases)>2:fig.suptitle('ESP-NOW：64 B / 100 Hz / unicast 1 Mbps｜Wi-Fi：Ch6 / 20 MHz TCP｜白破線：Wi-Fi名目帯域',fontsize=12)
 for ext in ('pdf','png'):fig.savefig(F/(name+'.'+ext),dpi=220,bbox_inches='tight')
 plt.close(fig)
plot([('espnow-off-ch6','Wi-Fi待機 / ESP-NOW Ch6'),('espnow-heavy-ch6','同一：ESP-NOW Ch6'),('espnow-heavy-ch7','隣接：ESP-NOW Ch7'),('espnow-heavy-ch11','分離：ESP-NOW Ch11')],'espnow-blue-green',(12,5.4))
plot([(f'espnow-heavy-ch6-r{i}',f'反復{i} / p99 {S["espnow-heavy-ch6"]["run_p99_ms"][i-1]:.1f} ms') for i in (1,3)],'espnow-compact',(6.6,3.2))

# Show every repeat of the condition with the largest change, including the
# middle repeat; the compact version explicitly selects repeats 1 and 3.
fig,axs=plt.subplots(2,3,figsize=(12,6.8),layout='constrained')
for i in range(3):
 run=f'espnow-heavy-ch6-r{i+1}'
 z=np.load(D/(run+'-spectrum.npz'));f=z['frequency_mhz'];p=z['power_dbfs']
 m=json.loads((D/(run+'.json')).read_text())
 im=axs[0,i].imshow(p,origin='upper',aspect='auto',extent=(f[0],f[-1],len(p),0),cmap=CM,vmin=-90,vmax=-45,rasterized=True)
 axs[0,i].set(xlim=(2410,2480),title=f'反復{i+1} / Wi-Fi実受信 {m["wifi_delivered_mbps"]:.2f} Mbps',xlabel='周波数 [MHz]',ylabel='間欠取得順' if i==0 else '')
 for edge in (2427,2447):axs[0,i].axvline(edge,color='white',ls='--',lw=.8)
 c=np.load(D/(run+'-control.npz'));sent=c['sent_ns'];received=c['received_ns'];ok=received>=0
 axs[1,i].scatter(sent[ok]/1e9,(received[ok]-sent[ok])/1e6,s=3,color='#087c86',rasterized=True)
 axs[1,i].axhline(20,color='#c03c35',ls='--',lw=1)
 axs[1,i].set(xlim=(0,30),ylim=(0,160),xlabel='送信開始から [s]',ylabel='応答RTT [ms]' if i==0 else '',title=f'p99 {m["rtt_ms"]["p99"]:.1f} ms / 20 ms超過 {m["missed_deadline_pct"]["20"]:.1f}%')
 axs[1,i].grid(alpha=.2)
fig.colorbar(im,ax=axs[0,:],label='dBFS',shrink=.85)
fig.suptitle('同じCh6・Wi-Fi負荷条件の3反復：設定を固定しても遅延は変わる',fontsize=13)
for ext in ('pdf','png'):fig.savefig(F/('espnow-repeat-variation.'+ext),dpi=220,bbox_inches='tight')
plt.close(fig)
