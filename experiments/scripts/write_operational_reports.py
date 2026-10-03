#!/usr/bin/env python3
"""Integrate checked operational notes while keeping exactly two report sources."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BEGIN = '% BEGIN OPERATIONAL STUDY'
END = '% END OPERATIONAL STUDY'


def escape(text):
    mapping = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%',
               '$': r'\$', '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}',
               '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}
    return ''.join(mapping.get(char, char) for char in text)


def inline(text):
    output = []; cursor = 0
    for match in re.finditer(r'\[([^\]]+)\]\((https?://[^)]+)\)', text):
        output += [escape(text[cursor:match.start()]),
                   r'\href{'+escape(match[2])+r'}{'+escape(match[1])+'}']
        cursor = match.end()
    output.append(escape(text[cursor:]))
    return ''.join(output)


def convert_notes(text):
    """Convert our generated plain Markdown; tables fit within the page width."""
    lines = text.splitlines(); output = []; index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith('# '):
            index += 1; continue
        if line.startswith('## '):
            output.append(r'\section{' + escape(line[3:]) + '}')
        elif line.startswith('### '):
            output.append(r'\subsection{' + escape(line[4:]) + '}')
        elif line.startswith('| '):
            rows = []
            while index < len(lines) and lines[index].startswith('| '):
                cells = [cell.strip() for cell in lines[index].strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?', cell) for cell in cells):
                    rows.append(cells)
                index += 1
            output += [r'\begin{center}\small\begin{adjustbox}{max width=\linewidth}',
                       r'\begin{tabular}{' + 'l' * len(rows[0]) + r'}\toprule']
            for row_index, row in enumerate(rows):
                output.append(' & '.join(escape(cell) for cell in row) + r'\\')
                if row_index == 0:
                    output.append(r'\midrule')
            output += [r'\bottomrule\end{tabular}\end{adjustbox}\end{center}']
            continue
        else:
            output.append(inline(line))
        index += 1
    return '\n'.join(output)


def figure(name, caption):
    return (r'\begin{figure}[htbp]\centering\includegraphics[width=\linewidth]{'
            '../experiments/figures/operational/' + name + '.pdf}'
            r'\caption{' + escape(caption) + r'}\end{figure}')


def radio_explanations(source):
    """Keep mechanism, measured effects and unmeasured causes distinct."""
    for tag in ('BLE CHANNELS', 'ESPNOW CHANNELS'):
        source = re.sub(r'% BEGIN '+tag+r'.*?% END '+tag+r'\n?', '', source, flags=re.S)
    source = re.sub(r'^BLEの広告は2402・2426・2480 MHz、接続通信はデータチャネルを使う[^\n]*\n', '', source, flags=re.M)
    team = json.loads((ROOT/'experiments/data/two-team/summary.json').read_text())
    ble = [team['ble-heavy-'+kind] for kind in ('off', 'advert', 'data')]
    own_rates = [sum(row['delivered_own_mbps'])/len(row['delivered_own_mbps']) for row in ble]
    notify = [team['ble-'+own+'-data']['delivered_other_mbps'] for own in ('off', 'heavy')]
    notify_rates = [sum(values)/len(values) for values in notify]
    explanation = r'''
% BEGIN BLE CHANNELS
\subsection{広告と接続通信で異なるチャネルの使い方}
周波数ホッピングは、送受信機が約束した順序で使用周波数を時間とともに切り替えることである。
周波数帯全体へ同時に広い信号を送ることではない。BLEは2.4 GHz帯に2 MHz間隔の40チャネルを持ち、
今回使ったlegacy広告には2402・2426・2480 MHzの3広告チャネル、接続後の通信には37データチャネルを使う\cite{blePrimer}。
したがって「広告をONにした」と「接続後のホッピング通信を高負荷で動かした」は別の条件である。

GATT通知のような接続通信では、接続イベントの開始ごとに両端が同じデータチャネルを選ぶ。
1つのイベント中の全パケットが毎回別周波数へ飛ぶという意味ではない。
AFH（適応的周波数ホッピング）は、使用するチャネルの集合を更新し、通信しにくい周波数を避ける仕組みである\cite{bleAFH}。
一方、今回のlegacy広告は3広告周波数を使用し、接続後と同じ37チャネルのAFHとして扱わない。
今回、チャネルマップや更新時刻を取得していないため、Wi-Fiを検出して特定チャネルを除外したかは確認していない。

\subsection{ホッピングしてもWi-Fiと干渉し得る理由}
Wi-Fi Ch6の中心は2437 MHz、名目20 MHzの範囲は2427--2447 MHzである。
その内部にもBLEデータチャネルがある。BLEがそこへホップした時にWi-Fiも同時送信すれば、
周波数と時間が重なり、受信失敗や再送につながり得る\cite{bleAFH}。
ホッピングは同じ悪い周波数へ留まり続けることを減らすが、全ての送信をWi-Fiから切り離す仕組みではない。
影響は重なる周波数だけでなく、送信の頻度・長さ、両送信機の強さ、受信側での信号対干渉比によって変わる。

Wi-Fiの幅を20から40 MHzへ広げると、BLEと重なり得る周波数の範囲も広がる。
ただし達成レートが上がれば同じデータを短時間で送り終える可能性もあるため、幅だけで衝突回数や劣化量は決められない。
今回の幅比較は別チームWi-Fi同士の実験であり、BLEとの共存を20/40 MHzで直接比較した実験ではない。
これは今回の観測を読むための機構説明で、幅とBLE干渉の因果効果を測定したという主張ではない。

\subsection{Wi-FiからBLEへ、BLEからWi-Fiへの実測変化}
'''
    explanation += ('Wi-Fi大容量通信中のRTT p99は、BLE停止・広告・通知の順に'+
                    '／'.join(f'{row["pooled_p99_ms"]:.2f}' for row in ble)+
                    ' msと近い。一方、20 ms期限超過は'+
                    '／'.join(f'{row["deadline20_pct"]:.2f}' for row in ble)+r'\%、Wi-Fiの実受信平均は'+
                    '／'.join(f'{rate:.3f}' for rate in own_rates)+' Mbpsだった。\n')
    explanation += (f'BLE通知の実受信平均は、Wi-Fi待機時{notify_rates[0]:.3f} Mbpsから負荷時{notify_rates[1]:.3f} Mbpsへ変化した。\n')
    explanation += r'''
したがって「Wi-Fi p99がほぼ同じなので影響なし」とは言えない。
指令の期限超過、Wi-Fiの配送量、BLE側の配送量を別々に見る必要がある。
同時に、各条件3反復で実負荷も変動しており、この変化を全てRF衝突やAFHの効果へ帰属できない。
通知の受付エラーも無線衝突数ではない。干渉機構を同定するには、再送、チャネルマップ、
周波数ごとの失敗を対応付ける記録が必要で、今回は取得していない。

図の短い細線は、広帯域Wi-Fiと異なる狭帯域送信を読む手掛かりである。
ただしC5の取得は間欠的で、図は2450--2470 MHzの一部のみを拡大している。
広告の3周波数はいずれもこの拡大範囲の外であり、広告の図で帯が見えないことは送信停止の証拠ではない。
全ての細線をBLEと同定したり、ホッピングの連続した軌跡やAFHで避けたチャネルを図から復元したりはできない。
同一チップ内の無線資源の共存制御、Bluetooth Classic、音声通信とは分けた実験である。
% END BLE CHANNELS
'''
    marker = '% BEGIN ESPNOW STUDY'
    source = source.replace(marker, explanation+'\n'+marker, 1)
    explanation = r'''
% BEGIN ESPNOW CHANNELS
\subsection{ESP-NOWの固定チャネルとBLEとの相違}
ESP-NOWはWi-Fiの無線部からvendor-specific action frameを直接送る方式であり、
標準でBLEのような自動的な周波数ホッピングを行う方式ではない\cite{espnowGuide}。
今回のESP32送受信機は2.4 GHzの同じWi-Fiチャネルに合わせて動作させた。
peerのchannel=0は現在の無線チャネルを使う指定であり、空いている周波数を自動探索する指定ではない。
送受信機のチャネルが一致しなければ通信できない。

先行試験ではCh6・Ch7・Ch11へ試行間で切り替え、それぞれの30秒試行中は固定した。
これはホッピング実験ではなく、試行ごとに設定した固定チャネルの比較である。
後続の600秒試験と配置比較は、ESP-NOWと別系統Wi-FiをともにCh6へ固定した。
試行前後の実チャネル読出しと取得コードでこの設定を確認しており、途中で自動的に干渉を回避した結果とは解釈しない。

\subsection{ルーターを経由しなくてもWi-Fiと干渉し得る理由}
ESP-NOWはAPによる中継を省けるが、同じ周波数帯の送信時間から独立するわけではない。
同一または重複チャネルのWi-Fiと同時に使うと、送信待ちや受信失敗・再送が増える可能性がある。
Ch6とCh7は中心周波数が5 MHzしか離れず、チャネル番号が違っても帯域は大きく重なる。
1 Mbpsは今回設定したPHYのbitrateであり、電波の占有幅が1 MHzという意味ではない。

別の無線機同士なら、自チームWi-FiとESP-NOWへ分離したチャネルを割り当てる構成を検討できる。
一方、同じESP32の無線部でAPへのWi-Fi接続も併用する場合、ESP-NOWのチャネルを接続APに合わせる必要がある\cite{espnowFAQ}。
その構成で「Wi-FiはCh6、ESP-NOWはCh11を同時に固定する」とは設定できない。
今回の独立した無線機によるチャネル比較と、同一チップ内の併用を区別する必要がある。

\subsection{Wi-Fiとの相互影響について今回言えること}
先行30秒試験では、Wi-Fi負荷を加えると同一Ch6のESP-NOW RTT p99が9.4から85.6 msへ変わった。
ただし同じCh6負荷中でも反復p99は8.6--123.8 msと変動した。
後続600秒試験では100 Hz・Wi-Fi待機から負荷へのp99が10.711から9.264 msであり、
同一チャネルなら必ず同じ量だけ悪化するという結果ではない。
実装・測定時間・配置の異なる系列をまとめず、指令の期限超過と最長更新途絶も比較する。

逆方向については、共存中のWi-Fi実受信量も保存したが、ESP-NOWを停止した同一条件のWi-Fi単独基準は測っていない。
したがって「ESP-NOWがWi-Fiを何\%遅くした」「Wi-Fiへ影響しない」は今回の記録から定量的に断定できない。
これはWi-Fi負荷の中でESP-NOW指令が間に合うかを中心に評価した実験である。
また指令とその応答はどちらも無線時間を使い、指令周期を短くするとヘッダ・応答・送信待ちも増える。
小さいpayloadのMbpsだけを見て無視できる負荷と決めず、映像と同時に動かして指令更新の尾部を調べることがロボコンでは有用である。
% END ESPNOW CHANNELS
'''
    marker = r'\subsection{ロボコンへの適用条件}'
    source = source.replace(marker, explanation+'\n'+marker, 1)
    if r'\bibitem{bleAFH}' not in source:
        source = source.replace(r'\begin{thebibliography}{99}', r'\begin{thebibliography}{99}'+'\n'+r'\bibitem{bleAFH} Bluetooth SIG, How Bluetooth technology uses adaptive frequency hopping to overcome packet interference, \url{https://www.bluetooth.com/blog/how-bluetooth-technology-uses-adaptive-frequency-hopping-to-overcome-packet-interference/}.'+'\n'+r'\bibitem{espnowFAQ} Espressif, ESP-NOW FAQ, \url{https://docs.espressif.com/projects/esp-faq/en/latest/application-solution/esp-now.html}.')
    source = re.sub(r'^\\bibitem\{bleAFH\}[^\n]*', lambda _: r'\bibitem{bleAFH} '+
        r'\href{https://www.bluetooth.com/blog/how-bluetooth-technology-uses-adaptive-frequency-hopping-to-overcome-packet-interference/}{Bluetooth SIG, How Bluetooth technology uses adaptive frequency hopping to overcome packet interference.}', source, flags=re.M)
    return source


def write_full(manifest):
    path = ROOT/'reports/full.tex'; source = path.read_text()
    if BEGIN in source:
        a = source.index(BEGIN); b = source.index(END, a)+len(END)
        source = source[:a]+source[b:]
    if r'\usepackage{adjustbox}' not in source:
        source = source.replace(r'\begin{document}', r'\usepackage{adjustbox}'+'\n'+r'\begin{document}', 1)
    body = convert_notes((ROOT/'docs/operational-results.md').read_text())
    body = re.sub(r'\\subsection\{保存待ちによる取得中断と補足記録\}.*?(?=\\section\{)', '', body, flags=re.S)
    figures = {
        '生成周期の比較': [('rate-limit-metrics', '流量制限の通信性能。小さい点は各反復、大きい点は統合値。'), ('rate-limit-blue-green', '他チーム通信中の流量比較。共通ゲイン・未校正dBFS。')],
        '実ROS 2のQoSと指令応答': [('payload-shaping-metrics', '同じ平均要求量で生成周期を変更した比較。'), ('payload-shaping-blue-green', '生成周期比較の青緑SDR画像。縦軸は間欠取得順。')],
        '省電力設定への介入と端末内時間': [('ros2-qos-metrics', '実ROS 2のQoS比較。センサQoSのみ変更し、指令QoSは固定。'), ('ros2-update-gaps', '画像と点群の各unique sequence初回受信の更新間隔。'), ('ros2-blue-green', '実ROS 2通信と別チーム負荷。色から配送成功や占有率は計算できない。')],
        'ESP-NOWの指令周期と長時間更新の安定性': [('power-save-timing', '省電力ON/OFFと同じ端末時計内の処理時間。'), ('power-save-blue-green', '省電力比較の実測SDR画像。')],
    }
    for heading, pairs in figures.items():
        marker = r'\section{'+heading+'}'
        body = body.replace(marker, '\n'.join(figure(*pair) for pair in pairs)+'\n'+marker)
    for name, caption in [('espnow-long-metrics', '600秒ESP-NOW試行。19試行、条件ごと2〜3反復。'), ('espnow-long-timeline', '10秒ごとの推移。縦軸の尺度は指令周期ごとに異なる。'), ('espnow-long-blue-green', '100 HzのWi-Fi待機と負荷、反復1。無線観測は間欠的である。')]:
        body += '\n'+figure(name, caption)
    if 'placement' in manifest['operational']:
        body += '\n'+figure('placement-metrics', '各10秒の手動配置比較。RSSIは届いた最新パケットの値。')
        body += '\n'+figure('placement-blue-green', '各配置の負荷反復1。C5と応答機の距離も変化している。')
    block = BEGIN+'\n'+r'\section*{追加運用評価の実測と考察}'+'\n'+body+'\n'+r'\clearpage\section*{先行通信実験とSDR受信評価}'+'\n'+END+'\n'
    position = source.index(r'\section{')
    source = source[:position]+block+source[position:]
    start = source.index(r'\begin{abstract}'); end = source.index(r'\end{abstract}', start)
    trial_count = sum(manifest[key]['trials'] for key in ('robotics', 'two_team', 'espnow'))
    trial_count += sum(value['trials'] for value in manifest['operational'].values())
    abstract = ('ロボコンで操縦指令・映像・点群がWi-Fiを共有し、他チームも通信する状況を室内で評価した。'
                '同一・隣接・分離チャネルと20/40 MHz幅、Wi-Fiと独立BLE通信、流量・生成周期、'
                '実ROS 2 Humble／JazzyのImage／PointCloud2のQoS、省電力設定、ESP-NOWの指令周期を比較する。'
                f'構成の異なる{trial_count}通信試行と115受信観測系列を区別して統合し、実測青緑SDR画像と'
                '応答期限・欠落・更新途絶を対応づける。ESP-NOW長時間系列は各600秒の19試行で、'
                '使用者の終了希望により残り5試行を省略した。実ロボット・実センサは用いていない。')
    source = source[:start]+r'\begin{abstract}'+'\n'+abstract+'\n'+source[end:]
    source = source.replace('ESP32-1/2間75 cmを維持した。', '配置は同じ机上で固定した。先行記録の距離は個々の中心間距離を再確認していない。')
    source = source.replace('ESP32-1/2間75 cm、C5から両ボードへ約40 cm・90 cm、観測PCとラップトップ2間約30 cm。距離とボード番号の対応、ESP32-3の距離は未測定であり、距離掃引ではない。', '配置は同じ机上で固定し、使用者は各機器おおむね30 cmと報告した。個々の中心間距離と姿勢は先行系列で再確認しておらず、距離掃引ではない。')
    source = re.sub(r'配置は利用者申告による概数で、追加ESP32間75 cm、.*?配置は測定中に変えない。', '配置は同じ机上で固定し、使用者は各機器おおむね30 cmと報告した。各中心間距離と姿勢はこの先行系列では実測していない。後続の手動配置比較の距離を遡って代入しない。', source)
    source = source.replace('実験終了時に両PCのWi-Fiと有線共有を復元し、', '先行系列の終了時に両PCのWi-Fiと有線共有を復元し、')
    if r'\bibitem{rosQoS}' not in source:
        source = source.replace(r'\begin{thebibliography}{99}', r'\begin{thebibliography}{99}'+'\n'+r'\bibitem{rosQoS} ROS 2 Jazzy, Quality of Service settings, \url{https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Quality-of-Service-Settings.html}.')
    source = radio_explanations(source)
    source = source.replace(r'\section{主実験の結論と公開データの範囲}', r'\section{主実験の結論}')
    source = source.replace(r'\section{統合した結論と再現性}', r'\section{統合した結論}')
    source = re.sub(r'^主比較42、周期Wi-Fi9、BLE18、ESP-NOW18の計[^\n]*公開した相対時刻[^\n]*\n', '', source, flags=re.M)
    source = re.sub(r'^公開資料は、実験日ではなく[^\n]*\n', '', source, flags=re.M)
    path.write_text(source)


def write_twitter(manifest):
    path = ROOT/'reports/twitter.tex'
    preamble = path.read_text().split(r'\begin{document}', 1)[0]
    preamble = preamble.replace(r'\usepackage{balance}', '')
    if r'\usepackage{multicol}' not in preamble:
        preamble += '\n'+r'\usepackage{multicol}'+'\n'
    # Keep the supplied ref.tex preamble and heading font settings. Explicit
    # page breaks keep the social version at three readable pages.
    def image(name, caption, width=r'\linewidth'):
        return (r'\begin{center}\includegraphics[width='+width+
                ']{../experiments/figures/'+name+r'.pdf}\captionof{figure}{'+caption+
                r'}\end{center}')
    team = json.loads((ROOT/'experiments/data/two-team/summary.json').read_text())
    long = json.loads((ROOT/'experiments/data/operational/espnow-long/summary.json').read_text())
    rows = []
    for ch in (6, 7, 11):
        a, b = [team[f'team-heavy-ch{ch}-w20-b{level}'] for level in (0, 1)]
        rows.append(f'{ch} & {a["pooled_p99_ms"]:.1f} / {b["pooled_p99_ms"]:.1f} & '
                    f'{a["deadline20_pct"]:.1f} / {b["deadline20_pct"]:.1f}'+r'\\')
    body = r'''
\begin{document}
\twocolumn[{
\begin{center}{\LARGE\bfseries\sffamily ロボコンの無線通信と帯域共有の実測評価\par}
\vspace{1mm}{\normalsize 他チーム通信・ROS 2・Bluetooth・ESP-NOW\par}
\vspace{.5mm}{\normalsize \ReportAuthor\par}\end{center}
\noindent\fbox{\parbox{\dimexpr\textwidth-2\fboxsep-2\fboxrule}{\small
\textbf{要旨}\quad 指令と大容量データを同時に流し、他チームの通信、チャネル幅、QoS、指令周期を比較した。
実測SDR画像は帯域の重なりを示す。一方、指令が期限内に届くかはアプリの応答記録から評価する。
チャネルを分離しても端末内部や同じチーム内の遅延は残り、帯域幅・平均速度・接続表示だけでは操縦品質を判断できなかった。}}\vspace{2mm}}]
\balance
\section{目的と実験方法}
スマートフォンからの指令、カメラ映像、LiDAR点群を同じWi-FiとROS 2で運ぶロボットを想定する。
自チーム内だけでなく、隣のチームも大容量通信中の条件を作った。
観測PC（Intel BE200）がCh6・20 MHz AP、ラップトップ2（MT7921E）がロボット役、
ラップトップ1（Intel AX210）が有線でインターネットを共有する。
ESP32 3台は指令、別チームAP／STA、独立BLE、ESP-NOWへ順次使用した。

先行試験は64 byte・100 Hz UDP指令とTCP模擬データをSTA→AP→STAへ通した。
追加の実ROS 2試験はPC AP→STA（指令側Humble・ロボット側Jazzy、双方CycloneDDS）、ImageとPointCloud2を各10 Hzで生成する。
合成センサの要求payloadは60.54 Mbps、実受信は約47--55 Mbpsだった。
実カメラ、スマートフォン、モータは使用していない。経路の異なる系列を混ぜて方式の順位を決めない。

1試行30秒・3反復を基本とし、ESP-NOW長時間系列だけ600秒・2--3反復とする。
RTT p99は応答が戻った指令の分位点、20 ms期限超過率は\textbf{全予定指令が分母で欠落も含む}。
最新sequenceの更新途絶も評価する。20 msは比較目標で、ロボットの安全限界ではない。
環境の反復数はパケット数とは区別する。

\section{他チーム通信とチャネル配置}
\begin{center}\captionof{table}{自チーム大容量TCP中。値は他チーム待機／負荷。各3反復。}
\small\begin{tabular}{@{}crr@{}}\toprule 他Ch & RTT p99 [ms] & 20 ms超過 [\%]\\\midrule
'''+ '\n'.join(rows)+r'''
\bottomrule\end{tabular}\end{center}
他チームを負荷へ変えると、p99の増分は同一Ch6で約23 ms、隣接Ch7で約9 ms、分離Ch11で約1 msだった。
\textbf{別のチャネル番号でも帯域が分かれるとは限らない}。Ch6とCh7は中心が5 MHzしか離れず、20 MHz幅で大きく重なる。
同一Chが今回最も遅く、隣接が常に最悪という結果ではない。

同一帯域の送信待ち、部分重複による受信妨害、再送などが候補になる\cite{rf}。
再送数やキャリアセンスを直接測っておらず、色だけで原因を特定しない。
他チーム実受信量も約0.4--4.7 Mbpsと異なるため、等しい干渉電力や空中時間の比較ではない。

\subsection{チャネル幅と周波数の余裕}
Ch1の20 MHzは名目上2402--2422 MHz、Ch6は2427--2447 MHz。
Ch1＋副Ch5の40 MHzでは約2402--2442 MHzとなりCh6へ重なる。
20→40 MHzでp99は128.6→127.5 ms、期限超過は55.0→56.8\%だった。
帯域が広いほど同時配置の余裕は減るが、転送が速くなれば同じデータの送信時間は短くなる。
\textbf{広いほど必ず悪いとは言えず、実受信量と指令期限を併せて判断する}。
今回の幅比較は他チームAPの介入で、自チームAPの最高速度比較ではない。

\subsection{基準性能の確認}
操縦のみ・他待機でもUDPのp99は117--120 ms、20 ms超過は47--49\%だった。
既に目標を満たさない構成なので、全遅延を他チームへ帰属しない。
RTTを2で割って片道値にすることや、別PC時計の差を未同期で使うことはできない。
\clearpage
\twocolumn[{
'''+image('two-team/two-team-blue-green-compact',
           '自チームCh6で指令＋大容量通信。他チーム負荷を同一・隣接・分離へ変更。反復1、共通ゲインと色尺度。', r'.98\textwidth')+r'''}]
\section{流量・生成周期・ROS 2の比較}
追加の流量試験では他チームを負荷中に固定し、自チームTCPの要求量を0--2 Mbpsへ変えた。
同一Ch6の0→1 Mbpsで20 ms超過は54.08→72.61\%、実受信平均は1.007 Mbpsだった。
2 Mbps要求でも実受信は1.105 Mbpsにとどまり、生成byteが未送信で積み上がった。
\textbf{設定Mbpsを達成速度や無線負荷とみなさず、生成・送信受付・実受信を分ける}。

同じ1 Mbps要求で生成周期100→10 msへ変えると、Ch6の超過は63.47→59.42\%だったが、
Ch7では53.88→53.88\%だった。小分け生成は常に改善する結果ではなく、TCPやOSはbyteをまとめ直せる。
平均量に加え時間的な集中と端末の待ち行列を評価する必要がある。

\subsection{QoSと大容量トピック}
指令QoSはreliable・深さ10に固定し、センサだけbest effort／reliable、深さ1／10を比較した。
指令のみの20 ms超過は約45\%、センサ追加時は約70--80\%となった。
best effort・深さ1でも同一Ch6のp99は145.57 ms、超過77.68\%だった。
深さ1はDDSの履歴設定であり、無線待ち行列を1つにしたり指令を優先したりする設定ではない\cite{ros}。
画像のunique sequence初回受信間隔には最大3.33秒の途絶もあった。
受信間隔は観測できたが、生成から到着までのデータの古さは未同期時計から計算していない。

\subsection{省電力と遅延の切り分け}
端末の省電力ON／OFFを実際に切り替え、前後のreadbackを確認した。
指令のみでは両方p99約103--109 msが残った。一方センサ負荷・他Ch11ではOFF→ONで163.38→248.66 msだった。
省電力OFFだけで今回の遅延は解消しない。
予定送信のずれは約0.5--1 ms、publish呼出し約0.08 ms、ロボット内の応答前処理約0.003--0.007 msだった。
publishが速くても、その後のDDS・OS・MACの待ちは残る。p99を引き算して原因の寄与を割り当てない。

\section{SDR画像の読み方}
C5：80 MS/s、16,380 I/Q、アナログ帯域48 MHz、ゲイン20、FFT1024。
各行約205 $\mu$s、名目RF観測時間比約0.4\%であり、縦軸は\textbf{間欠取得順}。
青緑は未校正dBFSで、同じ図の共通尺度内で比較する。
緑の割合を占有率、通信成功率、絶対dBmへ換算しない。
Ch11の一部は名目アナログ帯域の端へかかり、弱い色を無干渉の証拠としない。
画像で帯域の重複、アプリ記録で届く時刻、実受信量で負荷の実現度を確かめる。
\clearpage
\twocolumn[{
'''+image('two-team/ble-narrow-blue-green',
           'BLE停止・広告・GATT通知。2450--2470 MHzの拡大、反復1。この図は−90〜−60 dBFSで前ページとは尺度が異なる。', r'.91\textwidth')+r'''}]
\section{Bluetooth LEとの共存}
\subsection{広告と接続後の周波数の使い方}
今回の広告は2402・2426・2480 MHzの3周波数を使う方式である。
接続後のGATT通知は、2 MHz間隔の37データチャネルから、接続イベントごとに周波数を選ぶ。
\textbf{ホッピングは広帯域を一度に送ることではなく、狭い信号の送信先を時間で切り替えること}である。
AFHは使用チャネル集合を更新して混雑した周波数を避ける仕組みだが、今回その更新は測っていない\cite{ble}。

Wi-Fi Ch6の名目20 MHz帯域2427--2447 MHz内にもBLEデータチャネルがある。
同じ周波数へ同時に送れば干渉し得るため、\textbf{ホッピングしてもWi-Fiと無関係にはならない}。
40 MHz化は重なり得る周波数を増やすが、実送信時間も変わるので劣化量は幅だけで決まらない。

\subsection{双方の実測性能}
独立したESP32 2台でBLE停止・20 ms設定の広告・BLE 1M通知を各3反復比較した。
Wi-Fi大容量通信中のp99は停止126.2／広告126.0／通知126.3 msと近いが、20 ms超過は54.6／58.2／56.8\%だった。
Wi-Fi実受信平均は1.34／1.50／1.19 Mbps、BLE通知はWi-Fi待機0.365→負荷0.326 Mbpsだった。
\textbf{p99が同じでも、期限超過や双方の配送量まで同じではない}。
少数反復・実負荷の違いがあり、これを衝突やAFHの効果だけに帰属しない。
図の細線は狭帯域成分の手掛かりで、全てをBLEと同定したものではない。
間欠取得から連続ホッピングを復元せず、同一チップの共存制御やBluetooth音声も未検証である。

\section{ESP-NOW指令の周期と更新途絶}
\subsection{固定チャネルとWi-Fiの共有}
\textbf{ESP-NOWは標準でBLEのように自動ホッピングしない}。
Wi-Fiの無線部から専用action frameを送り、送受信機は同じチャネルに合わせる。
設定のchannel=0は現在のWi-Fiチャネルを使う意味で、自動探索ではない\cite{espnow}。
先行試験のCh6・7・11は試行間で変更し、各試行中は固定した。
長時間試験と配置比較はCh6固定である。

APを通らず指令経路を分けても、同一・重複帯域ではWi-Fiと送信時間を共有する。
別無線なら分離チャネルを選べるが、同じESP32でAP接続も併用する場合はAPのチャネルに合わせる必要がある\cite{espnowFAQ}。
指令の回数を増やすとヘッダや応答を含む送信機会も増えるため、payloadのMbpsだけで影響を判断しない。

\subsection{今回確認した影響と指令周期}
2台間で64 byteを往復し、20・50・100・200 Hz、別系統Wi-Fi Ch6の待機／TCP負荷を各600秒測った。
使用者の終了希望で19試行（8条件、各2--3反復）とし、残り5試行は未実施。
960,000予定指令を全て送信し、959,997 unique応答を記録した。
MAC送信成功はアプリ応答やアクチュエータ動作成功とは異なる\cite{espnow}。
\begin{center}\captionof{table}{長時間系列のWi-Fi負荷条件。欠落も超過に含む。}
\small\begin{tabular}{@{}rrrr@{}}\toprule Hz & p99 [ms] & 20 ms超過 [\%] & 最大更新途絶 [ms]\\\midrule
'''
    for hz in (20, 50, 100, 200):
        row = long[f'op-espnow-long-hz{hz}-wifiheavy-ch6']
        gap = max(value['maximum_increasing_sequence_gap_ms'] for value in row['run_application'])
        body += f'{hz} & {row["pooled_rtt_p99_ms"]:.2f} & {row["planned_deadline20_pct"]:.4f} & {gap:.1f}'+r'\\'+'\n'
    body += r'''\bottomrule\end{tabular}\end{center}
100 Hz・負荷中はp99 9.26 msだったが、200 Hzでは14.26 ms、10秒窓の超過が集中する区間もあった。
\textbf{指令周期を短くすれば必ず通信が良くなるわけではない}。
20 Hzの通常更新間隔自体が50 msであるため、1応答の20 ms期限と継続更新の周期は別に設計する。
200 Hzのpayloadは片道0.1024 Mbpsだが、ヘッダ・ACK・送信待ちも必要で空中時間とは一致しない。
先行30秒試験のCh6はWi-Fi待機→負荷でp99が9.4→85.6 msだったが、負荷中の反復差も大きい。実装の異なる長時間系列へ混ぜない。
Wi-Fiの実受信は約1.7--2.7 Mbpsだった。
ただしESP-NOW停止時の同一条件Wi-Fi基準がなく、\textbf{ESP-NOWがWi-Fi速度を何\%下げたかは測定していない}。
主にWi-Fi負荷中にESP-NOW指令が間に合うかを評価した。
AP中継UDP／ROS 2とは無線経路も異なり、方式だけの勝敗は決められない。
'''
    if 'placement' in manifest['operational']:
        placement = json.loads((ROOT/'experiments/data/operational/placement/summary.json').read_text())
        body += r'\subsection{短時間の配置比較}'+'\n'
        farther = json.loads((ROOT/'experiments/data/operational/placement/op-placement-farther-wifiheavy-ch6-r1.json').read_text())['layout']['placement']['distances_cm']
        body += ('送受信75 cm、C5→送信45 cm、C5→応答95 cmを基準に、応答機の90°回転、手による遮蔽、'
                 f'送受信{farther["sender_echo"]:g} cmへの距離変更、基準復帰を各10秒・3反復で比較した。\n')
        values = []
        for position, label in [('baseline-before', '基準前'), ('rotated', '回転'), ('obstructed', '遮蔽'), ('farther', '距離変更'), ('baseline-after', '基準後')]:
            row = next(value for value in placement.values() if value['condition']['placement_id'] == position and value['condition']['wifi'] == 'heavy')
            values.append(f'{label}{row["pooled_rtt_p99_ms"]:.2f}')
        body += '負荷中p99は'+ '／'.join(values)+' msで、全配置の負荷中20 ms超過は0'+r'\%。'+'\n'
        body += '全30試行・30,000指令で応答欠落はなかった。基準復帰後もp99が下がったため、回転や遮蔽による改善とは断定できない。届いた最新パケットのRSSIだけで欠落時の感度は判断できない。C5までの距離、ケーブルや反射を含め、短時間の結果を到達距離の保証へ広げない。\n'
    body += r'''
\section{ロボコン運用への示唆}
本番前にカメラ・点群を動かし、隣のチームにも通信を流してもらい、単独基準と同条件で比較する。
チャネル分離、生成量、周期、QoS、省電力は一つずつ変え、平均速度と\textbf{期限超過・欠落・最長更新途絶}を残す。
古い指令を追いつくまで送るより、最新指令の扱いと途絶時の動作を設計する。
後者は今回モータで検証しておらず、実機の停止期限は別に確かめる必要がある。

{\footnotesize
\begin{thebibliography}{9}\footnotesize
\bibitem{rf} \href{https://www.cisco.com/c/en/us/td/docs/wireless/controller/9800/technical-reference/wireless-rf-reference-guide.html}{Cisco, Wireless RF Reference Guide.}
\bibitem{ros} \href{https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Quality-of-Service-Settings.html}{ROS 2 Jazzy, Quality of Service settings.}
\bibitem{espnow} \href{https://docs.espressif.com/projects/esp-idf/en/v6.0/esp32/api-reference/network/esp_now.html}{Espressif, ESP-NOW Programming Guide.}
\bibitem{ble} \href{https://www.bluetooth.com/bluetooth-le-primer/}{Bluetooth SIG, Bluetooth LE Primer.}
\bibitem{espnowFAQ} \href{https://docs.espressif.com/projects/esp-faq/en/latest/application-solution/esp-now.html}{Espressif, ESP-NOW FAQ.}
\end{thebibliography}}
\end{document}
'''
    # Multicol balances each page's two text columns without the overfull
    # output boxes produced by balance.sty with ltjsarticle. Keep the supplied
    # margins, heading fonts and column spacing. Full-width measured plots sit
    # outside the two-column text; no floats can spill onto a fourth page.
    # Put fixed-channel mechanics beside the SDR discussion, using the room
    # on page two while keeping the BLE and ESP-NOW measurements on page three.
    a = body.index(r'\subsection{固定チャネルとWi-Fiの共有}')
    b = body.index(r'\subsection{今回確認した影響と指令周期}', a)
    mechanics = body[a:b].replace('固定チャネルとWi-Fiの共有', 'ESP-NOWの固定チャネルとWi-Fiの共有')
    body = body[:a]+body[b:]
    position = body.rfind(r'\clearpage', 0, body.index(r'\section{Bluetooth LEとの共存}'))
    body = body[:position]+mechanics+'\n'+body[position:]
    body = body.replace(r'\begin{document}', r'\begin{document}\onecolumn', 1)
    body = body.replace(r'\twocolumn[{', '')
    body = body.replace('}]\n', '\n'+r'\begin{multicols}{2}'+'\n')
    body = body.replace('\\balance\n', '')
    body = body.replace(r'\clearpage', r'\end{multicols}'+'\n'+r'\clearpage')
    body = body.replace(r'\end{document}', r'\end{multicols}'+'\n'+r'\end{document}')
    body = body.replace(r'\begin{multicols}{2}', r'\begin{multicols}{2}\fontsize{10}{14}\selectfont\raggedcolumns')
    if 'placement' in manifest['operational']:
        marker = r'\end{multicols}'+'\n'+r'\clearpage'
        body = body.replace(marker, r'\end{multicols}'+'\n'+image('operational/placement-blue-green',
            '短い配置比較のWi-Fi負荷・反復1。中心間距離とC5までの距離を併記。共通ゲイン・未校正dBFS。',
            r'.95\textwidth')+'\n'+r'\clearpage', 1)
    path.write_text(preamble+body)


def write_readme(manifest):
    path = ROOT/'README.md'; text = path.read_text()
    a = text.index('## 実験から得られたこと'); b = text.index('## ディレクトリ', a)
    lines = ['## 実験から得られたこと', '',
             '- 自チームの大容量通信中、他チーム負荷によるRTT p99の増分は同一Ch6で約23 ms、隣接Ch7で約9 ms、分離Ch11で約1 msでした。実受信量は条件間で異なり、固定室内配置での比較です。',
             '- 20/40 MHzでは帯域の重なりは広がりましたが、p99は単調に悪化しませんでした。帯域幅と平均Mbpsだけでは操縦品質を決められません。',
             '- 実ROS 2は指令側Humble・ロボット側Jazzy、双方CycloneDDSです。合成Image／PointCloud2を追加すると20 ms期限超過は約45%から約70〜80%へ増えました。センサQoSの深さ1や省電力OFFだけで今回の遅延は解消しませんでした。',
             '- 流量制限・生成周期の変更も比較しました。要求量、送信側受付、実受信、期限超過を分け、未送信データの蓄積を「通信速度を達成」と取り違えないようにします。',
             '- ESP-NOW長時間試験は各600秒、19試行、8条件を2〜3反復です。960,000指令のうちunique応答は959,997件でした。100 Hz負荷中のp99は9.26 ms、200 Hzでは14.26 msで、短い区間に期限超過が集中しました。異なる端末・経路・実装のUDP／ROS 2との方式だけの勝敗は決められません。',
             '- 独立BLEの広告・GATT通知は復号・実受信も確認しました。Wi-Fi p99が近い条件でも、期限超過と双方の配送量は異なりました。広告と接続後のホッピングを分け、今回測っていないAFHの効果だけへ帰属しないように説明しています。', '']
    if 'placement' in manifest['operational']:
        lines += ['- ESP32間で基準前、90°回転、手による遮蔽、75→150 cm、基準復帰を各10秒で比較しました。全30試行・30,000指令で応答欠落はありませんでした。元の配置へ戻した後もp99が低下したため、回転や手だけの改善効果とは断定できません。最新パケットのRSSIと共通尺度の青緑画像も保存しています。', '']
    labels = [('先行操縦通信', manifest['robotics']), ('両チーム・周期Wi-Fi・BLE', manifest['two_team']),
              ('先行ESP-NOW', manifest['espnow'])]
    titles = {'limit':'流量制限', 'shape':'生成周期', 'ros2':'実ROS 2 QoS',
              'power':'省電力ON／OFF', 'espnow-long':'ESP-NOW長時間', 'placement':'短時間配置比較'}
    labels += [(titles[key], value) for key, value in manifest['operational'].items()]
    lines += ['| 系列 | 試行数 | 予定・要求指令 | unique応答 | I/Q取得 |',
              '| --- | ---: | ---: | ---: | ---: |']
    for label, value in labels:
        planned = value.get('control_planned', value.get('control_sent'))
        lines.append(f'| {label} | {value["trials"]} | {planned:,} | {value["control_received"]:,} | {value["iq_snapshots_original"]:,} |')
    total = sum(value['trials'] for _, value in labels)
    lines += ['', f'計{total}通信試行と、構成を区別した115受信観測系列を統合しました。長時間試験は使用者の終了希望で残り5試行を省略し、24試行完了とは扱いません。保存待ち超過の別600秒記録は補足として保持し、正式19試行へ混ぜません。実センサやモータの安全停止は測定していません。', '',
              '青〜緑は未校正のFFT電力（dBFS）。各行は約205 µsの間欠取得で、占有率や通信成功率ではありません。', '',
              '[統合した結果と考察](docs/operational-results.md) · [流量・生成周期](docs/operational-method.md) · [ROS 2](docs/ros2-method.md) · [長時間ESP-NOW](docs/espnow-long-method.md) · [配置比較](docs/placement-method.md)', '', '']
    text = text[:a]+'\n'.join(lines)+text[b:]
    text = text.replace('ESP32-C5で受信したスペクトルと、操縦を模した100 Hz UDP通信の遅延を対応づけた室内実験です。',
                        'ESP32-C5のスペクトルと、操縦を模したUDP・実ROS 2・ESP-NOWのアプリ応答を比較した室内実験です。')
    text = text.replace('`espnow`はESP-NOW指令と外部Wi-Fi比較です。', '`espnow`は先行ESP-NOW指令と外部Wi-Fi比較、`operational`は流量・周期・ROS 2・省電力・長時間・配置比較です。')
    path.write_text(text)


if __name__ == '__main__':
    manifest = json.loads((ROOT/'experiments/data/manifest.json').read_text())
    write_full(manifest)
    write_twitter(manifest)
    write_readme(manifest)
