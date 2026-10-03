#!/usr/bin/env python3
"""Measured ROS 2 control quality, sensor updates and common-scale SDR plots."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from render_operational import CM, COL, save

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT/'data/operational/ros2'
FIGURES = ROOT/'figures/operational'


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    summary = json.loads((DATA/'summary.json').read_text())
    configs = [('off', 'best_effort', 1), ('heavy', 'best_effort', 1),
               ('heavy', 'best_effort', 10), ('heavy', 'reliable', 1), ('heavy', 'reliable', 10)]
    labels = ['指令のみ', 'BE / 深さ1', 'BE / 深さ10', 'R / 深さ1', 'R / 深さ10']
    fig, axes = plt.subplots(1, 4, figsize=(15, 4.5), layout='constrained')
    for channel in (6, 7, 11):
        rows = [next(value for value in summary.values() if
                     (value['condition']['bulk'], value['condition']['reliability'], value['condition']['depth'],
                      value['condition']['other_channel']) == (*config, channel)) for config in configs]
        metrics = [
            ([value['pooled_rtt_p99_ms'] for value in rows], [[run['rtt_p99_ms'] for run in value['run_control']] for value in rows]),
            ([value['planned_deadline20_pct'] for value in rows], [[run['planned_deadline20_pct'] for run in value['run_control']] for value in rows]),
            ([np.mean([run['image']['delivered_payload_mbps']+run['cloud']['delivered_payload_mbps'] for run in value['run_sensors']]) for value in rows],
             [[run['image']['delivered_payload_mbps']+run['cloud']['delivered_payload_mbps'] for run in value['run_sensors']] for value in rows]),
            ([np.mean(value['delivered_other_mbps']) for value in rows], [value['delivered_other_mbps'] for value in rows]),
        ]
        for axis, (pooled, runs) in zip(axes, metrics):
            axis.plot(range(5), [np.nan if value is None else value for value in pooled], 'o-',
                      color=COL[channel], label=f'他チーム Ch{channel}')
            for index, values in enumerate(runs):
                axis.scatter([index]*len(values), [np.nan if value is None else value for value in values],
                             s=18, alpha=.45, color=COL[channel])
    for axis in axes:
        axis.set(xticks=range(5), xticklabels=labels); axis.tick_params(axis='x', labelrotation=35)
        axis.grid(alpha=.2)
    axes[0].set(ylabel='指令応答RTT p99 [ms]', yscale='log'); axes[0].legend(fontsize=8)
    axes[1].set(ylabel='予定指令の20 ms期限超過 [%]', ylim=(0, 100))
    axes[2].set(ylabel='画像・点群の実受信payload [Mbps]')
    axes[3].set(ylabel='他チームの実受信payload [Mbps]')
    fig.suptitle('実ROS 2：指令100 Hz・模擬画像／点群10 Hz｜BE＝best effort、R＝reliable\n'
                 'センサ要求60.54 Mbps、他チームに飽和TCPを要求｜小さい点は各反復', fontsize=11)
    save(fig, FIGURES, 'ros2-qos-metrics')

    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout='constrained')
    for channel in (6, 7, 11):
        rows = [next(value for value in summary.values() if
                     (value['condition']['bulk'], value['condition']['reliability'], value['condition']['depth'],
                      value['condition']['other_channel']) == (*config, channel)) for config in configs[1:]]
        for axis, topic in zip(axes, ('image', 'cloud')):
            values = [max(run[topic]['maximum_update_gap_ms'] for run in value['run_sensors']) for value in rows]
            axis.plot(range(4), values, 'o-', color=COL[channel], label=f'他チーム Ch{channel}')
            for index, value in enumerate(rows):
                runs = [run[topic]['maximum_update_gap_ms'] for run in value['run_sensors']]
                axis.scatter([index]*len(runs), runs, s=18, color=COL[channel], alpha=.45)
            axis.set(xticks=range(4), xticklabels=labels[1:], ylabel='最長更新途絶 [ms]', yscale='log')
            axis.grid(alpha=.2)
    axes[0].set_title('模擬Image'); axes[0].legend(fontsize=9)
    axes[1].set_title('模擬PointCloud2')
    fig.suptitle('受信側の時計による30秒窓の更新間隔：大きい点は3反復中の最大、端点も含む', fontsize=11)
    save(fig, FIGURES, 'ros2-update-gaps')

    fig, axes = plt.subplots(1, 3, figsize=(12, 4.9), layout='constrained')
    for axis, channel in zip(axes, (6, 7, 11)):
        name = f'op-ros2-heavy-best_effort-d1-ch{channel}-r1'
        row = json.loads((DATA/(name+'.json')).read_text()); data = np.load(DATA/(name+'-spectrum.npz'))
        frequency = data['frequency_mhz']; power = data['power_dbfs']
        image = axis.imshow(power, origin='upper', aspect='auto',
                            extent=(frequency[0], frequency[-1], len(power), 0), cmap=CM,
                            vmin=-90, vmax=-45, rasterized=True)
        rate = sum(row['sensors'][topic]['delivered_payload_mbps'] for topic in ('image', 'cloud'))
        rtt = row['control']['rtt_p99_ms']; rtt_text = '応答なし' if rtt is None else f'{rtt:.1f} ms'
        axis.set(xlim=(2410, 2480), xlabel='周波数 [MHz]', ylabel='間欠取得順',
                 title=f'他チーム Ch{channel} / 指令RTT p99 {rtt_text}\n'
                       f'センサ実受信 {rate:.2f} Mbps\n'
                       f'他チーム実受信 {row["other_delivered_mbps"]:.2f} Mbps')
        for edge in (2427, 2447):
            axis.axvline(edge, color='white', ls='--', lw=.8)
    fig.colorbar(image, ax=list(axes), label='未校正dBFS', shrink=.8)
    fig.suptitle('ROS 2 best effort・深さ1、反復1：自チームCh6と他チームのスペクトル\n'
                 'C5の間欠取得・手動ゲイン20・共通色尺度、破線は自チームの名目帯域', fontsize=11)
    save(fig, FIGURES, 'ros2-blue-green')


if __name__ == '__main__':
    main()
