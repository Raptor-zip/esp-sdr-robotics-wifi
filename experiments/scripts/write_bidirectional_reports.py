#!/usr/bin/env python3
"""Explain why each experiment matters and integrate controlled mutual effects."""
import json
from pathlib import Path
import re

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'experiments/data/coexistence'


def read(name):
    return json.loads((DATA/name).read_text())


def mean(values):
    return float(np.mean(values))


def span(values,digits=1):
    return f'{min(values):.{digits}f}〜{max(values):.{digits}f}'


def image(stem,caption,width=r'\linewidth'):
    return r'\begin{center}\includegraphics[width='+width+']{../experiments/figures/coexistence/'+stem+r'.pdf}\captionof{figure}{'+caption+r'}\end{center}'+'\n'


def remove(source,tag):
    return re.sub(r'% BEGIN '+tag+r'\n.*?% END '+tag+r'\n?', '', source, flags=re.S)


def summary_intro():
    return r'''
% BEGIN RESEARCH GUIDE
\section{研究目的と結果の読み方}
本研究の目的はESP32の最高性能を測ることではなく、ロボコンの操縦指令と画像・点群が同じ無線を共有するとき、
どの設定や周辺通信が指令の到着、データ配送、更新途絶へ影響するかを判断する材料を得ることである。
スマートフォンの操縦アプリとロボットPCがルーターを介して通信し、ROS 2の指令、カメラ、LiDARのトピックを同じWi-Fiに載せる運用を想定する。
実際のスマートフォン・センサ・モータは用いず、アプリ要求・応答と模擬センサデータで無線経路を負荷する。

\subsection{設計上の判断と実験の対応}
\begin{center}\small
\begin{tabular}{p{.25\linewidth}p{.33\linewidth}p{.32\linewidth}}\toprule
設計上の判断 & 比較する操作 & 判断に使う指標\\\midrule
他チームとチャネルをどう分けるか & 同一Ch6、部分重複Ch7、分離Ch11で双方に通信 & 単独対照との差、指令期限、双方の実受信\\
広い帯域を使うか & 他チームの20/40 MHz幅 & 重なる帯域と通信品質。幅だけで順位を付けない\\
映像・点群をどの量とQoSで送るか & 要求量、生成周期、実ROS 2の履歴と信頼性 & 生成・受付・到着、指令とセンサの更新途絶\\
ESP-NOWやBLEを追加できるか & 停止対照、送信頻度、ESP-NOWのチャネル & Wi-Fi速度と外部リンクの応答・実受信を両方向に比較\\
接続表示だけで本番へ進めるか & 長時間、向き、遮蔽、距離、基準へ復帰 & 欠落、期限超過、最長更新途絶、対照の時間変動\\\bottomrule
\end{tabular}\end{center}

\subsection{速度・期限・スペクトルを別々に見る理由}
平均Mbpsは画像や点群を運べる量を示すが、操縦の指令が必要な時刻までに届くかを示さない。
応答が戻った指令だけのp99が小さくても、欠落が多ければ操縦は不安定になり得る。
そこで全予定指令の期限超過、応答欠落、最新sequenceが更新されない時間を併記する。
20 msは条件比較の目標であり、機体の安全な停止期限を証明した値ではない。
青緑SDR画像は受信した帯域の重なりを説明する補助で、画像の緑を通信成功、占有率、干渉原因の特定へ読み替えない。

\subsection{対照実験と構成を区別する理由}
別チームの負荷やESP-NOWをONにした値だけでは、その通信がなかった場合との差が分からない。
同じ経路・機器・配置を保ち、一つの要因だけを切り替える対照を置く。
今回追加した双方向評価は、Wi-Fi単独の対照がなかった先行ESP-NOW試験を補う。
さらにTCP接続を保った停止前・動作中・停止後を比較し、接続直後の変動と時間変動も確認する。
ただし独立無線機のRF共存、同一チップ内の共存制御、APを経由する経路は異なる。
室内の一構成の速度差を、ESP-NOW・BLE・ROS 2の普遍的な優劣として扱わない。

先に追加した双方向評価とその考察を示し、その後に流量・QoS・長時間・配置・他チーム比較を読む構成とした。
後半の受信設定、PCAP、LO掃引、5 GHz合成は、SDR画像で何が分かるかを確認する測定系の補足である。
% END RESEARCH GUIDE
'''


def full_results(esp,ble,brackets):
    out=r'''
% BEGIN MUTUAL RESULTS
\section{ESP-NOW・BLEとWi-Fiの双方向共存評価}\label{sec:mutual}
\subsection{目的と対照条件}
ESP-NOWの指令を追加して画像用Wi-Fiが遅くなるか、Wi-Fiを使いながらその指令が間に合うかを両方向で調べる。
先行試験ではWi-Fi側の実受信量も記録したが、全試行でESP-NOWが動いており、ESP-NOW停止時との差を算出できなかった。
今回、その停止対照を追加した。Wi-Fiは観測PCのCh6・20 MHz APから独立したESP32への1ホップTCPと100 Hz UDP要求・応答、
ESP-NOWは別のESP32とM5 ATOM LITEの64 byte要求・応答である。
送受信間75 cm、C5まで45 cm・95 cm、負荷用ESP32は同じ机上の位置を維持した。

ESP-NOW停止・100/200 HzとCh6/7/11、Wi-FiのTCPなし／20 Mbps生成要求を各20秒・3反復、反復内で無作為化した42試行を行った。
Wi-Fiの「TCPなし」でも100 Hz UDPとビーコンは残る。TCP要求20 Mbps・生成周期10 msは設定値であり、実受信Mbpsとは異なる。
負荷用ESP32の実際の20秒BENCH窓のTCP受信カウンタから速度を求め、準備時間とUARTダンプを除いた。
ESP-NOWの全指令イベントとWi-Fi UDPの記録をCRC検証し、実機カウンタと突き合わせた。
この新1ホップ系列を、先行のラップトップ→AP→ESP32という2ホップ系列と合算しない。

'''
    out+=image('mutual-topology','新しい双方向評価の論理構成。上段と下段は独立した無線機で、同じ室内のRFを共有する。距離や方向を表した図ではない。')
    out+=r'''
\subsection{ESP-NOWからWi-Fiへの速度と指令への影響}
Wi-Fi側の実受信速度低下率は、反復$r$ごとのESP-NOW停止対照$G_{0,r}$を使って
\[
d_r=100\left(1-\frac{G_{\mathrm{on},r}}{G_{0,r}}\right)
\]
とする。正の値は遅く、負の値は停止対照より速かったことを示す。下表の低下率は$d_r$の反復平均と範囲である。
負の結果も残し、全パケットを独立した環境反復として数えない。
\begin{center}\small\begin{tabular}{rrrrr}\toprule
ESP Hz & Ch & Wi-Fi平均 [Mbps] & 速度低下平均 [\%] & 反復範囲 [\%]\\\midrule
'''
    base=esp['bidirectional-espnow-wifiheavy-hz0-ch6']
    out+=f'0 & -- & {mean(base["wifi_goodput_mbps"]):.3f} & 0 & --'+r'\\'+'\n'
    for hz in (100,200):
        for ch in (6,7,11):
            row=esp[f'bidirectional-espnow-wifiheavy-hz{hz}-ch{ch}']
            out+=f'{hz} & {ch} & {mean(row["wifi_goodput_mbps"]):.3f} & {mean(row["matched_wifi_reduction_pct"]):.1f} & {span(row["matched_wifi_reduction_pct"])}'+r'\\'+'\n'
    out+=r'\bottomrule\end{tabular}\end{center}'+'\n'
    same=esp['bidirectional-espnow-wifiheavy-hz200-ch6']
    out+=(f'同一Ch6・200 HzではWi-Fi実受信平均が停止対照{mean(base["wifi_goodput_mbps"]):.3f}から'
          f'{mean(same["wifi_goodput_mbps"]):.3f} Mbpsへ増えた。一方、Wi-Fi UDPの20 ms超過は'
          f'{mean(base["wifi_deadline20_pct"]):.2f}から{mean(same["wifi_deadline20_pct"]):.2f}'+r'\%へ増えた。'+'\n')
    out+=r'''
\textbf{配送量の増加と指令品質の悪化が同時に観測された}ことがこの比較の重要な結果である。
「Wi-Fiが何\%遅くなるか」だけでなく、「その速度で操縦の応答が間に合うか」を独立に判断する必要がある。
'''
    out+=r'''
この表は同じ反復内での速度差を数値化したものだが、停止対照と動作条件の間には時間差がある。
TCP接続も条件ごとに新しくし、送信機・受信機・OSの状態、外来通信が変わり得る。
したがって差が全てRF干渉によるもの、あるいは負の値がESP-NOWによる速度改善の証拠とはしない。
Wi-Fiの指令遅延も併記する理由は、映像用の速度と操縦用の応答期限が同じ評価軸ではないためである。
'''
    out+=image('espnow-mutual-metrics','Wi-FiとESP-NOWの双方向評価。大きい点は反復平均、小さい点は各反復。速度低下は停止対照で正規化。')
    out+=r'\subsection{Wi-FiからESP-NOWへの指令品質の変化}'+'\n'
    out+=r'\begin{center}\small\begin{tabular}{rrrrrr}\toprule Hz & Ch & p99：TCPなし [ms] & TCPあり [ms] & 20 ms超過：なし [\%] & あり [\%]\\\midrule'+'\n'
    for hz in (100,200):
        for ch in (6,7,11):
            idle=esp[f'bidirectional-espnow-wifioff-hz{hz}-ch{ch}']['espnow'];load=esp[f'bidirectional-espnow-wifiheavy-hz{hz}-ch{ch}']['espnow']
            out+=f'{hz} & {ch} & {mean([r["rtt_p99_ms"] for r in idle]):.2f} & {mean([r["rtt_p99_ms"] for r in load]):.2f} & {mean([r["planned_deadline20_pct"] for r in idle]):.3f} & {mean([r["planned_deadline20_pct"] for r in load]):.3f}'+r'\\'+'\n'
    out+=r'\bottomrule\end{tabular}\end{center}'+'\n'
    adjacent_off=esp['bidirectional-espnow-wifioff-hz200-ch7']['espnow']
    adjacent_on=esp['bidirectional-espnow-wifiheavy-hz200-ch7']['espnow']
    out+=(f'200 Hz・隣接Ch7ではESP-NOWのp99平均が{mean([r["rtt_p99_ms"] for r in adjacent_off]):.2f}から'
          f'{mean([r["rtt_p99_ms"] for r in adjacent_on]):.2f} ms、20 ms超過が'
          f'{mean([r["planned_deadline20_pct"] for r in adjacent_off]):.3f}から'
          f'{mean([r["planned_deadline20_pct"] for r in adjacent_on]):.3f}'+r'\%へ増えた。'+'\n')
    out+=r'''
今回の200 Hzでは同一Ch6より隣接Ch7の尾部遅延・期限超過が大きかった。
先行のWi-Fi同士の比較では同一Ch6が最も遅く、順位は同じではない。
送信方式、経路、実通信量が変わると、単にチャネル番号の差だけから干渉の順位を決められないことを示す。
部分重複による受信妨害、キャリアセンス、ACKやキューの動作が説明候補だが、
フレームごとの衝突・送信待ちを測っていないため候補の寄与は分解できない。
'''
    out+=r'''
結果から、Wi-Fi側のMbpsとESP-NOW側の期限超過を独立に確認する必要が分かる。
ESP-NOWはAPを通らなくても同じ無線帯域を使い、指令と応答の両方に送信機会が必要である。
100から200 Hzへ増やすことは要求・応答の回数を増やす操作であり、制御が細かくなる利点と送信待ちが増える可能性の両方を持つ。
今回の64 byte要求・同サイズ応答を200 Hzで全て送ると、payload合計は$64\times8\times200\times2=204{,}800$ bit/sである。
1 Mbps設定ではpayloadの直列送信だけで理論上1秒あたり0.2048秒を要し、ヘッダ・プリアンブル・ACK・待ち時間は別に増える。
これは規定値からの下限計算であり、C5で実測した占有率ではない。
小さいメッセージだから帯域への負荷も小さい、と一律には判断できない理由がここにある。
反復が3回で室内固定配置に限られるため、Ch11で得た値を任意の会場の無干渉保証としない。
'''
    out+=image('espnow-mutual-blue-green','ESP-NOW停止と200 Hz・同一／隣接／分離チャネルのWi-Fi負荷中。実受信量と帯域の重なりを併記する。')
    out+=r'C5のLO2442 MHzに対する48 MHzアナログ帯域の名目範囲は2418--2466 MHzであり、Ch11の帯域上端の一部は外にかかる。Ch11の色が弱くても送信が少ない、または干渉しないとは判断しない。'+'\n'
    out+=r'\subsection{TCP接続を維持した停止前・動作・停止後の対照}'+'\n'
    out+=r'''
\paragraph{目的}
条件ごとの新しいTCP接続と100 Hz UDPの端末処理が速度へ混ざるため、別系列でTCP単独を測る。
Ch6/7/11・200 Hz・3反復の9ブロックで、同じTCP接続の停止前→ESP-NOW動作→停止後を各10秒測った。
UDP要求は生成せず、TCPの生成量と接続世代を維持した。停止前後の速度平均をそのブロックの基準とする。
カウンタの読出し区間は実時間で正規化し、9ブロックを27個の独立反復とは扱わない。
\begin{center}\small\begin{tabular}{rrrrrr}\toprule
Ch & 反復 & 停止前 [Mbps] & 動作 [Mbps] & 停止後 [Mbps] & 低下 [\%]\\\midrule
'''
    for ch in (6,7,11):
        for b in brackets[str(ch)]['blocks']:
            out+=f'{ch} & {b["repeat"]} & {b["before_mbps"]:.3f} & {b["on_mbps"]:.3f} & {b["after_mbps"]:.3f} & {b["reduction_pct"]:.1f}'+r'\\'+'\n'
    out+=r'\bottomrule\end{tabular}\end{center}'+'\n'
    same_blocks=brackets['6']['blocks']
    out+=(f'同一Ch6の速度低下率は3反復とも負で、平均{mean([r["reduction_pct"] for r in same_blocks]):.1f}'+
          r'\%、範囲'+span([r['reduction_pct'] for r in same_blocks])+r'\%だった。'+'\n')
    out+=r'''
これは停止前後の基準より動作窓の実受信が増えた結果であり、接続を作り直した試行だけに現れる現象ではなかった。
一方、隣接・分離の値と停止前後の差には反復変動があり、この増加をESP-NOW一般の速度改善効果へ広げない。
\paragraph{配送量が単純に低下しなかった理由の検討}
速度はRFの空中時間だけでなく、TCPの輻輳制御・受信窓・ACK、ソケットと受信タスクの処理によっても決まる。
一度にまとめて届く量が増えても、一つの指令の待ちは長くなり得る。
APの診断時点ではWi-Fi PHY送信65 Mbps・受信72.2 Mbpsを表示し、アプリの実受信Mbpsと大きく異なっていた。
同じ時間帯のTCP診断にはBBR、TCP再送、受信窓待ちが記録された。
これらは単一時点の補助診断であり、全試行のPHY速度やRF再送率を測定したものではない。
速度増加の機構を同定するには、同じ設定でのパケットごとのACK・TCP窓・無線送信の記録が必要である。
今回の結果は\textbf{無線方式の単純な取り分では説明し切れないアプリ配送の変化}を示し、
Wi-Fi PHYの最高速度や実ロボットPCへの映像速度の上限を測った結果とは区別する。
'''
    out+=r'''
\paragraph{結果の解釈}
停止後にも速度が変わる場合は、動作窓の変化をESP-NOWだけの影響として断定できない。
停止対照で挟む設計はその時間変動を可視化するためのもので、前後の平均が動作窓の真の反実仮想を完全に再現するとは限らない。
またTCP単独と指令同時の絶対Mbpsが違う場合は、RFだけでなく端末処理と待ち行列も運用評価に必要という示唆になる。
ロボコンでは「ESP-NOWを追加しても画像が出る」だけで合格にせず、指令周期と画像量を本番設定で動かし、双方の期限・更新・実受信を測る。
'''
    out+=image('tcp-bracket-metrics','同じTCP接続でESP-NOW停止前・200 Hz動作・停止後を比較。各線が1ブロック。')
    out+=r'\subsection{BLEとWi-Fiの両方向の配送量}'+'\n'
    out+=r'''
\paragraph{目的}
BLEが周波数ホッピングするためWi-Fiへ影響しない、という解釈を検証する。
停止・legacy広告・接続データを別条件とし、Wi-Fi TCPなし／負荷、各20秒・3反復の18試行で双方を測った。
BLEは独立した2台であり、同じESP32内の共存制御を測ったものではない。
Wi-Fiは固定20秒BENCH窓、BLE通知は前後カウンタの実読出し区間で配送量を求めるため、窓長が完全には一致しない。
\begin{center}\small\begin{tabular}{lrrrr}\toprule
BLE状態 & Wi-Fi平均 [Mbps] & 速度低下平均 [\%] & 反復範囲 [\%] & Wi-Fi20 ms超過 [\%]\\\midrule
'''
    for mode,label in [('off','停止'),('advert','広告'),('data','接続通知')]:
        r=ble[f'bidirectional-ble-wifiheavy-{mode}']
        out+=f'{label} & {mean(r["wifi_goodput_mbps"]):.3f} & {mean(r["matched_wifi_reduction_pct"]):.1f} & {span(r["matched_wifi_reduction_pct"])} & {mean(r["wifi_deadline20_pct"]):.3f}'+r'\\'+'\n'
    out+=r'\bottomrule\end{tabular}\end{center}'+'\n'
    idle=ble['bidirectional-ble-wifioff-data']['ble_goodput_mbps'];heavy=ble['bidirectional-ble-wifiheavy-data']['ble_goodput_mbps']
    out+=f'BLE接続通知の実受信平均はWi-FiのTCPなし{mean(idle):.3f} Mbps、TCP負荷あり{mean(heavy):.3f} Mbpsだった。反復範囲はそれぞれ{span(idle,3)}／{span(heavy,3)} Mbpsである。\n'
    baseline=ble['bidirectional-ble-wifiheavy-off'];notification=ble['bidirectional-ble-wifiheavy-data']
    out+=(f'通知の平均速度変化は{100*(mean(heavy)/mean(idle)-1):.1f}'+r'\%にとどまった一方、Wi-Fi指令の20 ms超過平均は'+
          f'{mean(baseline["wifi_deadline20_pct"]):.3f}から{mean(notification["wifi_deadline20_pct"]):.3f}'+r'\%へ増えた。'+'\n')
    out+=r'BLE通知が届いていることだけでWi-Fi操縦側の品質まで保たれると判断できない、という非対称な結果である。'+'\n'
    out+=(f'BLE通知中のWi-Fi速度低下率は反復平均{mean(notification["matched_wifi_reduction_pct"]):.1f}'+r'\%だったが、範囲は'+
          span(notification['matched_wifi_reduction_pct'])+r'\%で、一部の反復では停止対照より速かった。'+
          r'「BLEで常にこの割合だけ速度が低下する」という設計値には使えない。'+'\n')
    out+=r'''
\paragraph{結果から分かることと考察}
BLE側の通知が届くこととWi-Fi側の速度・指令が保たれることは別々に確認する必要がある。
legacy広告は2402・2426・2480 MHz、接続データは37チャネルから接続イベントごとに選ぶ方式である。
Wi-Fiの帯域内へBLEがホップし、同時に送信すれば、短い狭帯域信号でも受信失敗や再送が起こり得る。
名目20 MHzのCh6範囲2427--2447 MHz内には、中心2428--2446 MHzの10データチャネルがある。
37チャネルを全て同じ頻度で使う仮定なら約27\%の選択先がこの範囲へ入るが、これは周波数配置の計算であって衝突率ではない。
実際のAFH集合、Wi-FiとBLEの送信時間、受信電力が不明なため、今回の衝突確率を27\%とは置けない\cite{blePrimer,bleAFH}。
ホッピングは通信をWi-Fiから独立させる保証ではない。ただし今回は実ホッピング列、AFHチャネル集合、フレームごとの再送・衝突を取得していない。
実受信量の差を全てRF衝突へ割り当てたり、AFHが特定帯域を避けたと断定したりしない。
BLE通知の生成周期・接続間隔、Wi-Fiの実通信量、距離・向きによって共存の結果は変わり得る。
少数反復の平均差をBLE一般の固定した速度低下率として用いない。
'''
    out+=image('ble-mutual-metrics','BLE停止対照を含む双方向評価。Wi-Fiの速度低下、指令期限とBLE実受信を別々に示す。')
    out+=image('ble-mutual-blue-green','Wi-Fi負荷中のBLE停止・広告・接続データ。共通尺度の広帯域表示。')
    out+=image('ble-mutual-narrow-blue-green','2450--2470 MHzの拡大。この表示範囲にlegacy広告の3周波数は含まれない。前図とは色尺度が異なる。')
    out+=r'''
\subsection{競技で使う判断へのつなぎ方}
まず単独の映像・指令が目標を満たすかを確認し、外部無線をONにした差を求める。
同一・隣接・分離チャネルの比較は他チームとの配置を相談する材料になるが、分離後も自チーム内の待ち行列や端末処理は残る。
指令が遅れるなら、送信頻度を上げる操作だけでなく、映像の生成量、最新指令の扱い、期限を過ぎたデータの扱いを検討する。
今回の独立したESP-NOWは固定チャネルであり、同じESP32でWi-Fi APへ接続する併用ではAPのチャネルに合わせる制約がある。
BLEは接続後ホッピングするため、ESP-NOWのように双方を別の固定チャネルへ置くだけの対策とは異なる。
無線方式の名前ではなく、本番の配置・周期・データ量で双方の到着と更新を測ることが最終的な判断になる。
% END MUTUAL RESULTS
'''
    out=re.sub(r'\\paragraph\{([^}]+)\}',lambda m:r'\par\smallskip\noindent\textbf{'+m[1]+r'}\quad',out)
    out=out.replace(r'\begin{tabular}',r'\begin{adjustbox}{max width=\linewidth}\begin{tabular}')
    out=out.replace(r'\end{tabular}',r'\end{tabular}\end{adjustbox}')
    return out


def full(esp,ble,brackets):
    path=ROOT/'reports/full.tex';source=path.read_text()
    for tag in ('RESEARCH GUIDE','MUTUAL RESULTS'):
        source=remove(source,tag)
    source=source.replace('% BEGIN OPERATIONAL STUDY',summary_intro()+full_results(esp,ble,brackets)+'\n% BEGIN OPERATIONAL STUDY',1)
    source=source.replace('構成の異なる342通信試行と115受信観測系列を区別して統合し、',
        '先行342通信試行と115受信観測系列に、双方向共存60試行と同一TCP接続の9切替ブロックを加え、構成を区別して統合し、')
    source=source.replace('逆方向については、共存中のWi-Fi実受信量も保存したが、ESP-NOWを停止した同一条件のWi-Fi単独基準は測っていない。\nしたがって「ESP-NOWがWi-Fiを何\\%遅くした」「Wi-Fiへ影響しない」は今回の記録から定量的に断定できない。\nこれはWi-Fi負荷の中でESP-NOW指令が間に合うかを中心に評価した実験である。',
        'この先行30秒系列はWi-Fi負荷中のESP-NOW指令を中心に測り、Wi-Fi単独の停止対照がなかった。\n逆方向の評価は新たに追加した\\ref{sec:mutual}節で行う。経路と対照条件が異なるため、先行系列へ新しい停止対照を流用しない。')
    purposes={
        '流量制限の比較':'映像・点群を生成し過ぎたとき指令の到着がどう変わるかを調べる。自チームの要求量だけを変え、未送信データの蓄積と実受信量を区別する。',
        '生成周期の比較':'同じ平均データ量でも一度にまとめると指令が待たされるかを調べる。生成量を保ち100 msと10 msの周期を比較し、平滑化だけで改善できるかを判断する。',
        '実ROS 2のQoSと指令応答':'模擬TCPだけの知見を実ROS 2へ適用できるかを確認する。指令QoSを固定してセンサの信頼性と履歴だけを変え、大容量トピックと指令の共存を評価する。',
        '省電力設定への介入と端末内時間':'無線の省電力とロボット内の処理時間が遅延へ寄与するかを切り分ける。実際のON/OFFと読出しを確認し、別PCの時計差を片道遅延にしない。',
        'ESP-NOWの指令周期と長時間更新の安定性':'短い試行で見逃す更新途絶と、指令頻度を上げた時の尾部遅延を調べる。20から200 Hzの周期と10分間の全イベントを比較する。',
        'ESP32間通信の配置・向き・遮蔽比較':'机上で接続できても姿勢・遮蔽・距離で指令品質が変わるかを調べる。基準へ戻した後も測り、時間変動を配置の効果と取り違えない。',
        '同一・隣接・分離チャネルの比較結果':'他チームも大容量通信するときチャネル番号を変えることに意味があるかを調べる。自チーム内の通信を保ち、他チームの帯域と負荷を切り替える。',
        'チャネル幅と操縦通信性能':'広いチャネルが同時に置けるチーム数と操縦品質へどう影響するかを調べる。20/40 MHzで重なる周波数と実際の期限超過を比較する。',
        '通常Wi-Fiの周期負荷による意図的なストレス試験':'近隣通信が始まったり止まったりする時に指令遅延が変わるかを調べる。通常のWi-Fi TCP負荷を時間的にON/OFFし、規格外の妨害波を使用しない。',
        '独立したBluetooth LEリンクとの比較':'同じ2.4 GHz帯の異なる方式が共存した時に双方の配送が変わるかを調べる。広告と接続通知を分け、ホッピングを無干渉の保証として扱わない。',
        'ESP-NOWの指令と独立したWi-Fi大容量通信':'指令をAPを通らないリンクに分ける候補を評価する。Wi-Fi負荷によるESP-NOW応答の変化を固定チャネル間で比較する先行系列である。',
    }
    for title,paragraph in purposes.items():
        marker=r'\section{'+title+'}'
        addition='\n'+r'\par\smallskip\noindent\textbf{実験の目的}\quad '+paragraph+'\n'
        # The operational writer recreates these sections each time. Avoid
        # duplicating purpose paragraphs when this last writer is run alone.
        source=source.replace(marker+'\n'+r'\paragraph{実験の目的}'+paragraph+'\n',marker)
        source=source.replace(marker+addition,marker)
        source=source.replace(marker,marker+addition,1)
    path.write_text(source)


def twitter(esp,ble,brackets):
    base=esp['bidirectional-espnow-wifiheavy-hz0-ch6']
    same=esp['bidirectional-espnow-wifiheavy-hz200-ch6']
    path=ROOT/'reports/twitter.tex';preamble=path.read_text().split(r'\begin{document}',1)[0]
    preamble=re.sub(r'\n{3,}','\n\n',preamble)
    cols=r'\begin{multicols}{2}\fontsize{10}{14}\selectfont\raggedcolumns'+'\n'
    body=r'''\begin{document}\onecolumn
\begin{center}{\LARGE\bfseries\sffamily ロボコンの無線通信と帯域共有の実測評価\par}
\vspace{1mm}{\normalsize 他チーム通信・ROS 2・BLE・ESP-NOWの相互影響\par}
\vspace{.5mm}{\normalsize \ReportAuthor\par}\end{center}
\noindent\fbox{\parbox{\dimexpr\textwidth-2\fboxsep-2\fboxrule}{\small
\textbf{要旨}\quad 操縦と画像・点群が同じWi-Fiを使い、他チームやBLE・ESP-NOWも動く状況を比較した。
無線の停止対照と双方の通信記録を使い、帯域の重なり、実受信速度、指令期限を分けて評価する。
チャネル分離だけで端末内の遅延はなくならず、方式名や平均Mbpsだけでは操縦品質を判断できない。}}\vspace{2mm}
'''+cols+r'''
\section{目的と評価方法}
スマートフォンの操縦指令、ロボットのカメラ映像・LiDAR点群が、ルーターと同じWi-Fi／ROS 2を共有する運用を想定する。
\textbf{目的はESP32の最高性能ではなく、隣のチームや追加無線が動く中で指令とデータを両立させる判断材料を得ること}である。
観測PC（Intel BE200）のAP（アクセスポイント）、ラップトップ1（Intel AX210・有線共有）、ラップトップ2（MT7921E）、ESP32 3台とC5を使用した。
実スマートフォン・カメラ・モータは使用せず、画像・点群の形と大きさを持つ模擬データを送った。

Wi-Fiの平均Mbpsは運べる量、RTT p99は返った応答の99\%が収まる往復時間、20 ms期限超過は\textbf{欠落も含む}割合である。
指令の更新途絶も見る。20 msは比較目標で、機体の安全な停止期限ではない。
基本3反復。経路・端末の違う系列を合算して方式の順位を付けない。

\section{他チーム通信とチャネル配置}
\textbf{目的：}双方に大容量通信を流し、他チームとのチャネル分離が有効かを調べる。
自チームCh6・20 MHzを固定し、他チームを待機／TCP負荷とした30秒・3反復。
\begin{center}\captionof{table}{自チーム大容量通信中。値は他チーム待機／負荷。}
\small\begin{tabular}{@{}crr@{}}\toprule 他Ch & RTT p99 [ms] & 20 ms超過 [\%]\\\midrule
6 & 125.8 / 148.4 & 55.0 / 67.7\\
7 & 123.8 / 132.3 & 53.8 / 63.0\\
11 & 126.5 / 127.4 & 54.4 / 57.2\\\bottomrule\end{tabular}\end{center}
\textbf{分かること：}他負荷の追加によるp99増分は同一約23 ms、隣接約9 ms、分離約1 msだった。
Ch6と7は中心が5 MHz違うだけで20 MHz帯域は重なる。
\textbf{番号が違っても別の帯域とは限らない}。送信待ちや再送は候補だが、直接測定して原因を特定した結果ではない\cite{rf}。
他チームの実受信も0.4--4.7 Mbpsと異なり、等しい空中時間の比較ではない。

\subsection{チャネル幅と利用できる帯域}
\textbf{目的：}他チームの幅20→40 MHzで重なりと操縦品質が変わるかを調べる。
Ch1の20 MHzは名目2402--2422 MHz、Ch1＋副Ch5の40 MHzは2402--2442 MHzで自Ch6へ重なる。
p99は128.6→127.5 ms、超過は55.0→56.8\%だった。
広い幅は同時配置の余裕を減らすが、転送が速ければ送信時間を短くできる。
\textbf{広いほど必ず悪いという結果ではなく、指令期限と実受信を併せて判断する}。

\section{自チーム内の流量とROS 2}
\textbf{目的：}干渉を避けるだけでなく、画像・点群の量や送り方で指令を改善できるかを調べる。
同一Ch6負荷中、TCP要求0→1 Mbpsで20 ms超過54.08→72.61\%。2 Mbps要求でも実受信1.105 Mbpsで未送信byteが蓄積した。
同じ1 Mbpsの生成周期100→10 msではCh6超過63.47→59.42\%、Ch7は53.88→53.88\%。小分け生成は常に改善せず、TCPやOSもデータをまとめ直す。

実ROS 2（Humble／Jazzy・CycloneDDS）は指令QoSを固定し、センサのreliable／best effortと深さ1／10を比較した。
指令のみの20 ms超過約45\%に対し、模擬Image・PointCloud2追加時は約70--80\%。実受信約47--55 Mbpsでも指令が間に合うとは限らない。
深さ1はDDSの履歴で、無線待ち行列や指令優先度を設定する値ではない\cite{ros}。
省電力OFFでも指令のみp99約103--109 msが残り、全遅延を他チームや省電力だけへ帰属できない。
\end{multicols}
\begin{center}\includegraphics[width=.96\textwidth]{../experiments/figures/two-team/two-team-blue-green-compact.pdf}\captionof{figure}{他チームも通信中。同一・隣接・分離チャネル、反復1。青緑は未校正dBFS、白線は名目帯域。}\end{center}
\clearpage
'''
    body+=image('espnow-mutual-blue-green','新しい1ホップ系列。Wi-Fi負荷中のESP-NOW停止と200 Hz・Ch6／7／11、反復1。',r'.96\textwidth')+cols+r'''
\section{ESP-NOWとWi-Fiの相互影響}
\subsection{固定チャネルと追加測定の目的}
ESP-NOWはWi-Fiの無線部からaction frameを直接送り、\textbf{標準でBLEのような自動ホッピングをしない}。
送受信は同じ固定チャネルを使う。channel=0は現在のチャネルという意味で、自動探索ではない\cite{espnow}。
別の無線機ならWi-Fiと分離できるが、同じESP32でAP接続を併用する場合はAPのチャネルに合わせる制約がある\cite{espnowFAQ}。

\textbf{目的：}Wi-FiがESP-NOWへ与える影響と、その逆の速度・指令への影響を測る。
前の試験は全条件でESP-NOWが動いていたため、Wi-Fi単独との差を求められなかった。
今回は停止対照を加え、100/200 Hz・Ch6/7/11とWi-Fi TCPなし／要求20 Mbpsを各20秒・3反復、計42試行とした。
Wi-FiはPC AP→別のESP32という1ホップに統一し、UDP100 Hz指令も同時に送る。
先行の2ホップ系列の絶対Mbpsとは混ぜない。

\subsection{Wi-FiからESP-NOWへの影響}
\begin{center}\captionof{table}{新系列のESP-NOW 200 Hz。TCPなし／負荷、反復平均。}
\small\begin{tabular}{@{}crr@{}}\toprule Ch & ESP p99 [ms] & ESP20 ms超過 [\%]\\\midrule
'''
    for ch in (6,7,11):
        off=esp[f'bidirectional-espnow-wifioff-hz200-ch{ch}']['espnow'];on=esp[f'bidirectional-espnow-wifiheavy-hz200-ch{ch}']['espnow']
        body+=f'{ch} & {mean([r["rtt_p99_ms"] for r in off]):.2f} / {mean([r["rtt_p99_ms"] for r in on]):.2f} & {mean([r["planned_deadline20_pct"] for r in off]):.2f} / {mean([r["planned_deadline20_pct"] for r in on]):.2f}'+r'\\'+'\n'
    body+=r'''\bottomrule\end{tabular}\end{center}
APを経由しなくても帯域と送信機会は共有する。小さな指令も、要求・応答・ヘッダ・ACKを繰り返すのでpayloadのMbpsだけでは負荷を判断できない。
64 byteを200 Hzで往復するとpayloadだけで0.2048 Mbpsとなり、今回の1 Mbps PHYではその直列送信に理論上1秒の20.48\%を要する。ヘッダ等は別で、実測占有率ではない。
100/200 Hzの比較は詳細版へ併記し、頻度を上げる利点と期限超過を両方評価した。

\subsection{ESP-NOWからWi-Fiへの速度変化}
接続の初期変動を切り分けるため、\textbf{同じTCP接続の停止前→200 Hz動作→停止後}を各10秒、各Ch3反復追加した。
この9ブロックではUDP指令を生成しない。速度低下率は$100(1-G_{\rm on}/G_0)$、$G_0$は直前・直後の停止速度平均。
正は遅く、負は速かった値である。
\begin{center}\captionof{table}{TCP単独の切替対照。9ブロック・27窓。}
\small\begin{tabular}{@{}crr@{}}\toprule ESP Ch & 速度低下平均 [\%] & 反復範囲 [\%]\\\midrule
'''
    for ch in (6,7,11):
        values=[b['reduction_pct'] for b in brackets[str(ch)]['blocks']]
        body+=f'{ch} & {mean(values):.1f} & {span(values)}'+r'\\'+'\n'
    body+=r'\bottomrule\end{tabular}\end{center}'+'\n'
    body+='同一Ch6は3反復とも速度が増えた。20秒行列の同一Ch6・200 Hzも、Wi-Fi実受信平均は'
    body+=f'{mean(base["wifi_goodput_mbps"]):.3f}→{mean(same["wifi_goodput_mbps"]):.3f} Mbps、指令の20 ms超過は'
    body+=f'{mean(base["wifi_deadline20_pct"]):.2f}→{mean(same["wifi_deadline20_pct"]):.2f}'+r'\%へ増えた。'+'\n'
    body+=r'''
\textbf{配送量が増えても、操縦の応答が間に合うとは限らない}。
TCPのACK・受信窓・端末処理も速度を左右し、RFの取り分だけで変化を説明できない。
停止後にも速度が変わる場合は、動作窓の差を全てESP-NOWへ帰属できない。
20秒行列のWi-Fi速度・指令期限とこの切替対照は別に評価した。
今回の比は室内の観測値で、方式固有の固定した低下率ではない。

\section{指令周期と長時間の更新}
\textbf{目的：}短い試行で見逃す途絶と、高頻度化の限界を調べる。
先行600秒系列は20/50/100/200 Hz、Wi-Fi待機／負荷、計19試行。
960,000指令、959,997 unique応答。負荷中100 Hzのp99は9.26 ms、200 Hzは14.26 msだった。
指令を増やせば必ず良くなる結果ではない。
20 Hzでは通常の更新自体が50 ms間隔であり、1指令の20 ms期限と継続更新の周期は別に設計する。
短時間の新系列と実装・時間の異なる10分系列を合算しない。
\end{multicols}\clearpage
'''
    body+=image('ble-mutual-narrow-blue-green','新系列のBLE停止・広告・接続データ、Wi-Fi負荷中・反復1。2450--2470 MHz拡大は広告3周波数とWi-Fi Ch6の名目帯域の外。',r'.86\textwidth')+cols+r'''
\section{BLEとWi-Fiの相互影響}
\subsection{周波数の使い方と実験の目的}
\textbf{目的：}ホッピングするBLEを追加したとき、双方の配送とWi-Fi指令が保たれるかを調べる。
legacy広告は2402・2426・2480 MHzの3周波数、接続データは2 MHz間隔の37チャネルを使う。
接続イベントごとに両端が同じ周波数を選び、時間とともに狭い信号の送信先を変える\cite{ble}。
広帯域を一度に送る方式ではない。

Wi-Fi Ch6の名目2427--2447 MHz内にもBLEのデータチャネルがあり、同時送信すれば重なり得る。
\textbf{ホッピングは無干渉の保証ではない}。AFHは使用チャネル集合を更新する仕組みだが、今回その集合・再送・衝突数は取得していない。
40 MHz化で重なり得る周波数は増えるが、速く送れば空中時間も変わるため幅だけで劣化量を決められない。BLEの20/40 MHz比較は未実施である。

\subsection{停止対照と双方の実受信}
独立したESP32 2台で停止／広告／BLE 1M通知、Wi-Fi TCPなし／要求20 Mbps、各20秒・3反復の18試行を行った。
\begin{center}\captionof{table}{新1ホップ系列・Wi-Fi TCP負荷中。3反復平均。}
\small\begin{tabular}{@{}lrr@{}}\toprule BLE & Wi-Fi [Mbps] & 速度低下 [\%]\\\midrule
'''
    for mode,label in [('off','停止'),('advert','広告'),('data','接続通知')]:
        r=ble[f'bidirectional-ble-wifiheavy-{mode}']
        body+=f'{label} & {mean(r["wifi_goodput_mbps"]):.3f} & {mean(r["matched_wifi_reduction_pct"]):.1f}'+r'\\'+'\n'
    idle=ble['bidirectional-ble-wifioff-data']['ble_goodput_mbps'];heavy=ble['bidirectional-ble-wifiheavy-data']['ble_goodput_mbps']
    body+=r'\bottomrule\end{tabular}\end{center}'+'\n'
    body+=f'BLE通知の実受信平均はWi-Fi TCPなし{mean(idle):.3f}→負荷{mean(heavy):.3f} Mbps。\n'
    off=ble['bidirectional-ble-wifiheavy-off'];on=ble['bidirectional-ble-wifiheavy-data']
    body+=f'一方、Wi-Fi指令の20 ms超過はBLE停止{mean(off["wifi_deadline20_pct"]):.3f}→通知{mean(on["wifi_deadline20_pct"]):.3f}'+r'\%へ増えた。'+'\n'
    body+=r'BLEの配送が保たれてもWi-Fi操縦の期限が保たれるとは限らない。速度差の反復には増加もあり、固定した低下率とはしない。'+'\n'
    body+=r'''Wi-Fi速度低下は反復ごとのBLE停止対照に対する比で、負の値も残した。
BLEはカウンタの実読出し区間、Wi-Fiは固定20秒窓で正規化している。
\textbf{Wi-FiとBLEの両方を見る必要がある}が、3反復の差を全て衝突やAFHの効果とは断定できない。
Bluetooth音声と同じチップ内の共存制御は別の試験が必要である。

\section{SDRと配置比較の解釈}
C5は80 MS/s・16,380 I/Q・48 MHzアナログ帯域・手動ゲイン設定20・FFT1024。
各行約205 $\mu$s、名目RF観測時間比約0.4\%で、縦軸は\textbf{間欠取得順}である。
青緑の未校正dBFSを絶対dBm、占有率、通信成功率へ変換しない。
細線は狭帯域成分の手掛かりだが、全てをBLEと同定したり連続ホッピングを復元したりはできない。
Ch11の一部はC5のアナログ帯域端へかかり、弱い色を無干渉の証拠としない。

先行配置比較はESP32間75 cm、C5まで45 cm・95 cmから、90°回転、手の遮蔽、150 cm、基準復帰を各10秒・3反復した。
全30,000指令で欠落はなかったが、元へ戻した後もp99が低下したため、回転・遮蔽による改善とは断定できない。
近距離・固定配置の結果を、競技中の移動や到達距離の保証へ広げない。

\section{ロボコン運用への考察}
まず\textbf{単独の基準}で操縦と映像が目標を満たすかを調べ、隣チームやBLE・ESP-NOWをONにした差を測る。
チャネルを分離しても自チーム内の待ち行列・端末処理は残る。今回もQoS深さ1や省電力OFFだけでは遅延を解消できなかった。

映像・点群は生成量と実受信を比べ、未送信の蓄積を抑える。指令は平均速度より期限超過、欠落、最新情報の更新途絶を見る。
ESP-NOWの頻度は高ければ良いとは決めず、別リンクでも双方を本番のデータ量で動かす。
最後に停止対照へ戻し、時間変動と設定の効果を区別する。
この測定は構成を選ぶ材料であり、機体の安全停止は実機で別に確認する。

{\footnotesize\begin{thebibliography}{9}\footnotesize
\bibitem{rf} \href{https://www.cisco.com/c/en/us/td/docs/wireless/controller/9800/technical-reference/wireless-rf-reference-guide.html}{Cisco, Wireless RF Reference Guide.}
\bibitem{ros} \href{https://docs.ros.org/en/jazzy/Concepts/Intermediate/About-Quality-of-Service-Settings.html}{ROS 2 Jazzy, Quality of Service settings.}
\bibitem{espnow} \href{https://docs.espressif.com/projects/esp-idf/en/v6.0/esp32/api-reference/network/esp_now.html}{Espressif, ESP-NOW Programming Guide.}
\bibitem{ble} \href{https://www.bluetooth.com/bluetooth-le-primer/}{Bluetooth SIG, Bluetooth LE Primer.}
\bibitem{espnowFAQ} \href{https://docs.espressif.com/projects/esp-faq/en/latest/application-solution/esp-now.html}{Espressif, ESP-NOW FAQ.}
\end{thebibliography}}
\end{multicols}\end{document}
'''
    path.write_text(preamble+body)


def overview(esp,ble,brackets):
    base=esp['bidirectional-espnow-wifiheavy-hz0-ch6'];same=esp['bidirectional-espnow-wifiheavy-hz200-ch6']
    adj0=esp['bidirectional-espnow-wifioff-hz200-ch7']['espnow'];adj1=esp['bidirectional-espnow-wifiheavy-hz200-ch7']['espnow']
    ble0=ble['bidirectional-ble-wifiheavy-off'];ble1=ble['bidirectional-ble-wifiheavy-data']
    idle=ble['bidirectional-ble-wifioff-data']['ble_goodput_mbps'];heavy=ble1['ble_goodput_mbps']
    text=f'''# 双方向共存評価の結果と考察

## 実験の目的

ロボコンの画像・点群用Wi-FiへESP-NOWやBLEを追加した時、双方の配送と指令期限が保たれるかを調べた。前のESP-NOW系列に不足していた、ESP-NOWを止めたWi-Fi単独対照を追加した。1ホップのPC AP→ESP32を使い、先行の2ホップや実ROS 2系列とは別に集計する。配置は送受信75 cm、C5まで45 cm・95 cm、机上の位置を維持した。

## 測定した条件

- ESP-NOW停止・100/200 Hz、Ch6/7/11、Wi-Fi TCPなし／20 Mbps生成要求、各20秒・3反復：42試行。
- BLE停止・legacy広告・接続通知、Wi-Fi TCPなし／20 Mbps生成要求、各20秒・3反復：18試行。
- 同じTCP接続を保つESP-NOW停止前／200 Hz動作／停止後、Ch6/7/11、各窓10秒・3反復：9ブロック・27窓。UDP指令なしの別系列。

Wi-Fi要求20 Mbpsは実受信量ではない。両方向のアプリ記録、受信カウンタ、設定、I/QのCRCを確認した。各反復の停止対照を基準に速度低下率を算出し、負の値も残した。

## 結果から分かること

同一Ch6・ESP-NOW 200 HzではWi-Fi実受信平均が{mean(base['wifi_goodput_mbps']):.3f}から{mean(same['wifi_goodput_mbps']):.3f} Mbpsへ増えた。一方、Wi-Fi指令の20 ms超過は{mean(base['wifi_deadline20_pct']):.2f}から{mean(same['wifi_deadline20_pct']):.2f}%へ増えた。配送量が増えても操縦の応答が間に合うとは限らない。

200 Hz・隣接Ch7ではESP-NOWのp99平均が{mean([r['rtt_p99_ms'] for r in adj0]):.2f}から{mean([r['rtt_p99_ms'] for r in adj1]):.2f} ms、20 ms超過が{mean([r['planned_deadline20_pct'] for r in adj0]):.3f}から{mean([r['planned_deadline20_pct'] for r in adj1]):.3f}%へ増えた。先行のWi-Fi同士の順位とは異なり、チャネル番号の差だけで干渉の順位を決められない。

TCP単独の同じ接続でも同一Ch6の200 Hz動作窓は停止前後の平均より実受信が増え、低下率平均は{brackets['6']['mean_reduction_pct']:.1f}%だった。停止前後にも変動があり、RF、TCPのACK・窓、キュー・端末処理の寄与は分解していない。速度が増えたことをESP-NOW一般の改善効果へ広げない。

BLE通知の実受信平均はWi-Fi TCPなし{mean(idle):.3f}→負荷{mean(heavy):.3f} Mbps。一方、Wi-Fi指令の20 ms超過はBLE停止{mean(ble0['wifi_deadline20_pct']):.3f}→通知{mean(ble1['wifi_deadline20_pct']):.3f}%へ増えた。BLE側の配送が保たれることとWi-Fi側の指令期限は別々に判断する。

BLE通知中のWi-Fi速度低下率は反復平均{mean(ble1['matched_wifi_reduction_pct']):.1f}%、範囲{span(ble1['matched_wifi_reduction_pct'])}%だった。3反復の中には停止対照より速い試行もあり、普遍的な一定の速度低下率として扱わない。

## 仕組みと考察

ESP-NOWはこの実験では固定Wi-Fiチャネルで動作する。標準でBLEのように自動ホッピングせず、APを経由しないことも空中時間の独立を意味しない。64 byteの要求・応答を200 Hzで送ればpayload合計0.2048 Mbpsとなり、1 Mbps PHYではpayloadだけで理論上1秒の20.48%の直列送信時間を要する。ヘッダ等は別で、実測占有率ではない。

BLEのlegacy広告は3周波数、接続データは37チャネルから接続イベントごとに選ぶ方式である。Wi-Fiと同じ周波数・時刻なら重なり得る。ホッピングとAFHは無干渉の保証ではなく、今回AFHの使用集合や実衝突数は取得していない。

今回のAPの診断ではPHYの表示速度とアプリ実受信量が大きく異なり、TCPの再送と受信窓待ちも見られた。補助診断は単一時点の記録で、全試行のRF再送率ではない。競技用PCの最高映像速度をESP32のアプリ実受信値から推定しない。単独対照、本番の映像・指令量、隣チームの通信、停止対照への復帰を組み合わせて評価する。

[方法と適用範囲](coexistence-method.md) · [詳細版](../reports/full.pdf) · [X用3ページ版](../reports/twitter.pdf)
'''
    (ROOT/'docs/coexistence-results.md').write_text(text)
    path=ROOT/'README.md';source=remove(path.read_text(),'MUTUAL OVERVIEW')
    source=re.sub(r'(?:先行)*計342通信試行と、','先行計342通信試行と、',source)
    addition=f'''<!-- MUTUAL OVERVIEW BEGIN -->
## 双方向共存評価の追加

ESP-NOW42試行とBLE18試行（各20秒・3反復）、同じTCP接続の停止前／動作／停止後9ブロックを追加しました。先行の2ホップ系列と異なる1ホップ系列です。

- 同一Ch6・200 HzではWi-Fi実受信平均が{mean(base['wifi_goodput_mbps']):.3f}→{mean(same['wifi_goodput_mbps']):.3f} Mbpsへ増えましたが、Wi-Fi指令の20 ms超過も{mean(base['wifi_deadline20_pct']):.2f}→{mean(same['wifi_deadline20_pct']):.2f}%へ増えました。Mbpsと操縦品質は別に判断します。
- BLE通知はWi-Fi TCPなし／負荷で{mean(idle):.3f}／{mean(heavy):.3f} Mbpsでした。一方、Wi-Fi指令の20 ms超過はBLE停止／通知で{mean(ble0['wifi_deadline20_pct']):.3f}／{mean(ble1['wifi_deadline20_pct']):.3f}%でした。
- 速度低下率は停止対照と反復ごとに比較し、負の値と範囲も表示します。TCP・端末処理・外来通信をRFの影響だけへ帰属しません。

[追加結果と考察](docs/coexistence-results.md) · [双方向評価の方法](docs/coexistence-method.md)
<!-- MUTUAL OVERVIEW END -->

'''
    source=re.sub(r'<!-- MUTUAL OVERVIEW BEGIN -->.*?<!-- MUTUAL OVERVIEW END -->\n*','',source,flags=re.S)
    source=source.replace('## ディレクトリ',addition+'## ディレクトリ',1)
    path.write_text(source)


def main():
    esp=read('espnow-summary.json');ble=read('ble-summary.json');brackets=read('tcp-bracket-summary.json')
    full(esp,ble,brackets)
    twitter(esp,ble,brackets)
    overview(esp,ble,brackets)
    from clarify_report_conclusions import revise_reports
    revise_reports()


if __name__=='__main__':
    main()
