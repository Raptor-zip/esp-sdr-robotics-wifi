#!/usr/bin/env python3
"""Real FFT waterfalls for periodic Wi-Fi load and independent BLE traffic."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
R=Path(__file__).resolve().parents[1];D=R/'data/two-team';F=R/'figures/two-team'
S=json.loads((D/'summary.json').read_text())
plt.rcParams.update({'font.family':'Noto Sans CJK JP','font.size':10,'pdf.fonttype':42})
CM=LinearSegmentedColormap.from_list('sdr_blue_green',['#071321','#092c70','#075bcc','#008abb','#00bd89','#64ed69'])
def save(fig,name):
 for ext in ('pdf','png'):fig.savefig(F/(name+'.'+ext),bbox_inches='tight',dpi=220)
 plt.close(fig)
def ble():
 cases=[('ble-off-off','Wi-Fi待機 / BLE停止'),('ble-off-advert','Wi-Fi待機 / BLE広告'),('ble-off-data','Wi-Fi待機 / BLE通知'),('ble-heavy-data','Wi-Fi負荷 / BLE通知')]
 if any(k not in S for k,_ in cases):return
 fig,axs=plt.subplots(1,4,figsize=(12,5.8),layout='constrained')
 for i,(k,title) in enumerate(cases):
  z=np.load(D/(k+'-r1-spectrum.npz'));r=json.loads((D/(k+'-r1.json')).read_text());f=z['frequency_mhz'];p=z['power_dbfs'];ax=axs[i]
  im=ax.imshow(p,origin='upper',aspect='auto',extent=(f[0],f[-1],len(p),0),cmap=CM,vmin=-90,vmax=-45,rasterized=True)
  ax.set(xlim=(2410,2480),xlabel='周波数 [MHz]',ylabel='取得順（間欠取得）' if i==0 else '',title=title);ax.set_xticks([2420,2440,2460,2480])
  ax.axvline(2426,color='white',ls=':',lw=.9)
  for edge in (2427,2447):ax.axvline(edge,color='white',ls='--',lw=.8)
  text=f'RTT p99 {S[k]["pooled_p99_ms"]:.1f} ms（{S[k]["runs"]}反復）'
  if k.endswith('advert'):text+=f'\n広告復号 {r["ble_advertisements_received"]} 回（画像の試行）'
  if k.endswith('data'):text+=f'\nBLE受信 {r["other_delivered_mbps"]:.3f} Mbps（画像の試行）'
  ax.text(.5,-.17,text,ha='center',va='top',transform=ax.transAxes,fontsize=9)
 fig.colorbar(im,ax=axs,label='FFT bin power [dBFS]：共通色尺度',shrink=.9)
 fig.suptitle('外部ESP32の独立BLEリンク｜白破線：Wi-Fi Ch6｜白点線：広告2426 MHz',fontsize=12)
 save(fig,'ble-blue-green')
 fig,axs=plt.subplots(1,4,figsize=(12,4.1),layout='constrained')
 for i,(k,title) in enumerate(cases):
  z=np.load(D/(k+'-r1-spectrum.npz'));f=z['frequency_mhz'];p=z['power_dbfs'];ax=axs[i]
  im=ax.imshow(p,origin='upper',aspect='auto',extent=(f[0],f[-1],len(p),0),cmap=CM,vmin=-90,vmax=-60,rasterized=True)
  ax.set(xlim=(2450,2470),xlabel='周波数 [MHz]',ylabel='間欠取得順' if i==0 else '',title=title);ax.set_xticks([2450,2460,2470])
 fig.colorbar(im,ax=axs,label='dBFS（この図の共通尺度）',shrink=.9)
 fig.suptitle('Ch6帯域の上側を拡大｜弱い狭帯域成分を見る別色尺度：−90〜−60 dBFS',fontsize=12)
 save(fig,'ble-narrow-blue-green')
def burst():
 keys=[f'team-heavy-ch{ch}-w20-b2' for ch in (6,7,11)]
 if any(k not in S for k in keys):return
 fig=plt.figure(figsize=(12,6),layout='constrained');gs=fig.add_gridspec(2,3,height_ratios=[3,1.3]);axes=[]
 for i,(ch,k) in enumerate(zip((6,7,11),keys)):
  z=np.load(D/(k+'-r1-spectrum.npz'));r=json.loads((D/(k+'-r1.json')).read_text());ax=fig.add_subplot(gs[0,i]);axes.append(ax);t=z['capture_start_s'];f=z['frequency_mhz'];p=z['power_dbfs']
  im=ax.pcolormesh(f,t,p,cmap=CM,vmin=-90,vmax=-45,shading='nearest',rasterized=True);ax.set(xlim=(2410,2480),ylim=(30,0),xlabel='周波数 [MHz]',ylabel='ホスト取得時刻 [s]' if i==0 else '',title=f'他チームCh{ch}：2 s ON / 2 s OFF')
  for edge in (2427,2447):ax.axvline(edge,color='white',ls='--',lw=.8)
  b=fig.add_subplot(gs[1,i]);a=np.load(D/(k+'-r1-control.npz'));send=a['sent_ns']/1e9;ok=a['received_ns']>=0;rtt=(a['received_ns'][ok]-a['sent_ns'][ok])/1e6;b.scatter(send[ok],rtt,s=.7,c='#167bce',rasterized=True)
  transitions=r['load_transitions']
  for j,x in enumerate(transitions):
   end=transitions[j+1]['before_s'] if j+1<len(transitions) else 30
   if x['on']:
    b.axvspan(x['after_s'],end,color='#26c27a',alpha=.18)
    ax.plot([2478,2478],[x['after_s'],end],color='#96fca5',lw=3)
  b.set(xlim=(0,30),ylim=(0,250),xlabel='コントローラー相対時刻 [s]',ylabel='RTT [ms]' if i==0 else '');b.grid(alpha=.2)
 fig.colorbar(im,ax=axes,label='FFT bin power [dBFS]',shrink=.9)
 fig.suptitle('自チーム大容量通信を維持し、他チームの通常TCP負荷を周期操作｜緑帯：ON操作区間',fontsize=12)
 save(fig,'wifi-burst-blue-green')
 # One condition at readable column width for the three-page paper.
 k=keys[0];z=np.load(D/(k+'-r1-spectrum.npz'));r=json.loads((D/(k+'-r1.json')).read_text());a=np.load(D/(k+'-r1-control.npz'))
 fig,(ax,b)=plt.subplots(2,1,figsize=(4.8,4.2),layout='constrained',gridspec_kw={'height_ratios':[2.5,1]})
 im=ax.pcolormesh(z['frequency_mhz'],z['capture_start_s'],z['power_dbfs'],cmap=CM,vmin=-90,vmax=-45,shading='nearest',rasterized=True)
 ax.set(xlim=(2410,2480),ylim=(30,0),xlabel='周波数 [MHz]',ylabel='取得時刻 [s]',title='同一Ch6：他チームTCPを2 s ON / OFF')
 for edge in (2427,2447):ax.axvline(edge,color='white',ls='--',lw=.8)
 ok=a['received_ns']>=0;b.scatter(a['sent_ns'][ok]/1e9,(a['received_ns'][ok]-a['sent_ns'][ok])/1e6,s=.8,c='#167bce',rasterized=True)
 for j,x in enumerate(r['load_transitions']):
  end=r['load_transitions'][j+1]['before_s'] if j+1<len(r['load_transitions']) else 30
  if x['on']:b.axvspan(x['after_s'],end,color='#26c27a',alpha=.18);ax.plot([2478,2478],[x['after_s'],end],color='#96fca5',lw=3)
 b.set(xlim=(0,30),ylim=(0,250),xlabel='相対時刻 [s]',ylabel='RTT [ms]');b.grid(alpha=.2)
 fig.colorbar(im,ax=ax,label='dBFS',shrink=.8)
 save(fig,'wifi-burst-single')
ble();burst()
