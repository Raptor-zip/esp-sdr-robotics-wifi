#!/usr/bin/env python3
"""Continuous application timing and intermittent RF, with distinct axes."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from render_operational import CM, save

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT/'data/operational/espnow-long'
FIGURES = ROOT/'figures/operational'
RATES = (20, 50, 100, 200)
COLORS = {'off': '#087bad', 'heavy': '#da5844'}
LABELS = {'off': 'Wi-Fi待機', 'heavy': 'Wi-Fi TCP負荷'}


def numeric(values):
    return [np.nan if value is None else value for value in values]


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    summary = json.loads((DATA/'summary.json').read_text())
    repetitions = sorted({value['runs'] for value in summary.values()})
    scope = f"{sum(value['runs'] for value in summary.values())}試行・条件ごと{min(repetitions)}〜{max(repetitions)}反復"
    deadline_top = max(.01, 1.15*max(run['planned_deadline20_pct']
        for value in summary.values() for run in value['run_application']))
    fig, axes = plt.subplots(1, 4, figsize=(15, 4.4), layout='constrained')
    for wifi in ('off', 'heavy'):
        rows = [next(row for row in summary.values() if
                     row['condition']['hz'] == hz and row['condition']['wifi'] == wifi)
                for hz in RATES]
        pooled = [numeric([row['pooled_rtt_p99_ms'] for row in rows]),
                  [row['planned_deadline20_pct'] for row in rows],
                  [max(run['maximum_increasing_sequence_gap_ms'] for run in row['run_application']) for row in rows],
                  [np.mean(row['wifi_delivered_mbps']) for row in rows]]
        fields = ('rtt_p99_ms', 'planned_deadline20_pct', 'maximum_increasing_sequence_gap_ms')
        for index, (axis, values) in enumerate(zip(axes, pooled)):
            axis.plot(range(4), values, 'o-', color=COLORS[wifi], label=LABELS[wifi])
            for rate_index, row in enumerate(rows):
                runs = ([run[fields[index]] for run in row['run_application']] if index < 3
                        else row['wifi_delivered_mbps'])
                axis.scatter([rate_index]*len(runs), numeric(runs), s=18, alpha=.45, color=COLORS[wifi])
    for axis in axes:
        axis.set(xticks=range(4), xticklabels=RATES, xlabel='予定指令送信頻度 [Hz]')
        axis.grid(alpha=.2)
    axes[0].set(ylabel='応答した指令のRTT p99 [ms]', yscale='log'); axes[0].legend(fontsize=9)
    axes[1].set(ylabel='予定指令の20 ms期限超過 [%]', ylim=(0, deadline_top))
    axes[2].set(ylabel='新しいsequenceへの最長更新途絶 [ms]', yscale='log')
    axes[3].set(ylabel='別系統Wi-Fiの実受信payload [Mbps]')
    fig.suptitle('ESP-NOW連続指令：未送信・欠落も期限超過へ含める / '+scope+'\n'
                 '大きい点は統合p99／期限超過・最大途絶・平均実受信、小さい点は各反復', fontsize=11)
    save(fig, FIGURES, 'espnow-long-metrics')

    fig, axes = plt.subplots(4, 2, figsize=(12, 11), layout='constrained', sharex=True)
    for index, hz in enumerate(RATES):
        timeline_deadline_top = .01
        for wifi in ('off', 'heavy'):
            for repeat in (1, 2, 3):
                name = f'op-espnow-long-hz{hz}-wifi{wifi}-ch6-r{repeat}'
                if not (DATA/(name+'.json')).exists():
                    continue
                row = json.loads((DATA/(name+'.json')).read_text())
                centers = [(window['start_s']+window['end_s'])/2 for window in row['timeline']]
                timeline_deadline_top = max(timeline_deadline_top,
                    1.15*max(window['planned_deadline20_pct'] for window in row['timeline']))
                label = LABELS[wifi] if repeat == 1 else None
                for axis, field in zip(axes[index], ('rtt_p99_ms', 'planned_deadline20_pct')):
                    axis.plot(centers, numeric([window[field] for window in row['timeline']]),
                              color=COLORS[wifi], alpha=.65, lw=1, ls=('-', '--', ':')[repeat-1], label=label)
        axes[index, 0].set(ylabel=f'{hz} Hz：RTT p99 [ms]', yscale='log')
        axes[index, 1].set(ylabel=f'{hz} Hz：20 ms期限超過 [%]', ylim=(0, timeline_deadline_top))
        for axis in axes[index]:
            axis.grid(alpha=.2)
    for axis in axes[-1]:
        axis.set_xlabel('送信機の試行開始からの相対時刻 [s]')
    axes[0, 0].legend(fontsize=9)
    fig.suptitle('連続アプリ記録の10秒窓：各反復を別線で表示 / '+scope+'\n'
                 'p99は応答した指令だけ、期限超過は全予定指令。期限超過の縦軸範囲はHzごとに異なる。', fontsize=11)
    save(fig, FIGURES, 'espnow-long-timeline')

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), layout='constrained')
    for axis, wifi in zip(axes, ('off', 'heavy')):
        name = f'op-espnow-long-hz100-wifi{wifi}-ch6-r1'
        row = json.loads((DATA/(name+'.json')).read_text()); spectrum = np.load(DATA/(name+'-spectrum.npz'))
        frequency = spectrum['frequency_mhz']; power = spectrum['power_dbfs']
        image = axis.imshow(power, origin='upper', aspect='auto',
                            extent=(frequency[0], frequency[-1], len(power), 0),
                            cmap=CM, vmin=-90, vmax=-45, rasterized=True)
        axis.set(xlim=(2410, 2480), xlabel='周波数 [MHz]', ylabel='間欠取得順',
                 title=f'{LABELS[wifi]} / {row["seconds"]}秒・100 Hz・反復1\n'
                       f'Wi-Fi実受信 {row["wifi_delivered_mbps"]:.2f} Mbps / '
                       f'名目RF観測時間比 {row["sdr"]["nominal_observation_pct"]:.3f}%')
        for edge in (2427, 2447):
            axis.axvline(edge, color='white', ls='--', lw=.8)
    fig.colorbar(image, ax=list(axes), label='未校正dBFS', shrink=.8)
    fig.suptitle('ESP-NOW Ch6と別系統Wi-Fi Ch6：共通ゲイン・色尺度\n'
                 'RFは間欠取得：縦軸は連続時間・占有率ではなく取得順', fontsize=11)
    save(fig, FIGURES, 'espnow-long-blue-green')


if __name__ == '__main__':
    main()
