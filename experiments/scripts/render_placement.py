#!/usr/bin/env python3
"""Render confirmed measurements without filling missing placements."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from acquisition.placement_conditions import PLACEMENT_IDS
from render_operational import CM, save

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT/'data/operational/placement'
FIGURES = ROOT/'figures/operational'
LABELS = ('基準・前', '90°回転', '遮蔽', '距離変更', '基準・後')
COLORS = {'off': '#087bad', 'heavy': '#da5844'}


def numeric(values):
    return [np.nan if value is None else value for value in values]


def latest_rssi(row):
    before = row['radio']['echo']['before']; after = row['radio']['echo']['after']
    return after['rssi'] if after['rx_messages'] > before['rx_messages'] else None


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    summary = json.loads((DATA/'summary.json').read_text())
    fig, axes = plt.subplots(1, 5, figsize=(16, 4.5), layout='constrained')
    for wifi in ('off', 'heavy'):
        rows = [next(row for row in summary.values() if
                     row['condition']['placement_id'] == position and row['condition']['wifi'] == wifi)
                for position in PLACEMENT_IDS]
        aggregate = [numeric([row['pooled_rtt_p99_ms'] for row in rows]),
                     [row['planned_deadline20_pct'] for row in rows],
                     [max(run['maximum_increasing_sequence_gap_ms'] for run in row['run_application']) for row in rows],
                     [np.mean(row['wifi_delivered_mbps']) for row in rows]]
        fields = ('rtt_p99_ms', 'planned_deadline20_pct', 'maximum_increasing_sequence_gap_ms')
        for index, (axis, values) in enumerate(zip(axes, aggregate)):
            axis.plot(range(5), values, 'o-', color=COLORS[wifi],
                      label='Wi-Fi待機' if wifi == 'off' else 'Wi-Fi TCP負荷')
            for position_index, row in enumerate(rows):
                runs = ([run[fields[index]] for run in row['run_application']] if index < 3
                        else row['wifi_delivered_mbps'])
                axis.scatter([position_index]*len(runs), numeric(runs), s=18, alpha=.45, color=COLORS[wifi])
        for index, position in enumerate(PLACEMENT_IDS):
            runs = [json.loads((DATA/f'op-placement-{position}-wifi{wifi}-ch6-r{repeat}.json').read_text())
                    for repeat in (1, 2, 3)]
            axes[4].scatter([index]*3, numeric([latest_rssi(row) for row in runs]),
                            s=24, color=COLORS[wifi], alpha=.7)
    for axis in axes:
        axis.set(xticks=range(5), xticklabels=LABELS); axis.tick_params(axis='x', labelrotation=35)
        axis.grid(alpha=.2)
    axes[0].set(ylabel='応答した指令のRTT p99 [ms]', yscale='log'); axes[0].legend(fontsize=8)
    deadline_max = max(run['planned_deadline20_pct']
                       for row in summary.values() for run in row['run_application'])
    axes[1].set(ylabel='予定指令の20 ms期限超過 [%]',
                ylim=(0, max(.12, deadline_max * 1.2)))
    axes[2].set(ylabel='新しいsequenceへの最長更新途絶 [ms]', yscale='log')
    axes[3].set(ylabel='Wi-Fi実受信payload [Mbps]')
    axes[4].set(ylabel='応答機の最新受信RSSI [dBm]')
    fig.suptitle('手動配置比較：ESP-NOW Ch6・100 Hz・各10秒、別系統Wi-Fi Ch6\n'
                 '大きい点は統合p99／期限超過・最大途絶・平均実受信、RSSIは各反復の終了読出し', fontsize=11)
    save(fig, FIGURES, 'placement-metrics')

    fig, axes = plt.subplots(1, 5, figsize=(16, 4.8), layout='constrained')
    for axis, position, label in zip(axes, PLACEMENT_IDS, LABELS):
        name = f'op-placement-{position}-wifiheavy-ch6-r1'
        row = json.loads((DATA/(name+'.json')).read_text()); spectrum = np.load(DATA/(name+'-spectrum.npz'))
        frequency = spectrum['frequency_mhz']; power = spectrum['power_dbfs']
        image = axis.imshow(power, origin='upper', aspect='auto',
                            extent=(frequency[0], frequency[-1], len(power), 0),
                            cmap=CM, vmin=-90, vmax=-45, rasterized=True)
        placement = row['layout']['placement']; distances = placement['distances_cm']
        if position == 'obstructed':
            label = '手による遮蔽' if placement['body_obstruction']['kind'] == 'hand' else '身体による遮蔽'
        rssi = latest_rssi(row); rssi_text = '新規RSSI未取得' if rssi is None else f'最新RSSI {rssi} dBm'
        axis.set(xlim=(2410, 2480), xlabel='周波数 [MHz]', ylabel='間欠取得順',
                 title=f'{label} / 送受信 {distances["sender_echo"]:g} cm\n'
                       f'C5→応答 {distances["c5_echo"]:g} cm\n'
                       f'{rssi_text} / Wi-Fi {row["wifi_delivered_mbps"]:.2f} Mbps')
        axis.title.set_fontsize(9)
        for edge in (2427, 2447):
            axis.axvline(edge, color='white', ls='--', lw=.8)
    fig.colorbar(image, ax=list(axes), label='未校正dBFS', shrink=.8)
    fig.suptitle('Wi-Fi TCP負荷・各配置の反復1：共通ゲイン・青緑色尺度\n'
                 'C5までの距離の変化も含む。RFは間欠取得で、通信相手のRSSIや占有率ではない。', fontsize=11)
    save(fig, FIGURES, 'placement-blue-green')


if __name__ == '__main__':
    main()
