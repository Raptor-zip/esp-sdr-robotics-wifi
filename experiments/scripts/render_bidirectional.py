#!/usr/bin/env python3
"""Measured cross-radio performance and blue-green RF controls."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

from render_operational import CM, save

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT/'data/coexistence'
FIGURES = ROOT/'figures/coexistence'
COLORS = {100:'#087bad',200:'#da5844'}


def topology():
    fig,axis=plt.subplots(figsize=(8,3.1),layout='constrained')
    axis.set(xlim=(0,1),ylim=(0,1));axis.axis('off')
    boxes=[(.02,.64,.25,.24,'観測PC・AP\nIntel BE200\nWi-Fi Ch6・20 MHz','#e3f2fa'),
           (.73,.64,.25,.24,'独立したWi-Fi受信機\n負荷用ESP32\nTCP受信・UDP要求','#e3f2fa'),
           (.02,.27,.25,.22,'外部リンクの一方\nESP32\nWi-Fi APへ接続しない','#e0f6ed'),
           (.73,.27,.25,.22,'外部リンクのもう一方\nM5 ATOM LITE\nWi-Fi APへ接続しない','#e0f6ed'),
           (.25,.02,.5,.14,'ESP32-C5：全条件のRFを間欠観測\nUSBは設定・時刻記録用。図は論理構成で、物理配置ではない。','#eef0f2')]
    for x,y,w,h,text,color in boxes:
        axis.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.008',fc=color,ec='#55717d',lw=1))
        axis.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=10 if h>.15 else 9)
    for y,text,color in [(.75,'TCPの模擬大容量データ\nUDP 100 Hz要求・応答','#087bad'),
                         (.38,'ESP-NOW：64 byte往復・固定Ch6/7/11\nまたはBLE：広告／接続通知','#00835e')]:
        axis.add_patch(FancyArrowPatch((.29,y),(.71,y),arrowstyle='<->',mutation_scale=15,lw=1.8,color=color))
        axis.text(.5,y+.055,text,ha='center',va='bottom',fontsize=9,color=color)
    axis.text(.5,.98,'新しい双方向評価：Wi-Fi 1ホップと独立した外部無線リンク',ha='center',va='top',fontsize=12)
    save(fig,FIGURES,'mutual-topology')


def espnow():
    s = json.loads((DATA/'espnow-summary.json').read_text())
    fig, axes = plt.subplots(2,2,figsize=(9,6.5),layout='constrained')
    axes=axes.ravel()
    baseline = s['bidirectional-espnow-wifiheavy-hz0-ch6']
    axes[0].axhline(np.mean(baseline['wifi_goodput_mbps']),color='gray',ls='--',label='ESP-NOW停止平均')
    for hz in (100,200):
        rows = [s[f'bidirectional-espnow-wifiheavy-hz{hz}-ch{ch}'] for ch in (6,7,11)]
        for axis, field, ylabel in zip(axes[:2], ('wifi_goodput_mbps','matched_wifi_reduction_pct'),
                ('Wi-Fi実受信 [Mbps]','同じ反復の停止対照からの速度低下 [%]')):
            values = [np.mean(r[field]) for r in rows]
            axis.plot(range(3),values,'o-',color=COLORS[hz],label=f'ESP-NOW {hz} Hz')
            for i,row in enumerate(rows):
                axis.scatter([i]*len(row[field]),row[field],s=22,alpha=.5,color=COLORS[hz])
            axis.set(ylabel=ylabel,xticks=range(3),xticklabels=['同一 Ch6','隣接 Ch7','分離 Ch11'])
        for load, marker, style in [('off','o','--'),('heavy','s','-')]:
            app = [s[f'bidirectional-espnow-wifi{load}-hz{hz}-ch{ch}']['espnow'] for ch in (6,7,11)]
            for axis, field, ylabel in zip(axes[2:],('rtt_p99_ms','planned_deadline20_pct'),
                    ('ESP-NOWの応答RTT p99 [ms]','ESP-NOWの予定指令20 ms超過 [%]')):
                axis.plot(range(3),[np.mean([v[field] for v in row]) for row in app],marker+style,
                    color=COLORS[hz],label=f'{hz} Hz / Wi-Fi {"指令のみ" if load=="off" else "TCP負荷"}')
                for i,row in enumerate(app):
                    axis.scatter([i]*len(row),[v[field] for v in row],s=15,alpha=.4,color=COLORS[hz],marker=marker)
                axis.set(ylabel=ylabel,xticks=range(3),xticklabels=['同一 Ch6','隣接 Ch7','分離 Ch11'])
    axes[1].axhline(0,color='gray',ls='--');axes[1].text(.03,.02,'負の値は停止対照より速い',transform=axes[1].transAxes,fontsize=8)
    axes[0].legend(fontsize=8);axes[2].legend(fontsize=7)
    for axis in axes:
        axis.grid(alpha=.2)
    fig.suptitle('独立したESP-NOWとWi-Fiの相互影響｜各20秒・3反復、Wi-Fi Ch6・20 MHz・1段の経路\n'
                 '大きい点は反復平均、小さい点は各反復。速度低下率は反復ごとの停止対照で正規化。',fontsize=11)
    save(fig,FIGURES,'espnow-mutual-metrics')
    names=['bidirectional-espnow-wifiheavy-hz0-ch6-r1']+[f'bidirectional-espnow-wifiheavy-hz200-ch{ch}-r1' for ch in (6,7,11)]
    spectrum(names,['ESP-NOW停止','200 Hz・同一Ch6','200 Hz・隣接Ch7','200 Hz・分離Ch11'],'espnow-mutual-blue-green')


def spectrum(names, titles, stem, narrow=False):
    fig, axes = plt.subplots(1,len(names),figsize=(8.7,3.1),layout='constrained',squeeze=False)
    for i,(name,title) in enumerate(zip(names,titles)):
        row=json.loads((DATA/(name+'.json')).read_text());z=np.load(DATA/(name+'-spectrum.npz'))
        f=z['frequency_mhz'];p=z['power_dbfs'];axis=axes[0,i]
        im=axis.imshow(p,origin='upper',aspect='auto',extent=(f[0],f[-1],len(p),0),
            cmap=CM,vmin=-90,vmax=-60 if narrow else -45,rasterized=True)
        axis.set(xlim=(2450,2470) if narrow else (2410,2480),xlabel='周波数 [MHz]',
            ylabel='間欠取得順' if i==0 else '',title=title+f'\nWi-Fi実受信 {row["wifi"]["goodput_mbps"]:.3f} Mbps')
        if not narrow:
            for edge in (2427,2447):
                axis.axvline(edge,color='white',ls='--',lw=.8)
    fig.colorbar(im,ax=axes.ravel().tolist(),label='未校正dBFS',shrink=.8)
    fig.suptitle('Wi-Fi負荷中・反復1｜共通ゲイン・色尺度、各行約205 µsの間欠取得\n'
                 + ('2450–2470 MHz拡大：広告の3周波数は表示範囲外' if narrow else '白破線はWi-Fi Ch6の名目20 MHz帯域。色の割合を占有率として扱わない。'),fontsize=10)
    save(fig,FIGURES,stem)


def ble():
    s=json.loads((DATA/'ble-summary.json').read_text());modes=('off','advert','data');labels=('BLE停止','広告','接続データ')
    fig,axes=plt.subplots(2,2,figsize=(9,6.5),layout='constrained')
    axes=axes.ravel()
    rows=[s[f'bidirectional-ble-wifiheavy-{mode}'] for mode in modes]
    for axis,field,ylabel in zip(axes[:3],('wifi_goodput_mbps','matched_wifi_reduction_pct','wifi_deadline20_pct'),
        ('Wi-Fi実受信 [Mbps]','停止対照からのWi-Fi速度低下 [%]','Wi-Fi指令の20 ms超過 [%]')):
        values=[np.mean(row[field]) for row in rows];axis.bar(range(3),values,color=['#7f8b92','#087bad','#00b686'],alpha=.7)
        for i,row in enumerate(rows):
            axis.scatter([i]*len(row[field]),row[field],color='black',s=20)
        axis.set(ylabel=ylabel,xticks=range(3),xticklabels=labels);axis.grid(axis='y',alpha=.2)
    values=[s[f'bidirectional-ble-wifi{load}-data']['ble_goodput_mbps'] for load in ('off','heavy')]
    axes[3].bar(range(2),[np.mean(v) for v in values],color=['#087bad','#da5844'],alpha=.7)
    for i,value in enumerate(values):
        axes[3].scatter([i]*len(value),value,color='black',s=20)
    axes[3].set(ylabel='BLE通知の実受信 [Mbps]',xticks=range(2),xticklabels=['Wi-Fi指令のみ','Wi-Fi TCP負荷']);axes[3].grid(axis='y',alpha=.2)
    axes[1].axhline(0,color='gray',ls='--')
    fig.suptitle('独立したBLEとWi-Fiの相互影響｜各20秒・3反復、Wi-Fi Ch6・20 MHz・1段の経路\n'
                 '棒は反復平均、点は各反復。BLEのカウンタ区間は実際の読み出し間隔で正規化。',fontsize=10)
    save(fig,FIGURES,'ble-mutual-metrics')
    names=[f'bidirectional-ble-wifiheavy-{mode}-r1' for mode in modes]
    spectrum(names,labels,'ble-mutual-blue-green')
    spectrum(names,labels,'ble-mutual-narrow-blue-green',narrow=True)


def brackets():
    s=json.loads((DATA/'tcp-bracket-summary.json').read_text())
    fig,axes=plt.subplots(1,3,figsize=(8.5,3.1),layout='constrained',sharey=True)
    for axis,channel in zip(axes,(6,7,11)):
        rows=s[str(channel)]['blocks']
        for row,color in zip(rows,('#087bad','#da5844','#00b686')):
            axis.plot(range(3),[row['before_mbps'],row['on_mbps'],row['after_mbps']],
                'o-',color=color,label=f'反復{row["repeat"]}：低下 {row["reduction_pct"]:.1f}%')
        axis.set(xticks=range(3),xticklabels=['停止前','200 Hz動作','停止後'],
                 title=f'ESP-NOW Ch{channel} / Wi-Fi Ch6',ylim=(0,None))
        axis.grid(alpha=.2);axis.legend(fontsize=8)
    axes[0].set_ylabel('TCP単独のWi-Fi実受信 [Mbps]')
    fig.suptitle('同じTCP接続の停止前・動作・停止後｜各10秒・3反復、UDP指令なし\n'
                 '低下率は直前と直後の停止窓の平均が基準。負の値は基準より速い。',fontsize=10)
    save(fig,FIGURES,'tcp-bracket-metrics')


def main():
    FIGURES.mkdir(parents=True,exist_ok=True)
    topology();espnow();ble();brackets()


if __name__=='__main__':
    main()
