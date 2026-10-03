#!/usr/bin/env python3
"""Write the measured operational discussion from verified public aggregates."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT/'experiments/data/operational'


def ros2_notes(manifest):
    path = DATA/'ros2/summary.json'
    if not path.exists():
        return []
    summary = json.loads(path.read_text()); evidence = manifest['operational']['ros2']
    assert evidence['trials'] == 45 and len(summary) == 15
    assert all(value['runs'] == 3 for value in summary.values())
    lines = ['', '## 実ROS 2のQoSと指令応答', '',
        f"45試行・15条件・各30秒・3反復。指令側ROS 2 Humble・ロボット側Jazzy、双方CycloneDDS。"
        f"予定{evidence['control_planned']}指令を全てpublishし、"
        f"{evidence['control_received']} unique応答と{evidence['iq_snapshots_original']} I/Q取得を保存した。"
        '指令のQoSはreliable・深さ10に固定し、Image／PointCloud2のQoSだけを変更した。'
        'PC AP→ロボットSTAの経路であり、前段のSTA→AP→STAとは比較経路が異なる。', '',
        '| センサ負荷 | センサQoS | 深さ | 他チームCh | RTT統合p99 [ms] | 予定指令の20 ms期限超過 [%] | センサ実受信範囲 [Mbps] | 最長画像更新途絶の反復範囲 [ms] |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    order = lambda item: (item['condition']['bulk'], item['condition']['reliability'],
                          item['condition']['depth'], item['condition']['other_channel'])
    for value in sorted(summary.values(), key=order):
        condition = value['condition']; sensors = value['run_sensors']
        rate = [sum(run[topic]['delivered_payload_mbps'] for topic in ('image', 'cloud')) for run in sensors]
        gaps = [run['image']['maximum_update_gap_ms'] for run in sensors]
        gap_text = '—' if condition['bulk'] == 'off' else f'{min(gaps):.2f}–{max(gaps):.2f}'
        lines.append(f"| {condition['bulk']} | {condition['reliability']} | {condition['depth']} | "
            f"{condition['other_channel']} | {value['pooled_rtt_p99_ms']:.2f} | "
            f"{value['planned_deadline20_pct']:.2f} | {min(rate):.2f}–{max(rate):.2f} | {gap_text} |")
    lines += ['',
        '指令のみの条件にも約100 ms級のRTT p99と約45%の20 ms期限超過がある。'
        'センサを止めても指令期限を満たしていないため、カメラ帯域を削減するだけで解決すると結論できない。'
        'センサを加えると期限超過はおよそ70〜80%となり、同じWi-Fiに大容量トピックを載せた状態で'
        '指令品質を検証する必要がある。', '',
        'best effort・深さ1を常に最善とする結果でも、reliableの優位を一般化する結果でもない。'
        '同じQoSでも反復ごとの尾部遅延と更新途絶が変わる。深さ1はアプリの受信履歴設定であり、'
        '無線の待ち行列を深さ1にする操作ではない。センサの受信更新間隔を指令RTTと併記することで、'
        '操縦指令の遅れとカメラ・点群の更新停止を分けて評価できる。'
        'センサの更新間隔は各sequenceの初回受信の間隔であり、古いsequenceの遅着を除くESP-NOWの最新sequence更新間隔とは異なる。'
        '異なるPCの時計は引いておらず、センサの生成から到着までの絶対的な古さは測っていない。', '',
        'センサの要求data payloadは60.53888 Mbpsだが、実受信はおよそ47〜55 Mbpsである。'
        'publishが遅れた古い生成slotは飛ばしているため、未生成・publish済み・測定窓内受信を分ける。'
        'センサ内容は合成データであり、圧縮映像、実LiDARの処理負荷やモータ制御を再現していない。', '',
        '他チームの飽和TCPは全試行で現行相手のnonce/challengeと実受信増加を確認したが、'
        'チャネルごとの実受信量は揃っていない。Ch11の20 MHz信号の一部はC5の48 MHzアナログ帯域の'
        '名目端の外へかかるため、青緑SDR図の弱い色から干渉がなくなったとは言えない。', '',
        '認証による転送停止前の28試行と、回収・再開後の17試行をそのまま保持した。'
        '取得セグメント、転送方法、転送元SHA256を記録し、性能を理由に悪い試行を再測定していない。'
        '再開前後の時間帯・環境変動は統制できていない。', '',
        'ロボコンでの実装候補は、指令と大容量トピックの用途別QoS、画像・点群の生成量や周期、'
        '省電力設定を個別に変え、予定指令の期限超過と最新データの途絶を測ることである。'
        'QoS設定だけで通信の優先度や20 ms期限が保証される結果にはなっていない。', '']
    return lines


def power_notes(manifest):
    path = DATA/'power/summary.json'
    if not path.exists():
        return []
    summary = json.loads(path.read_text()); evidence = manifest['operational']['power']
    assert evidence['trials'] == 24 and len(summary) == 8
    assert all(value['runs'] == 3 for value in summary.values())
    lookup = {(value['condition']['bulk'], value['condition']['power_save'],
               value['condition']['other_channel']): value for value in summary.values()}
    lines = ['', '## 省電力設定への介入と端末内時間', '',
        f"QoS比較とは別に24試行・8条件・各30秒・3反復。予定{evidence['control_planned']}指令、"
        f"publish済み{evidence['control_published']}指令、{evidence['control_received']} unique応答、"
        f"{evidence['iq_snapshots_original']} I/Q取得。STAの省電力ON／OFFを実際に切り替え、"
        '各試行の前後にiwのreadbackを保存した。AP側はOFFに固定した。'
        'センサQoSはbest effort・深さ1、指令はreliable・深さ10。', '',
        '| センサ負荷 | 他チームCh | STA省電力 | RTT統合p99 [ms] | 20 ms期限超過 [%] | 予定送信のずれ統合p99 [ms] | 指令publish統合p99 [ms] | callbackから応答publish前までp99の範囲 [ms] |',
        '| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |']
    for bulk in ('off', 'heavy'):
        for channel in (6, 11):
            for power in ('off', 'on'):
                value = lookup[bulk, power, channel]
                echo = [run['echo_pre_publish_p99_ms'] for run in value['run_control']
                        if run['echo_pre_publish_p99_ms'] is not None]
                lines.append(f"| {bulk} | {channel} | {power} | {value['pooled_rtt_p99_ms']:.2f} | "
                    f"{value['planned_deadline20_pct']:.2f} | {value['pooled_send_lateness_p99_ms']:.3f} | "
                    f"{value['pooled_publication_p99_ms']:.3f} | {min(echo):.4f}–{max(echo):.4f} |")
    lines += ['',
        '### 同じ負荷条件でのOFFからONへの変化', '']
    for bulk in ('off', 'heavy'):
        for channel in (6, 11):
            off = lookup[bulk, 'off', channel]; on = lookup[bulk, 'on', channel]
            lines.append(f"センサ{bulk}・他チームCh{channel}で省電力OFF→ONにすると、"
                f"RTT統合p99は{off['pooled_rtt_p99_ms']:.2f}→{on['pooled_rtt_p99_ms']:.2f} ms、"
                f"20 ms期限超過は{off['planned_deadline20_pct']:.2f}→{on['planned_deadline20_pct']:.2f}%だった。")
    lines += ['',
        'ON／OFFは設定要求だけでなく取得前後の実readbackで確認した介入である。'
        'ただしiwの状態は、実際に何ms眠ったかや無線の待ち時間を直接測った値ではない。'
        '他チームの実受信量やセンサ実配送も変動するため、効果を端末一般の保証へ広げない。', '',
        '予定送信のずれとpublish呼出しはコントローラー内の時計、callbackから応答publish前までの'
        '処理はロボット内の時計、往復応答はコントローラーの時計で測った。'
        'publishが短くても、その後のDDS・OS・MACの待ち行列、無線再送、受信dispatchの時間は残る。'
        'p99同士を引いて各原因の寄与を割り当てたり、RTTの半分を片道遅延と扱ったりしない。', '',
        'ロボコンで確認すべきなのは、実際の端末で省電力設定を変えたときに、'
        '指令の期限超過と最長更新途絶がどう変わるかである。'
        '省電力OFF・チャネル分離・QoS設定を組み合わせても、今回の試験で満たしていない期限を'
        '満たしたものとして扱わない。測定中に監視用HTTPを周期送信せず、終了後にログを転送した。', '']
    return lines


def espnow_long_notes(manifest):
    path = DATA/'espnow-long/summary.json'
    if not path.exists():
        return []
    summary = json.loads(path.read_text()); evidence = manifest['operational']['espnow-long']
    assert len(summary) == 8 and sum(value['runs'] for value in summary.values()) == evidence['trials']
    assert all(2 <= value['runs'] <= 3 and value['seconds'] == [600]*value['runs'] for value in summary.values())
    stopped = evidence['trials'] < 24
    assert evidence['trials'] == 24 or (evidence['status'] == 'stopped_at_user_request' and evidence['planned_trials'] == 24)
    lines = ['', '## ESP-NOWの指令周期と長時間更新の安定性', '',
        f"{evidence['trials']}試行・8条件・各600秒・条件ごと2〜3反復。予定{evidence['control_planned']}指令、"
        f"{evidence['control_send_calls']}送信呼出し、{evidence['control_received']} unique応答、"
        f"{evidence['iq_snapshots_original']} I/Q取得を保存した。"
        'ESP32 2台間の64 byteアプリ応答を20・50・100・200 Hzで連続記録し、'
        '別系統のCh6・20 MHz Wi-Fiを待機／TCP負荷に切り替えた。'
        '配置は同じ机上のおおむね30 cmという使用者の申告であり、正確な送受信距離は未測定。', '',
        '| 指令周期 [Hz] | Wi-Fi | 反復数 | RTT統合p99 [ms] | 予定指令の20 ms期限超過 [%] | 応答欠落 / 予定指令 | 新しいsequenceへの最長更新途絶の反復範囲 [ms] | Wi-Fi実受信範囲 [Mbps] |',
        '| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    if stopped:
        lines[3:3] = [f"当初24試行の予定だったが、使用者が実験を早く終えたいと希望したため、"
            f"進行中の試行を保存した{evidence['trials']}試行で長時間測定を終了した。残り{24-evidence['trials']}試行は測っていない。"
            f"反復1・2は全8条件、反復3は{evidence['trials']-16}条件である。"
            '取得した全試行を残し、条件間の反復数が異なることを明記する。', '']
    for value in sorted(summary.values(), key=lambda row: (row['condition']['hz'], row['condition']['wifi'])):
        condition = value['condition']; gaps = [run['maximum_increasing_sequence_gap_ms'] for run in value['run_application']]
        rates = value['wifi_delivered_mbps']
        lines.append(f"| {condition['hz']} | {condition['wifi']} | {value['runs']} | {value['pooled_rtt_p99_ms']:.3f} | "
            f"{value['planned_deadline20_pct']:.5f} | {value['planned']-value['replies']} / {value['planned']} | "
            f"{min(gaps):.3f}–{max(gaps):.3f} | {min(rates):.3f}–{max(rates):.3f} |")
    lookup = {(value['condition']['hz'], value['condition']['wifi']): value for value in summary.values()}
    lines += ['', '### Wi-Fi待機と負荷の比較', '']
    for hz in (20, 50, 100, 200):
        off = lookup[hz, 'off']; heavy = lookup[hz, 'heavy']
        lines.append(f"{hz} HzでWi-Fi待機→負荷へ切り替えたとき、RTT統合p99は"
            f"{off['pooled_rtt_p99_ms']:.3f}→{heavy['pooled_rtt_p99_ms']:.3f} ms、"
            f"予定指令の20 ms期限超過は{off['planned_deadline20_pct']:.5f}→"
            f"{heavy['planned_deadline20_pct']:.5f}%、応答欠落は"
            f"{off['planned']-off['replies']}→{heavy['planned']-heavy['replies']}件だった。")
    missed = []
    for file in sorted((DATA/'espnow-long').glob('op-espnow-long-*.json')):
        row = json.loads(file.read_text()); stats = row['application']
        if stats['unique_replies'] == stats['planned']:
            continue
        condition = row['condition']; sender = row['radio']['sender']['after']; echo = row['radio']['echo']['after']
        missed.append(f"{condition['hz']} Hz・Wi-Fi {condition['wifi']}・反復{condition['repeat']}："
            f"予定{stats['planned']}、送信呼出し{stats['send_calls']}、unique応答{stats['unique_replies']}。"
            f"応答機の受信カウンタ{echo['rx_messages']}、応答送信APIエラー{echo['tx_api_errors']}、"
            f"MAC送信失敗{echo['tx_fail']}、echo queue drop{echo['echo_queue_drops']}。"
            f"指令機のMAC送信失敗{sender['tx_fail']}、UART trace drop{sender['trace_drops']}。")
    if missed:
        lines += ['', '### 応答欠落を記録した試行', ''] + missed + ['',
            'これらは試行全体のカウンタであり、MAC結果を個々の欠落sequenceへ対応づけていない。'
            'Wi-Fi待機条件でも欠落がある場合、全欠落を追加TCP負荷の影響として扱わない。']
    lines += ['',
        '### 指令の往復時間と情報の更新間隔', '',
        '20 Hzの通常更新間隔は50 ms、200 Hzは5 msである。'
        '20 ms期限超過は各指令の予定送信から応答までを測る比較指標であり、'
        '20 Hzの制御情報が20 msごとに更新されるという意味ではない。'
        '最長更新途絶には通常の指令周期も含むため、周期の違う条件を欠落率だけ、'
        'あるいは途絶の絶対値だけで順位付けしない。'
        '新しいsequenceが届いた時刻で途絶を計算し、古い応答の到着を新しい制御情報の更新に数えない。', '',
        '64 byteの要求を100 Hzで送るアプリpayloadは片方向0.0512 Mbps、'
        '200 Hzでは0.1024 Mbpsであり、全要求に同サイズの応答がある場合は往復合計がその2倍になる。'
        'これはフレームヘッダー、プリアンブル、ACK、送信待ち、再送を含む空中時間ではない。'
        '設定PHY 1 Mbpsも受信アナログ帯域やアプリ実到達量ではない。'
        '小さな指令を高頻度で送る設計では、平均payloadだけでなく周期と更新途絶を検証する。', '',
        '送信API受付、MAC送信結果、相手からのアプリ応答は別々の観測である。'
        'MAC成功は相手アプリの実行やロボットの動作を保証しない。'
        'この区別は[EspressifのESP-NOWガイド](https://docs.espressif.com/projects/esp-idf/en/v6.0/esp32/api-reference/network/esp_now.html#send-esp-now-data)でも示されている。'
        '応答がない場合も、往路の指令が届かなかったのか復路の応答が欠けたのかを'
        '送信側の記録だけで決められない。連続記録のCRC、予定slot、END、UART dropを検算し、'
        'テレメトリ欠落を無線欠落として数えない。', '',
        '### Wi-Fiとの共存と適用範囲', '',
        'Wi-Fi TCPの要求payloadは15.72864 Mbpsであり、達成量は表の実受信値である。'
        '要求が同じでも実受信と空中時間は同じとは限らない。'
        '待機にもAPビーコンと監視通信があり、電波が完全に停止した基準ではない。'
        '10秒ごとのカウンタで接続と実通信を確認するが、瞬間ごとのRF送信量は測っていない。', '',
        'ESP-NOWは今回の設定ではルーターを通らない独立リンクである。'
        'ROS 2のPC間通信やSTA→AP→STAのUDPと経路、端末、実装、配置が異なるため、'
        '絶対RTTの差をプロトコル固有の優劣として扱わない。'
        'ロボコンへの示唆は、大容量データと指令の経路を分ける候補でも、'
        '同じチャネルで両者を実際に動かして更新途絶を測る必要があることにある。'
        '連続10分を3回測っても、会場、遮蔽、移動、長距離や安全停止の保証にはならない。'
        '欠落ゼロの条件も、将来の欠落確率ゼロを意味しない。', '',
        'C5のRF記録は連続ではなく間欠取得であり、アプリイベントの全時間軸とは別である。'
        '青緑の色は未校正dBFSを共通尺度で表示した受信エネルギーで、'
        'ESP-NOWの成功率、Wi-Fi占有率、送信電力ではない。', '',
        '### 保存待ちによる取得中断と補足記録', '',
        '当初7試行を完了した後、次の600秒試行では測定後のI/Q圧縮が旧15秒の保存待ちを超え、'
        '最終設定・負荷カウンタのcontextが揃わなかった。'
        'この試行は正式24試行へ入れず、12000送信／12000応答の全アプリ記録を'
        'operational/supplementalへ補足公開した。設定前の予定条件を、取得後に確認済みの設定へ読み替えていない。'
        '元I/Qも私有保管した。保存待ちを120秒へ延長し、失敗時checkpointを加えた後、'
        '有効な7試行を保持して未完了17試行の取得を再開した。'
        '再開中に使用者の要望で長時間測定を短縮し、実際に保存できた試行だけを集計した。'
        'これはRF測定窓を変えず、測定後の保存処理を修正したものである。'
        '取得セグメントを公開し、中断前後の環境変動を統制したとは扱わない。', '']
    return lines


def placement_notes(manifest):
    path = DATA/'placement/summary.json'
    if not path.exists():
        return []
    summary = json.loads(path.read_text()); evidence = manifest['operational']['placement']
    assert evidence['trials'] == 30 and len(summary) == 10
    assert all(value['runs'] == 3 and value['seconds'] == [10]*3 for value in summary.values())
    positions = ('baseline-before', 'rotated', 'obstructed', 'farther', 'baseline-after')
    labels = ('基準・前', '90°回転', '遮蔽', '距離変更', '基準・後')
    lookup = {(value['condition']['placement_id'], value['condition']['wifi']): value for value in summary.values()}
    records = {(position, wifi): [json.loads((DATA/'placement'/
        f'op-placement-{position}-wifi{wifi}-ch6-r{repeat}.json').read_text()) for repeat in (1, 2, 3)]
        for position in positions for wifi in ('off', 'heavy')}
    def number(value):
        return '—' if value is None else f'{value:.3f}'
    def rssi_text(rows):
        values = [row['radio']['echo']['after']['rssi'] for row in rows
                  if row['radio']['echo']['after']['rx_messages'] > row['radio']['echo']['before']['rx_messages']]
        return '新規受信なし' if not values else f'{min(values)}–{max(values)}'
    lines = ['', '## ESP32間通信の配置・向き・遮蔽比較', '',
        f"使用者が適用・確認した5配置、Wi-Fi待機／負荷、各10秒・3反復の30試行。"
        f"予定{evidence['control_planned']}指令、{evidence['control_send_calls']}送信呼出し、"
        f"{evidence['control_received']} unique応答、{evidence['iq_snapshots_original']} I/Q取得。"
        'ESP32 2台間のESP-NOW Ch6・100 Hzを評価対象とし、PC間の距離は比較指標にしていない。'
        '距離はボードまたはケース中心間の使用者報告値で、アンテナ間距離の校正値ではない。', '',
        '| 配置 | ESP32送受信間 [cm] | C5と指令機 [cm] | C5と応答機 [cm] | 応答機の回転 [°] | 遮蔽物 |',
        '| --- | ---: | ---: | ---: | ---: | --- |']
    for position, label in zip(positions, labels):
        value = records[position, 'off'][0]['layout']['placement']; distance = value['distances_cm']
        lines.append(f"| {label} | {distance['sender_echo']:g} | {distance['c5_sender']:g} | "
            f"{distance['c5_echo']:g} | {value['echo_rotation_degrees']} | { {'none': 'なし', 'hand': '手', 'body': '身体'}[value['body_obstruction']['kind']] } |")
    for position, label in zip(positions, labels):
        note = records[position, 'off'][0]['layout']['placement'].get('distance_note')
        if note:
            lines += ['', f'{label}の距離注記：{note}']
    lines += ['',
        '| 配置 | Wi-Fi | RTT統合p99 [ms] | 20 ms期限超過 [%] | 応答欠落 / 予定指令 | 最長更新途絶 [ms] | 応答機の最新RSSIの反復範囲 [dBm] | Wi-Fi実受信範囲 [Mbps] |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for position, label in zip(positions, labels):
        for wifi in ('off', 'heavy'):
            value = lookup[position, wifi]; rates = value['wifi_delivered_mbps']
            gap = max(run['maximum_increasing_sequence_gap_ms'] for run in value['run_application'])
            lines.append(f"| {label} | {wifi} | {number(value['pooled_rtt_p99_ms'])} | "
                f"{value['planned_deadline20_pct']:.3f} | {value['planned']-value['replies']} / {value['planned']} | "
                f"{gap:.3f} | {rssi_text(records[position, wifi])} | {min(rates):.3f}–{max(rates):.3f} |")
    lines += ['', '### 基準配置の前後と条件比較', '']
    for wifi in ('off', 'heavy'):
        before = lookup['baseline-before', wifi]; after = lookup['baseline-after', wifi]
        lines.append(f"Wi-Fi {wifi}の基準・前→基準・後では、RTT統合p99が"
            f"{number(before['pooled_rtt_p99_ms'])}→{number(after['pooled_rtt_p99_ms'])} ms、"
            f"20 ms期限超過が{before['planned_deadline20_pct']:.3f}→{after['planned_deadline20_pct']:.3f}%だった。")
    for position, label in zip(positions[1:4], labels[1:4]):
        base = lookup['baseline-before', 'heavy']; value = lookup[position, 'heavy']
        lines.append(f"Wi-Fi負荷中の{label}では、基準・前から20 ms期限超過が"
            f"{base['planned_deadline20_pct']:.3f}→{value['planned_deadline20_pct']:.3f}%、"
            f"応答欠落が{base['planned']-base['replies']}→{value['planned']-value['replies']}件に変わった。")
    if evidence['control_received'] == evidence['control_planned']:
        lines += ['',
            '今回の全配置で予定指令に対する応答欠落はなかった。ただし期限超過は応答欠落と別であり、'
            '届いた全指令が20 ms以内だったという意味ではない。'
            'この近距離・短時間試験では、向き・手・距離変更による応答不達の増加を捉えなかった。'
            'リンクの受信余裕が大きい場合、姿勢や反射が変わっても配送が保たれ得る。'
            '遠距離や金属筐体の遮蔽で同じ余裕があるかは今回の配置から判断できない。']
    before = lookup['baseline-before', 'heavy']; after = lookup['baseline-after', 'heavy']
    if after['pooled_rtt_p99_ms'] < before['pooled_rtt_p99_ms']:
        lines += ['',
            '負荷中の基準・後も基準・前よりRTT p99が低かった。'
            'したがって変更条件のp99低下を、回転や遮蔽だけの改善効果と結論できない。'
            '元に戻した条件にも変化が残ることが、時間経過・端末状態・ケーブルや室内反射を'
            '比較に含める必要性を示す。ロボットのアンテナ配置を決める際も、基準へ戻す測定を挟む価値がある。']
    lines += ['',
        '各配置をまとめて測るため、配置間の順序は無作為化していない。'
        '基準・前後の変動と各反復を併せて示し、一つの良い／悪い試行だけで配置を順位付けしない。'
        'Wi-Fi実受信量も比較に併記し、負荷実現度の変化を配置の効果だけへ帰属しない。', '',
        '### RSSI・SDR画像と指令品質の関係', '',
        '表のRSSIは各反復の終了時に読み出した最後の受信パケットの値である。'
        '3点の最小・最大は全パケットの分布や試行平均ではない。'
        '新しい受信のない試行には以前のRSSIを流用しない。'
        'RSSIが改善しても期限超過が減るとは限らず、欠落時の信号強度は観測できない。', '',
        '手または身体を2台の間へ置いた操作を評価したもので、'
        '人体・ロボット筐体の一般的な遮蔽損失を測った校正実験ではない。'
        '応答機の回転にはケーブルと周囲の反射の変化も伴い得る。'
        '距離点が少なく、近い机上配置なので到達距離や自由空間伝搬の式を推定しない。', '',
        'C5の青緑画像は各配置のWi-Fi負荷・反復1を事前指定して共通設定と色尺度で並べる。'
        '応答機を移動するとC5までの距離も変わるため、画像の色は通信相手のRSSIと同じ量ではない。'
        '10秒窓で色の違いが見えなくても、人体や向きが影響しないと一般化しない。', '',
        'ロボコンでは、実機搭載位置、コントローラーの向き、人や金属物の位置を変え、'
        '大容量通信中に指令がいつまで更新されないかを測る比較へ展開できる。'
        '今回の各10秒・3反復を会場全体の性能保証や600秒試行と同じ耐久性へ読み替えない。', '']
    return lines


def main():
    summary = json.loads((DATA/'limit/summary.json').read_text())
    manifest = json.loads((ROOT/'experiments/data/manifest.json').read_text())['operational']['limit']
    assert manifest['trials'] == 45 and len(summary) == 15 and all(value['runs'] == 3 for value in summary.values())
    rows = {(value['condition']['other_channel'], value['condition']['requested_mbps']): value for value in summary.values()}
    def rate_mean(value): return sum(value['delivered_own_mbps'])/3
    lines = ['# ロボコン運用評価の結果と考察', '', '## 流量制限の比較', '',
        f"version7・source helper version2で新たに取得した45試行、15条件、各3反復・30秒。全{manifest['control_sent']}指令送信、{manifest['control_received']}応答、{manifest['iq_snapshots_original']} I/Q取得。全条件の数値検算・現行接続相手の応答確認・負荷設定readbackを確認し、図を目視した。旧version6の取得は非公開の予備診断記録として保存し、正式比較には混ぜない。", '',
        '観測PCのAPはCh6・20 MHz、指令役ESP32からAPを経由してラップトップ2へ64 byte・100 HzのUDP指令を往復する。同じWi-Fiでラップトップ2から指令役へTCP模擬データを送る。他チームは独立したESP32 AP→STAに飽和TCPを要求する。ROS 2・実カメラ・実LiDARの試験ではない。配置は全機器が同じ机上、おおむね30 cmで固定。SDRボードはESP32-C5-WROOM-1。', '',
        '| 他チームCh | 自チーム要求TCP [Mbps] | 応答RTT統合p99 [ms] | 20 ms期限超過 [%] | 自チーム実受信平均 [Mbps] | 他チーム実受信範囲 [Mbps] |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for channel in (6, 7, 11):
        for rate in (0, .25, .5, 1, 2):
            value = rows[channel, rate]
            lines.append(f"| {channel} | {rate:g} | {value['pooled_p99_ms']:.2f} | {value['deadline20_pct']:.2f} | {rate_mean(value):.3f} | {min(value['delivered_other_mbps']):.3f}–{max(value['delivered_other_mbps']):.3f} |")
    lines += ['', '統合p99は戻った応答をまとめた分位点であり、各反復p99の平均ではない。20 ms期限超過は欠落を含む。各条件の環境反復数は3回であり、135000パケットを独立した環境反復と扱わない。図の小さい点で反復間の変動を併記する。', '',
        '## 自チームの大容量通信と指令品質', '',
        f"要求0→1 Mbpsで期限超過率は、同一Ch6で{rows[6,0]['deadline20_pct']:.2f}→{rows[6,1]['deadline20_pct']:.2f}%、隣接Ch7で{rows[7,0]['deadline20_pct']:.2f}→{rows[7,1]['deadline20_pct']:.2f}%、分離Ch11で{rows[11,0]['deadline20_pct']:.2f}→{rows[11,1]['deadline20_pct']:.2f}%となった。平均速度だけでは指令品質を表せない。Ch6・要求1 Mbpsの実受信は平均{rate_mean(rows[6,1]):.3f} Mbpsだが、20 ms期限超過は{rows[6,1]['deadline20_pct']:.2f}%だった。この構成では画像・点群相当の通信を制限することが指令遅延を減らす候補になる。", '',
        'ただし要求量に比例した単調な劣化ではない。要求2 Mbpsでは、全チャネルで実受信が要求に達せず、アプリ未送信byteが累積した。例えばCh6の実受信平均は'+f"{rate_mean(rows[6,2]):.3f} Mbpsで、期限超過{rows[6,2]['deadline20_pct']:.2f}%は要求1 Mbpsより低い。"+'これを「2 Mbpsの方が安全」と解釈できない。生成量、アプリの待ち行列、ソケットの受付、RFの送信機会、受信量は異なる観測であり、バックプレッシャーで負荷の形が変わる。', '',
        '## チャネル分離の効果と比較の限界', '',
        '要求1 Mbpsにおける期限超過は同一Ch6、隣接Ch7、分離Ch11の順に低かった。ただし、他チームの実受信量もチャネルで異なり、同じ干渉電力・同じ空中時間を与えた比較ではない。机上固定でも受信量と端末状態は変動している。3反復の結果から会場全体に通用するチャネル順位や安全なMbps上限を決めない。', '',
        f"分離Ch11・自チーム待機でもRTT統合p99は{rows[11,0]['pooled_p99_ms']:.2f} msで、各反復p99は"+ '、'.join(f'{value:.2f}' for value in rows[11,0]['run_p99_ms'])+' msだった。分離Ch11の0.5 Mbps条件でも反復間の尾部遅延の差が大きい。チャネル分離だけで自チーム内部の待ち行列・端末処理・外来通信を解消できるとは言えない。RTT p99と期限超過率の両方を見る必要がある。', '',
        '全45試行で他チームSTAの受信増加を確認した。ただし最低実受信は0.074 Mbpsで、飽和TCP要求が持続的なRF負荷や大容量データの達成を保証しない。負荷の実現度は図と表の他チーム実受信量を併せて判断する。APソケット受付量や送信試行数をRF空中時間へ読み替えない。', '',
        '## 基準遅延と後段の切り分け', '',
        '大容量通信を止めた基準でも期限超過は約半数あり、この経路では「0.5 Mbps以下なら20 ms以内」といった指令保証は得られない。予定送信からのずれp99は全試行で約1–2 msだが、応答RTTの尾部は100 ms級以上である。送信予定のずれ、RTT、ロボット処理時間を同一の指標にまとめず、後続の実ROS 2と省電力比較で遅延箇所を切り分ける。今回の観測から原因を特定していない。', '',
        '## SDR画像とロボコン運用への示唆', '',
        '共通ゲイン・共通色尺度の反復1では、自チームの要求0・0.5・2 MbpsのいずれにもCh6付近の受信エネルギーが見える。他チームが負荷中なので、要求0でも帯状の信号が存在する。色が似ていても指令の期限超過と実受信量は異なる。SDRは周波数上のエネルギーの重なりを示し、アプリの通信ログは指令が間に合ったかを示す。両方を組み合わせることで、緑の帯を通信成功と取り違えずに干渉条件を説明できる。', '',
        'C5は間欠取得で、FFTはDC除去・Hann窓・1024点、受信値は未校正dBFSである。緑の割合は占有率ではなく、個々のI/Q取得を指令パケットと厳密に時刻照合した結果でもない。', '',
        'ロボコンの事前検証では、カメラや点群を同時に流した状態で、指令の期限超過・欠落・最長更新途絶を測ることが有用である。チャネル分離、データ量制限、生成周期、QoS、省電力設定は別々に介入して比較する。実センサ・モータを使っていないため、今回の数値を停止期限の安全性や大会会場での性能保証に用いない。', '']
    shape_path = DATA/'shape/summary.json'
    if shape_path.exists():
        shape = json.loads(shape_path.read_text())
        shape_manifest = json.loads((ROOT/'experiments/data/manifest.json').read_text())['operational']['shape']
        assert shape_manifest['trials'] == 36 and len(shape) == 12 and all(value['runs'] == 3 for value in shape.values())
        lookup = {(value['condition']['other_channel'], value['condition']['requested_mbps'],
                   value['condition']['generation_period_ms']): value for value in shape.values()}
        extra = ['', '## 生成周期の比較', '',
            f"流量比較とは別に、同じversion7・helper version2で36試行・12条件・各3反復を新たに取得した。全{shape_manifest['control_sent']}指令、{shape_manifest['control_received']}応答、{shape_manifest['iq_snapshots_original']} I/Q取得。0.5/1 Mbpsの要求量を固定し、TCP byteの生成周期100/10 msを比較する。", '',
            '| 他チームCh | 要求 [Mbps] | 生成周期 [ms] | RTT統合p99 [ms] | 20 ms期限超過 [%] | 自チーム実受信平均 [Mbps] | 他チーム実受信範囲 [Mbps] |',
            '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
        for channel in (6, 7, 11):
            for rate in (.5, 1):
                for period in (100, 10):
                    value = lookup[channel, rate, period]
                    extra.append(f"| {channel} | {rate:g} | {period} | {value['pooled_p99_ms']:.2f} | {value['deadline20_pct']:.2f} | {rate_mean(value):.3f} | {min(value['delivered_other_mbps']):.3f}–{max(value['delivered_other_mbps']):.3f} |")
        extra += ['', '### 同じ平均要求量と通信品質', '']
        for channel in (6, 7, 11):
            before = lookup[channel, 1, 100]; after = lookup[channel, 1, 10]
            extra.append(f"要求1 Mbps・他チームCh{channel}では、100→10 msへの変更で期限超過{before['deadline20_pct']:.2f}→{after['deadline20_pct']:.2f}%、RTT統合p99 {before['pooled_p99_ms']:.2f}→{after['pooled_p99_ms']:.2f} ms、実受信平均{rate_mean(before):.3f}→{rate_mean(after):.3f} Mbpsだった。")
        extra += ['',
            '生成周期を小さくする操作は、同じ平均要求量を小分けにする介入である。ただしTCP・OS・MACはbyteをまとめ直せるため、10 ms化でRFの送信が均等になったとは実証していない。画像フレームを丸ごと送る方式と圧縮ストリームを一定量ずつ出す方式に着目するきっかけになるが、実映像・ROS 2のQoS・CPU負荷が異なるシステムへ今回の絶対値を移さない。', '',
            '実受信量と他チームの負荷実現度も条件間で異なる。期限超過が低下した条件は平均Mbpsだけでは説明できない通信の時間構造を調べる候補になる一方、3反復の変動と反対の変化を示す条件も残して比較する。チャネル、流量、生成周期を一つの介入にまとめず、ロボコンの指令期限に対して個別に検証する。', '',
            '周期比較の青・緑の図は要求0.5 Mbpsの反復1を全チャネル・両周期で事前指定し、共通ゲインと色尺度で並べる。色の密度から送信周期の実現度や通信成功率を計算しない。', '']
        lines.extend(extra)
    manifest = json.loads((ROOT/'experiments/data/manifest.json').read_text())
    for notes in (ros2_notes, power_notes, espnow_long_notes, placement_notes):
        lines.extend(notes(manifest))
    target = ROOT/'docs/operational-results.md'
    temporary = target.with_suffix('.md.tmp')
    temporary.write_text('\n'.join(lines)+'\n')
    temporary.replace(target)


if __name__ == '__main__':
    main()
