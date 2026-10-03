#!/usr/bin/env python3
"""Measured control quality versus offered rate / periodic generation."""
import argparse,json
from pathlib import Path
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
R=Path(__file__).resolve().parents[1]
plt.rcParams.update({'font.family':'Noto Sans CJK JP','font.size':10,'pdf.fonttype':42})
CM=LinearSegmentedColormap.from_list('sdr_blue_green',['#071321','#092c70','#075bcc','#008abb','#00bd89','#64ed69'])
COL={6:'#da5844',7:'#be892a',11:'#087bad'}
def rtt_label(row):
 value=row['rtt_ms']['p99'];return '応答なし' if value is None else f'p99 {value:.1f} ms'
def save(fig,F,name):
 for ext in ('pdf','png'):fig.savefig(F/(name+'.'+ext),dpi=220,bbox_inches='tight')
 plt.close(fig)

def main():
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['limit','shape'],required=True);a=p.parse_args();D=R/'data/operational'/a.mode;F=R/'figures/operational';F.mkdir(parents=True,exist_ok=True);S=json.loads((D/'summary.json').read_text())
 if a.mode=='limit':
  fig,axs=plt.subplots(1,4,figsize=(14,3.8),layout='constrained')
  for ch in (6,7,11):
   ss=sorted([s for s in S.values() if s['condition']['other_channel']==ch],key=lambda s:s['condition']['requested_mbps']);rates=[s['condition']['requested_mbps'] for s in ss]
   for ax,field,values in [(axs[0],'run_p99_ms',[s['pooled_p99_ms'] for s in ss]),(axs[1],'run_deadline20_pct',[s['deadline20_pct'] for s in ss]),(axs[2],'delivered_own_mbps',[np.mean(s['delivered_own_mbps']) for s in ss]),(axs[3],'delivered_other_mbps',[np.mean(s['delivered_other_mbps']) for s in ss])]:
    ax.plot(rates,values,'o-',color=COL[ch],label=f'他チーム Ch{ch}')
    for rate,s in zip(rates,ss):ax.scatter([rate]*s['runs'],s[field],s=18,color=COL[ch],alpha=.45)
   for ax in axs:ax.set(xlabel='自チーム要求TCP [Mbps]');ax.grid(alpha=.2)
  axs[0].set(ylabel='応答RTT p99 [ms]',yscale='log');axs[1].set(ylabel='20 ms期限超過 [%]',ylim=(0,100));axs[2].set(ylabel='自チーム実受信 [Mbps]');axs[2].plot([0,2],[0,2],'k--',alpha=.5,label='要求と実受信が一致');axs[2].legend(fontsize=8)
  axs[3].set(ylabel='他チーム実受信 [Mbps]')
  zeros=sum(len(s['other_zero_delivery_runs']) for s in S.values())
  axs[0].legend(fontsize=9);fig.suptitle(f'TCP流量制限：他チームに飽和TCPを要求（実受信0は{zeros}試行）｜大きい点は統合値、小さい点は各反復',fontsize=11);save(fig,F,'rate-limit-metrics')
  selected=[]
  for rate in (0,.5,2):
   ss=[(k,s) for k,s in S.items() if s['condition']['other_channel']==6 and s['condition']['requested_mbps']==rate]
   if ss:selected.append(ss[0])
  if selected:
   fig,axs=plt.subplots(1,len(selected),figsize=(10,4),layout='constrained',squeeze=False)
   for i,(k,s) in enumerate(selected):
    z=np.load(D/(k+'-r1-spectrum.npz'));f=z['frequency_mhz'];power=z['power_dbfs'];m=json.loads((D/(k+'-r1.json')).read_text());ax=axs[0,i]
    im=ax.imshow(power,origin='upper',aspect='auto',extent=(f[0],f[-1],len(power),0),cmap=CM,vmin=-90,vmax=-45,rasterized=True)
    ax.set(xlim=(2410,2480),title=f'要求 {s["condition"]["requested_mbps"]:g} Mbps\n実受信 {m["delivered_payload_mbps"][0]:.2f} Mbps / {rtt_label(m)}',xlabel='周波数 [MHz]',ylabel='間欠取得順' if i==0 else '')
    for edge in (2427,2447):ax.axvline(edge,color='white',ls='--',lw=.8)
   fig.colorbar(im,ax=axs.ravel().tolist(),label='dBFS',shrink=.8);fig.suptitle('自チームCh6・他チームCh6負荷：流量別の反復1、共通ゲイン・色尺度',fontsize=12);save(fig,F,'rate-limit-blue-green')
 else:
  fig,axs=plt.subplots(1,3,figsize=(12,4),layout='constrained')
  for ch in (6,7,11):
   for rate,ls in [(.5,'-'),(1,'--')]:
    ss=sorted([s for s in S.values() if s['condition']['other_channel']==ch and s['condition']['requested_mbps']==rate],key=lambda s:s['condition']['generation_period_ms'])
    if len(ss)!=2:continue
    x=[s['condition']['generation_period_ms'] for s in ss]
    for ax,field,v in [(axs[0],'run_p99_ms',[s['pooled_p99_ms'] for s in ss]),(axs[1],'run_deadline20_pct',[s['deadline20_pct'] for s in ss]),(axs[2],'delivered_own_mbps',[np.mean(s['delivered_own_mbps']) for s in ss])]:
     ax.plot(x,v,marker='o',ls=ls,color=COL[ch],label=f'Ch{ch} / {rate:g} Mbps')
     for xx,s in zip(x,ss):ax.scatter([xx]*s['runs'],s[field],s=15,alpha=.4,color=COL[ch])
  for ax in axs:ax.set(xlabel='TCP byte生成周期 [ms]',xscale='log',xticks=[10,100],xticklabels=['10（平滑化）','100（バースト）']);ax.grid(alpha=.2)
  axs[0].set(ylabel='応答RTT p99 [ms]',yscale='log');axs[1].set(ylabel='20 ms期限超過 [%]',ylim=(0,100));axs[2].set(ylabel='自チーム実受信 [Mbps]');axs[0].legend(fontsize=8)
  fig.suptitle('同じ平均要求量で生成周期を変更：実受信量と指令品質を同時に評価',fontsize=12);save(fig,F,'payload-shaping-metrics')
  fig,axs=plt.subplots(2,3,figsize=(12,7.5),layout='constrained')
  for row,period in enumerate((10,100)):
   for col,ch in enumerate((6,7,11)):
    ax=axs[row,col];name=f'op-shape-m0p5-p{period}-ch{ch}-r1'
    if not (D/(name+'.json')).exists():ax.set_visible(False);continue
    m=json.loads((D/(name+'.json')).read_text());z=np.load(D/(name+'-spectrum.npz'));f=z['frequency_mhz'];power=z['power_dbfs']
    im=ax.imshow(power,origin='upper',aspect='auto',extent=(f[0],f[-1],len(power),0),cmap=CM,vmin=-90,vmax=-45,rasterized=True)
    ax.set(xlim=(2410,2480),title=f'生成 {period} ms / 他チームCh{ch}\n実受信 {m["delivered_payload_mbps"][0]:.2f} Mbps / {rtt_label(m)}',xlabel='周波数 [MHz]' if row==1 else '',ylabel='間欠取得順' if col==0 else '')
    for edge in (2427,2447):ax.axvline(edge,color='white',ls='--',lw=.8)
  fig.colorbar(im,ax=axs.ravel().tolist(),label='dBFS',shrink=.85)
  fig.suptitle('同じ平均要求0.5 Mbps・自チームCh6：生成周期と他チームチャネル別の反復1',fontsize=12)
  save(fig,F,'payload-shaping-blue-green')
if __name__=='__main__':main()
