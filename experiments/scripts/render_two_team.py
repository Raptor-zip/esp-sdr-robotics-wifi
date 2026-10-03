#!/usr/bin/env python3
"""Figures for simultaneously loaded Wi-Fi teams, using measured FFT and UDP/TCP."""
import json
import sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyBboxPatch
R=Path(__file__).resolve().parents[1];D=R/'data/two-team';F=R/'figures/two-team';F.mkdir(parents=True,exist_ok=True)
S=json.loads((D/'summary.json').read_text())
plt.rcParams.update({'font.family':'Noto Sans CJK JP','font.size':10,'pdf.fonttype':42})
CM=LinearSegmentedColormap.from_list('sdr_blue_green',['#071321','#092c70','#075bcc','#008abb','#00bd89','#64ed69'])
def save(fig,name):
 for ext in ('pdf','png'):fig.savefig(F/(name+'.'+ext),bbox_inches='tight',dpi=220)
 plt.close(fig)
def panel(cases,name,xlim,compact=False):
 fig=plt.figure(figsize=(12,3 if compact else 6.5),layout='constrained');gs=fig.add_gridspec(2 if compact else 3,len(cases),height_ratios=[.85,2.4] if compact else [.65,3,1]);axs=[]
 for i,(key,title) in enumerate(cases):
  a=np.load(D/(key+'-r1-spectrum.npz'));f=a['frequency_mhz'];z=a['power_dbfs'];s=S[key];r=json.loads((D/(key+'-r1.json')).read_text());own=sum(r['delivered_payload_mbps']);other=r['other_delivered_mbps']
  top=fig.add_subplot(gs[0,i]);top.axis('off');top.text(.5,.83,title,ha='center',fontsize=14,weight='bold');top.text(.5,.37,f'自 {own:.2f} / 他 {other:.2f} Mbps（画像の試行）',ha='center',fontsize=9);top.text(.5,0,f'{s["runs"]}反復 RTT p99 {s["pooled_p99_ms"]:.1f} ms',ha='center',fontsize=10)
  ax=fig.add_subplot(gs[1,i]);axs.append(ax);im=ax.imshow(z,origin='upper',aspect='auto',extent=(f[0],f[-1],len(z),0),cmap=CM,vmin=-90,vmax=-45,rasterized=True)
  ax.set(xlim=xlim,xlabel='周波数 [MHz]',ylabel='取得順（間欠取得）' if i==0 else '');ax.set_xticks(np.arange(xlim[0],xlim[1]+1,20))
  for edge in (2427,2447):ax.axvline(edge,color='white',ls='--',lw=.9)
  if not compact:
   b=fig.add_subplot(gs[2,i]);mean=10*np.log10(np.maximum(np.mean(10**(z/10),axis=0),1e-16));b.plot(f,mean,color='#167bce',lw=1);b.axvspan(2427,2447,color='#29b75d',alpha=.12);b.set(xlim=xlim,ylim=(-90,-40),xlabel='周波数 [MHz]',ylabel='平均FFT [dBFS]' if i==0 else '');b.grid(alpha=.2)
 fig.colorbar(im,ax=axs,label='FFT bin power [dBFS]：共通色尺度',shrink=.9)
 fig.suptitle('自チーム：Ch6 / 20 MHz / 大容量TCP＋100 Hz UDP操縦｜白点線：自チーム名目帯域',fontsize=12)
 save(fig,name)
base='team-heavy-'
if '--compact-only' in sys.argv:
 panel([(base+'ch7-w20-b0','他チーム待機（Ch7）'),(base+'ch6-w20-b1','両チーム：同一Ch6'),(base+'ch7-w20-b1','両チーム：隣接Ch7'),(base+'ch11-w20-b1','両チーム：分離Ch11')],'two-team-blue-green-compact',(2410,2480),True)
 raise SystemExit(0)
panel([(base+'ch7-w20-b0','他チーム待機（Ch7）'),(base+'ch6-w20-b1','両チーム：同一Ch6'),(base+'ch7-w20-b1','両チーム：隣接Ch7'),(base+'ch11-w20-b1','両チーム：分離Ch11')],'two-team-blue-green',(2410,2480))
panel([(base+'ch7-w20-b0','他チーム待機（Ch7）'),(base+'ch6-w20-b1','両チーム：同一Ch6'),(base+'ch7-w20-b1','両チーム：隣接Ch7'),(base+'ch11-w20-b1','両チーム：分離Ch11')],'two-team-blue-green-compact',(2410,2480),True)
panel([(base+'ch1-w20-b1','両チーム：Ch1 / 20 MHz'),(base+'ch1-w40-b1','両チーム：Ch1 / 40 MHz')],'two-team-width',(2390,2460))
# Interaction: compare B on/off at each channel for both A load states.
fig,axes=plt.subplots(2,2,figsize=(11,6),layout='constrained')
for row,own in enumerate(('off','heavy')):
 for i,ch in enumerate((6,7,11)):
  for j,b in enumerate((0,1)):
   k=f'team-{own}-ch{ch}-w20-b{b}';s=S[k];x=i+(j-.5)*.22;color=('#167bce','#159b73')[j]
   axes[row,0].scatter([x]*s['runs'],s['run_p99_ms'],color=color,s=24,label=('他チーム待機','他チーム負荷')[j] if i==0 else None)
   axes[row,0].scatter(x,s['pooled_p99_ms'],marker='_',s=180,color=color)
   axes[row,1].bar(x,s['deadline20_pct'],width=.2,color=color)
 for ax in axes[row]:ax.set_xticks(range(3),['同一Ch6','隣接Ch7','分離Ch11']);ax.grid(axis='y',alpha=.2)
 axes[row,0].set(ylabel='操縦RTT p99 [ms]',title='自チーム：'+('操縦のみ' if own=='off' else '操縦＋大容量TCP'));axes[row,1].set(ylabel='20 ms期限超過 [%]',title='欠落を含む');axes[row,0].legend(fontsize=8)
save(fig,'two-team-interaction')
# Network architecture diagram: real endpoints and dedicated AP.
fig,ax=plt.subplots(figsize=(10,4.2));ax.set(xlim=(0,10),ylim=(0,4.2));ax.axis('off')
def box(x,y,w,h,label,color):
 ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.05',ec=color,fc='#f4f8fa',lw=1.5));ax.text(x+w/2,y+h/2,label,ha='center',va='center',fontsize=10)
box(.2,2.7,2.5,1,'ESP32-3\nコントローラー役\nUDP往復＋TCP受信','#167bce')
box(3.6,2.7,2.6,1,'観測PC（Intel BE200）\n自チームAP：Ch6 / 20 MHz\n2つのSTA間を転送','#167bce')
box(7.1,2.7,2.7,1,'ラップトップ2（MT7921E）\nロボットPC役\nTCPデータを送信','#167bce')
for x,y in ((2.7,3.6),(6.2,7.1)):ax.annotate('',xy=(y,3.2),xytext=(x,3.2),arrowprops=dict(arrowstyle='<->',color='#167bce',lw=1.5))
ax.text(5,2.35,'指令・応答：64 B / 100 Hz / UDP\nカメラ・点群相当：合計192 KiB / 10 Hz / TCP（模擬負荷）',ha='center',va='center',fontsize=10)
box(.9,.35,3.1,.8,'ESP32-2：他チームAP\nCh6 / Ch7 / Ch11 / Ch1','#159b73');box(6,.35,3.1,.8,'ESP32-1：他チームSTA\n飽和TCP負荷を受信','#159b73')
ax.annotate('実測受信量を記録',xy=(6,.75),xytext=(4,.75),ha='left',arrowprops=dict(arrowstyle='->',color='#159b73'),fontsize=9)
ax.text(5,1.55,'ESP32-C5：両チームのRFを同時に間欠観測',ha='center',fontsize=11,weight='bold')
save(fig,'two-team-setup')
fig,axes=plt.subplots(1,2,figsize=(6.6,3.2),layout='constrained')
for ax,w in zip(axes,(20,40)):
 z=np.load(D/f'team-heavy-ch1-w{w}-b1-r1-spectrum.npz');f=z['frequency_mhz'];p=z['power_dbfs']
 im=ax.imshow(p,origin='upper',aspect='auto',extent=(f[0],f[-1],len(p),0),cmap=CM,vmin=-90,vmax=-45,rasterized=True)
 ax.set(xlim=(2400,2450),title=f'他チームCh1 / {w} MHz',xlabel='周波数 [MHz]');ax.set_xticks([2400,2420,2440])
 for edge in (2427,2447):ax.axvline(edge,color='white',ls='--',lw=.8)
axes[0].set_ylabel('間欠取得順');fig.colorbar(im,ax=axes,label='dBFS',shrink=.8);save(fig,'two-team-width-compact')
fig,ax=plt.subplots(figsize=(5.2,2.5));ax.set(xlim=(0,10),ylim=(0,4.2));ax.axis('off')
box(.1,2.7,2.6,1,'ESP32-3\n操縦役','#167bce');box(3.5,2.7,2.8,1,'観測PC\nAP Ch6','#167bce');box(7.1,2.7,2.8,1,'ラップトップ2\nロボット役','#167bce')
for x,y in ((2.7,3.5),(6.3,7.1)):ax.annotate('',xy=(y,3.2),xytext=(x,3.2),arrowprops=dict(arrowstyle='<->',color='#167bce'))
ax.text(5,2.25,'UDP操縦とTCP模擬データをAPで中継',ha='center',fontsize=10)
box(.5,.45,3.6,1,'ESP32-2：別AP\nCh6 / Ch7 / Ch11','#159b73');box(6,.45,3.6,1,'ESP32-1：受信\n別チームTCP','#159b73')
ax.annotate('',xy=(6,.95),xytext=(4.1,.95),arrowprops=dict(arrowstyle='->',color='#159b73'));ax.text(5,1.7,'C5で両チームを観測',ha='center',fontsize=10)
save(fig,'two-team-setup-compact')
print('Two-team figures rendered from actual measurements.')
