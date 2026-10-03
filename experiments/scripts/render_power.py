#!/usr/bin/env python3
"""Power-save intervention and within-process timing evidence."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from render_operational import CM, COL, save

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT/'data/operational/power'
FIGURES = ROOT/'figures/operational'


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    summary = json.loads((DATA/'summary.json').read_text())
    configs = [('off', 'off'), ('off', 'on'), ('heavy', 'off'), ('heavy', 'on')]
    labels = ['指令のみ\nPS OFF', '指令のみ\nPS ON', 'センサ負荷\nPS OFF', 'センサ負荷\nPS ON']
    fields = ['rtt_p99_ms', 'send_lateness_p99_ms', 'publication_p99_ms',
              'echo_pre_publish_p99_ms', 'planned_deadline20_pct', 'maximum_response_gap_ms']
    titles = ['指令応答RTT p99', '予定送信からのずれp99', '指令publish所要時間p99',
              'ロボットcallbackから応答publish前までp99', '予定指令の20 ms期限超過', '最長指令応答途絶（窓端点を含む）']
    fig, axes = plt.subplots(2, 3, figsize=(13, 8), layout='constrained')
    for channel in (6, 11):
        rows = [next(value for value in summary.values() if
                     (value['condition']['bulk'], value['condition']['power_save'], value['condition']['other_channel'])
                     == (*config, channel)) for config in configs]
        for axis, field, title in zip(axes.ravel(), fields, titles):
            for index, value in enumerate(rows):
                samples = [run[field] for run in value['run_control']]
                axis.scatter([index]*len(samples), [np.nan if sample is None else sample for sample in samples],
                             s=26, color=COL[channel], alpha=.7,
                             label=f'他チーム Ch{channel}' if index == 0 else None)
            axis.set(title=title, xticks=range(4), xticklabels=labels,
                     ylabel='%' if field == 'planned_deadline20_pct' else 'ms')
            axis.grid(alpha=.2)
            if field == 'planned_deadline20_pct':
                axis.set_ylim(0, 100)
            else:
                axis.set_yscale('log')
    axes[0, 0].legend(fontsize=9)
    fig.suptitle('ロボットSTAの省電力設定ON／OFF：各点は30秒試行、各条件3反復\n'
                 'RTTはコントローラー時計、ロボット内処理はロボット時計のみで計算', fontsize=12)
    save(fig, FIGURES, 'power-save-timing')

    fig, axes = plt.subplots(2, 2, figsize=(11, 8), layout='constrained')
    for axis, (channel, power_setting) in zip(axes.ravel(), [(6, 'off'), (6, 'on'), (11, 'off'), (11, 'on')]):
        name = f'op-power-heavy-ps{power_setting}-ch{channel}-r1'
        row = json.loads((DATA/(name+'.json')).read_text()); data = np.load(DATA/(name+'-spectrum.npz'))
        frequency = data['frequency_mhz']; power = data['power_dbfs']
        image = axis.imshow(power, origin='upper', aspect='auto',
                            extent=(frequency[0], frequency[-1], len(power), 0), cmap=CM,
                            vmin=-90, vmax=-45, rasterized=True)
        rate = sum(row['sensors'][topic]['delivered_payload_mbps'] for topic in ('image', 'cloud'))
        axis.set(xlim=(2410, 2480), xlabel='周波数 [MHz]', ylabel='間欠取得順',
                 title=f'他チーム Ch{channel} / ロボットPS {power_setting.upper()}\nセンサ実受信 {rate:.2f} Mbps')
        for edge in (2427, 2447):
            axis.axvline(edge, color='white', ls='--', lw=.8)
    fig.colorbar(image, ax=list(axes.ravel()), label='未校正dBFS', shrink=.8)
    fig.suptitle('実ROS 2センサ負荷・best effort・深さ1、反復1：共通ゲイン・色尺度', fontsize=12)
    save(fig, FIGURES, 'power-save-blue-green')


if __name__ == '__main__':
    main()
