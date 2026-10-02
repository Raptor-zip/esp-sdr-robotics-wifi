#!/usr/bin/env python3
"""Append measured ESP-NOW comparisons while preserving the two report sources."""
import json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];D=R/'experiments/data/espnow'
if not (D/'summary.json').exists():raise SystemExit(0)
S=json.loads((D/'summary.json').read_text());M=json.loads((R/'experiments/data/manifest.json').read_text());E=M['espnow'];T=M['two_team']
if len(S)!=6 or any(v['runs']!=3 for v in S.values()):raise SystemExit('ESP-NOW needs all 18 measured trials')
def key(level,ch):return f'espnow-{level}-ch{ch}'
def value(k,field='pooled_p99_ms'):return f'{S[k][field]:.1f}'
rows=[];fullrows=[]
for level in ('off','heavy'):
 for ch in (6,7,11):
  k=key(level,ch);s=S[k];label=('待機' if level=='off' else '負荷')+f' / Ch{ch}';basic=label+' & '+value(k)+' & '+value(k,'deadline20_pct')+f' & {s["loss_pct"]:.2f}';rows.append(basic+r'\\');fullrows.append(basic+f' & {min(s["wifi_mbps"]):.2f}--{max(s["wifi_mbps"]):.2f}'+r'\\')
measurements=[json.loads(p.read_text()) for p in D.glob('espnow-*.json')]
def counter(role,field):return sum(m['radio'][role]['after'][field]-m['radio'][role]['before'][field] for m in measurements)
telemetry=f'全54,000送信要求に対し、送信側API受付エラー{counter("sender","tx_api_errors")}、送信側MAC失敗{counter("sender","tx_fail")}、echo側MAC失敗{counter("echo","tx_fail")}を記録した。echoキューの取りこぼしは{counter("echo","queue_drops")}だった。これらはパケットごとの因果対応を持たず、合計をそのままアプリ応答欠落へ割り当てない。'
variation=S[key('heavy',6)]['run_p99_ms']
variation_text=f'{min(variation):.1f}--{max(variation):.1f}'
alltrials=T['trials']+E['trials'];allsent=T['control_sent']+E['control_sent'];allgot=T['control_received']+E['control_received'];allshots=T['iq_snapshots_original']+E['iq_snapshots_original']
p=R/'reports/full.tex';t=p.read_text();begin='% BEGIN ESPNOW STUDY';end='% END ESPNOW STUDY'
if begin in t:t=t[:t.index(begin)]+t[t.index(end)+len(end):]
section=begin+r'''
\section{ESP-NOWの指令と独立したWi-Fi大容量通信}
ESP32-1からESP32-2へ64 byte・100 Hzの未暗号化unicast指令を送り、受信タスクが同じ内容をアプリ応答として返す。APを通らない経路である。Wi-Fi側は観測PC（Intel BE200）Ch6・20 MHz APに固定し、ラップトップ2からESP32-3へ大容量TCP模擬データを流す。ESP-NOWをCh6・Ch7・Ch11へ動かし、Wi-Fi待機・負荷の6条件、各30 s・3反復、18試行を実施した。条件順は反復内で無作為化した。

ESP-NOWは1 Mbps・long preambleへ明示設定し、受信metadataのrate=0、sig\_mode=0を両端で確認した。PHY設定と受信結果を区別して残す。MACの送信成功はアプリ応答の成功ではない\cite{espnowGuide}ため、後者のRTTと欠落を測り、送信callbackの成功・失敗、APIエラー、echoキューの取りこぼしも保存した。アプリ再送は行わない。API受付失敗も送信要求の分母に含め、応答欠落を物理層の損失率へ読み替えない。時刻列は送信側の同じµs時計で、終了後1 sを応答猶予とする。UART115200によるCRC付き読み出しは測定後に行い、RTTへ含めない。Wi-Fi受信量には読み出しを含むカウンタ区間の実時間を使う。

ESP32-1/2間75 cmを維持した。送受信機、無線経路、PHYがAP中継のUDP比較と異なるので、その差をESP-NOWという方式だけの因果効果として扱わない。C5の80 MS/s・48 MHz・ゲイン20・FFT1024・LO2442 MHzは同じで、間欠取得と未校正dBFSの制約も同じである。
\begin{table}[htbp]\centering\small\caption{ESP-NOW操縦応答。表のChはESP-NOW側、Wi-Fi APはCh6固定。各9,000送信。Wi-Fi実受信は試行範囲Mbps。}\begin{tabular}{lrrrr}\toprule Wi-Fi / ESP-NOW & p99 ms & 20 ms超過\% & 欠落\% & Wi-Fi Mbps\\\midrule
'''+ '\n'.join(fullrows)+r'''\bottomrule\end{tabular}\end{table}
\plot{../espnow/espnow-blue-green}{1}{ESP-NOWとWi-Fiの実測RF。各画像は1反復目、注記は3反復統合値。Wi-Fiの名目帯域を白破線で示す。}
Wi-Fi負荷を加えた時、ESP-NOWの統合p99は同一Ch6で'''+value(key('off',6))+'→'+value(key('heavy',6))+' ms、隣接Ch7で'+value(key('off',7))+'→'+value(key('heavy',7))+' ms、分離Ch11で'+value(key('off',11))+'→'+value(key('heavy',11))+r''' msだった。数値の比較には欠落と期限超過も使い、遅い応答が欠落したことによる見かけのp99低下を改善と扱わない。各反復p99は公開JSONに残し、9,000パケットを9,000の独立な環境反復とはみなしていない。'''+'Ch11待機の各反復p99は'+f'{min(S[key("off",11)]["run_p99_ms"]):.1f}--{max(S[key("off",11)]["run_p99_ms"]):.1f}'+r''' msとばらついた。分離Ch11にも待機状態で大きな遅延があり、今回の結果は「周波数を離すと常に良い」ではない。試験用Wi-Fiを止めても室内の他の送信機やリンクの状態は残る。外来通信、受信余裕、送信待ち、処理のどれが主因かは今回分離していない。

\plot{../espnow/espnow-repeat-variation}{1}{同一Ch6・Wi-Fi負荷の全3反復。下段は届いた応答のRTT、赤破線は20 ms。欠落は点として現れない。上段と下段はUART開始時刻に基づく近似対応であり、パケット単位の時刻相関ではない。}
同じCh6・負荷ありでも反復p99は'''+variation_text+r''' msだった。1・2反復目では20 ms期限超過が0\%、3反復目では14.1\%に増えた。チャネルと負荷設定を固定しても尾部遅延は再現しなかった。Wi-Fi実受信も変わるため、一定の干渉強度を与えた比較ではない。単独基準、反復、期限超過、応答途絶を組み合わせ、1回の平均速度やスペクトルの見栄えから指令品質を判断しないことが実践上の学びである。原因を処理待ちとRF干渉へ分解するには、追加の処理時刻と送受信フレームの観測が必要となる。

'''+telemetry+r'''

\subsection{ロボコンでの意味と運用上の条件}
AP経路を外した小さい指令でも同じ2.4 GHz帯を使い、外部Wi-Fiが動作する配置で評価する必要がある。1 Mbpsはbitrateで、電波の幅が1 MHzという意味ではない。小さい指令でも帯域幅を持つ成分として観測される。今回のESP-NOWは64 byteの指令試験であり、映像や点群を運ぶ大容量転送の性能を測っていない。ROS 2トピックがそのままESP-NOWになる実装でもなく、PCやコントローラーとの橋渡しは別途必要で、その遅延は今回含まない。同じESP32無線にWi-Fi接続とESP-NOWを併用する場合、接続APとpeerのチャネル条件を考慮する必要がある\cite{espnowGuide}。今回の独立無線によるチャネル分離結果をそのまま同一チップへ適用しない。

距離、向き、移動、暗号化、通信途絶時の停止動作は未比較である。無線が接続しているかより、届いた指令の新しさと途絶を判断する方法が検討対象になるが、本測定だけで安全な停止期限を決められない。
'''+end+'\n'
pos=t.index(r'\section{主実験の結論と公開データの範囲}');t=t[:pos]+section+t[pos:]
t=t.replace('独立した外部BLEリンクを変え、','独立した外部BLEリンクとESP-NOW指令を変え、')
t=t.replace('追加69試行',f'追加{alltrials}試行').replace('主比較42、周期Wi-Fi9、BLE18の計69試行、207,000送信、189,858応答、39,149 I/Q取得',f'主比較42、周期Wi-Fi9、BLE18、ESP-NOW18の計{alltrials}試行、{allsent:,}送信、{allgot:,}応答、{allshots:,} I/Q取得')
if r'\bibitem{espnowGuide}' not in t:t=t.replace(r'\begin{thebibliography}{99}',r'\begin{thebibliography}{99}'+'\n'+r'\bibitem{espnowGuide} Espressif, ESP-NOW Programming Guide, \url{https://docs.espressif.com/projects/esp-idf/en/v6.0/esp32/api-reference/network/esp_now.html}.')
p.write_text(t)
p=R/'reports/twitter.tex';t=p.read_text();a=t.index(r'\section{細い信号が見えれば、何が分かるか}');b=t.index(r'\section{データと再現範囲}',a)
new=r'''\section{ESP-NOWにも近くのWi-Fiは影響する？}
ESP32-1/2間で64 byte・100 Hzの未暗号化unicastを往復させた。APを通らず、PHYは1 Mbps。MAC送信成功とアプリ応答を分ける\cite{espnow}。
他チームWi-FiはCh6 APで大容量TCPを流し、ESP-NOW側をCh6・Ch7・Ch11へ変えた。各30 s・3反復。
\begin{center}\includegraphics[width=\linewidth]{../experiments/figures/espnow/espnow-compact.pdf}\captionof{figure}{同一Ch6・Wi-Fi負荷の反復1と3。p99は8.6 / 123.8 ms。共通$-90$--$-45$ dBFS。白破線はWi-Fiの名目帯域。}\end{center}
\begin{center}\captionof{table}{Wi-Fi状態 / ESP-NOW Ch。APはCh6固定。}\small\begin{tabular}{@{}lrrr@{}}\toprule 条件 & p99 ms & 超過\% & 欠落\%\\\midrule
'''+ '\n'.join(rows)+r'''\bottomrule\end{tabular}\end{center}
同一Ch6ではWi-Fi待機'''+value(key('off',6))+'→負荷'+value(key('heavy',6))+r''' msだった。AP中継のUDPとは端末・経路・PHYが違い、差を方式だけの効果としない。
小さい指令を測った結果で、映像・点群転送、ROS 2との橋渡し、同じチップ内のWi-Fi併用は未検証である。
同じCh6負荷でも反復p99は'''+variation_text+r''' msと変動した。Ch11も待機から遅延が大きい。番号だけで良否を決めず、各チャネルの単独基準・反復・負荷中の期限超過と途絶を確かめる。
'''
t=t[:a]+new+t[b:]
# Put the BLE interpretation under its table, leaving the opposite column for ESP-NOW.
pos=t.index(r'\newpage',t.index(r'\section{Bluetoothも実通信と合わせて測る}'))
note=r'''\subsection{BLE画像で言える範囲}
広告2426 MHzは表示外である。通知時の細い成分は方式の違いを見る手掛かりだが、外来RFも含み、全てをBLEへ同定しない。間欠取得から全パケットやホッピングの連続軌跡は復元できない。
'''
t=t[:pos]+note+t[pos:];t=t.replace('今回の追加実験は69試行、207,000送信、39,149 I/Q取得',f'今回の追加実験は{alltrials}試行、{allsent:,}送信、{allshots:,} I/Q取得')
t=t.replace(r'\end{thebibliography}',r'\bibitem{espnow} \href{https://docs.espressif.com/projects/esp-idf/en/v6.0/esp32/api-reference/network/esp_now.html}{Espressif, ESP-NOW Programming Guide.}'+'\n'+r'\end{thebibliography}')
# Keep the data links and short primary-source list in the BLE column.
# The ESP-NOW column is dedicated to its results and interpretation.
a=t.index(r'\section{データと再現範囲}')
b=t.index(r'\end{thebibliography}',a)+len(r'\end{thebibliography}')
source=t[a:b]
source=source.replace('先行実験は構成が異なる補足として詳細版へ統合し、今回の表と混ぜていない。','先行実験は構成を区別して詳細版へ統合した。')
source='{\\footnotesize\n'+source.replace(r'\begin{thebibliography}{9}\small',r'\begin{thebibliography}{9}\footnotesize')+'}\n'
t=t[:a]+t[b:]
pos=t.index(r'\newpage',t.index(r'\subsection{BLE画像で言える範囲}'))
t=t[:pos]+source+t[pos:]
t=t.replace('外部BLEの広告・通知も比較し、','外部BLEの広告・通知、ESP-NOW指令も比較し、')
p.write_text(t)
p=R/'README.md';t=p.read_text();start=f'追加は{T["trials"]}試行（主42・周期Wi-Fi9・BLE18）、{T["control_sent"]:,}送信、{T["iq_snapshots_original"]:,} I/Q取得';new=f'追加は{alltrials}試行（主42・周期Wi-Fi9・BLE18・ESP-NOW18）、{allsent:,}送信、{allshots:,} I/Q取得';t=t.replace(start,new)
t=t.replace('- 通常Wi-Fiの2秒ON/OFF負荷',f'- ESP-NOWの64 byte・100 Hz指令も測定しました。同一Ch6のWi-Fi待機→負荷でRTT p99は{value(key("off",6))}→{value(key("heavy",6))} msでした。同じ負荷条件でも反復p99が{variation_text.replace("--", "〜")} msと変動しました。異なるAP経路とのプロトコルだけの因果比較ではありません。\n- 通常Wi-Fiの2秒ON/OFF負荷')
t=t.replace('`two-team`は両チーム負荷・周期Wi-Fi・BLE比較です。','`two-team`は両チーム負荷・周期Wi-Fi・BLE比較、`espnow`はESP-NOW指令と外部Wi-Fi比較です。');p.write_text(t)
print('Reports include',alltrials,'additional trials')
