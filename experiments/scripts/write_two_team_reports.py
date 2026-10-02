#!/usr/bin/env python3
"""Update the two report sources using checked anonymous experiment summaries."""
import json,re
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[2];D=R/'experiments/data/two-team';S=json.loads((D/'summary.json').read_text());M=json.loads((R/'experiments/data/manifest.json').read_text())['two_team']
def val(k,field='pooled_p99_ms'):return f'{S[k][field]:.1f}'
def mean(k,field):return f'{np.mean(S[k][field]):.2f}'
def rows(keys):
 return '\n'.join(label+' & '+val(k)+' & '+val(k,'deadline20_pct')+' & '+val(k,'loss_pct')+r'\\' for k,label in keys)
def table(keys,caption):
 return r'\begin{center}\captionof{table}{'+caption+r'}\small\begin{tabular}{@{}lrrr@{}}\toprule 条件 & p99 ms & 期限超過\% & 欠落\%\\\midrule '+rows(keys)+r'\bottomrule\end{tabular}\end{center}'
def fig(name,caption,width=r'\linewidth'):
 return r'\begin{center}\includegraphics[width='+width+']{../experiments/figures/two-team/'+name+r'.pdf}\captionof{figure}{'+caption+r'}\end{center}'
keys=[(f'team-heavy-ch{c}-w20-b{b}',label) for c,b,label in [(6,0,'他待機 Ch6'),(6,1,'両負荷 Ch6'),(7,0,'他待機 Ch7'),(7,1,'両負荷 Ch7'),(11,0,'他待機 Ch11'),(11,1,'両負荷 Ch11')]]
blekeys=[(f'ble-{own}-{kind}',label) for own,kind,label in [('off','off','操縦 / BLE停止'),('off','advert','操縦 / BLE広告'),('off','data','操縦 / BLE通知'),('heavy','off','重負荷 / BLE停止'),('heavy','advert','重負荷 / BLE広告'),('heavy','data','重負荷 / BLE通知')]]
burstkeys=[(f'team-heavy-ch{c}-w20-b2',f'周期負荷 Ch{c}') for c in (6,7,11)]
if any(k not in S or S[k]['runs']!=3 for k,_ in keys+blekeys+burstkeys):raise SystemExit('All three repeats must be published before generating reports')
p=R/'reports/twitter.tex';preamble=p.read_text().split(r'\begin{document}',1)[0]
body=r'''
\begin{document}
\twocolumn[{
\begin{center}{\LARGE\bfseries\sffamily ロボコンの通信を、他チームの負荷と一緒に測る\par}
\vspace{1mm}{\normalsize 同一・隣接・分離チャネル、帯域幅、Wi-FiとBluetoothの実測\par}
\vspace{.5mm}{\normalsize 貝淵蒼馬\par}\end{center}
\noindent\fbox{\parbox{\dimexpr\textwidth-2\fboxsep-2\fboxrule}{\small
\textbf{要旨}\quad 操縦と映像相当通信を同じAPへ通し、別チームも通信中の条件を比較した。
100 Hz UDPの応答とESP32-C5の実測I/Qから、帯域の重なりを青〜緑で示す。
今回の配置では他チーム負荷により、同一・隣接チャネルで遅延と期限超過が増えた。
通常Wi-Fiの周期負荷、外部BLEの広告・通知も比較し、画像と通信性能の両方から考察する。}}\vspace{2mm}}]
\section{測りたいのは「他チームも通信中」}
スマートフォンからの指令とロボットからの映像・点群は、同じAPや帯域を共有する。
操縦だけが動く構成では、大容量通信中の他チームの影響を十分に再現できない。
今回は自チームのUDP指令とTCP模擬データを\textbf{STA→AP→STA}へ通し、独立した他チームにもTCPを流した。
スマートフォン、ROS 2、実映像やモータは使用していない。
'''+fig('two-team-setup-compact','自チームは2端末間をAPが中継。他チームは独立APの飽和TCP通信。')+r'''
\section{条件と、数値の読み方}
観測PC（Intel BE200）はCh6・20 MHz AP、ESP32-3はコントローラー役、ラップトップ2（MT7921E）はロボット役。
ラップトップ1（Intel AX210）から有線でインターネットを共有した。
他チームはESP32-2 AP→ESP32-1 STAで、Ch6・Ch7・Ch11、Ch1の20/40 MHzを比較する。

ESP32-1/2間75 cm、C5から両ボードへ約40 cm・90 cm、観測PCとラップトップ2間約30 cm。
位置固定で距離掃引ではなく、ESP32-3の距離は未測定。
1試行30 s・3,000送信、各条件3反復、反復内の順序を入れ替えた。
64 byte・100 Hz UDPを反射し、送信側の同じ時計で往復遅延（RTT）を測る。
p99は戻った応答の99パーセンタイル。\textbf{20 ms期限超過には欠落も含む}。
20 msは比較用の目標で、ロボットの安全限界を示す値ではない。
\newpage
\section{両チームに負荷をかけた結果}
'''+table(keys,'自チーム大容量通信中の操縦応答。各9,000送信の統合値。期限は20 ms。')+r'''
他チームを待機から負荷へ変えた時、統合p99は同一Ch6で'''+val('team-heavy-ch6-w20-b0')+'→'+val('team-heavy-ch6-w20-b1')+r''' ms、隣接Ch7で'''+val('team-heavy-ch7-w20-b0')+'→'+val('team-heavy-ch7-w20-b1')+r''' msとなった。
分離Ch11は'''+val('team-heavy-ch11-w20-b0')+'→'+val('team-heavy-ch11-w20-b1')+r''' msで、今回の配置では増分が小さかった。
20 ms期限超過も同一・隣接で増えた。欠落率だけなら逆方向に見える条件があり、\textbf{「届く率」と「間に合う率」を分ける必要がある}。

\subsection{まず単独時の限界を見つける}
操縦のみ・他待機でもp99は117--120 ms、期限超過は47--49\%だった。
この実験系は既に20 ms目標を満たさない。AP、端末処理、無線のどこで遅れるかは未分離であり、全遅延を他チームの干渉へ帰属しない。
RTTを半分にして片道値とみなすこともできない。

\subsection{要求Mbpsより、実際に届いた量}
TCP模擬データは192 KiBを10 Hzで送ろうとする、要求15.73 Mbpsの負荷である。
実受信は今回約0.6--1.6 Mbpsにとどまり、要求量を達成していない。
送信側の逆圧がかかる飽和状態を測っており、15.73 Mbpsの映像を再現したとは言わない。
他チームもチャネル別に約0.4--4.7 Mbpsと異なる。
自チームのデータはAPを通るため無線を2回通過する。Mbpsを揃えても空中時間は同じにならない。

\subsection{ロボコンへ持ち帰る問い}
自分のカメラを動かし、隣のチームにも実際の通信を流してもらった時、指令の期限は守れるか。
その比較を\textbf{転送速度・RTT・期限超過・欠落}の組で行う。
接続表示と平均Mbpsだけでは、今回の遅い応答を見抜けない。
\clearpage
\twocolumn[{
'''+fig('two-team-blue-green-compact','自チームはCh6・20 MHzで大容量TCP＋操縦UDP。各画像は1反復目、p99注記は3反復統合。白破線は自チームの名目帯域。色尺度・ゲイン共通。',r'.98\textwidth')+r'''}]
\section{チャネル番号より、帯域の重なり}
Ch6の2437 MHzとCh7の2442 MHzは5 MHzしか離れない。
20 MHz幅で番号を1つずらすと広く重なり、画像でも他チームの帯域が主リンクへ重なる。
Ch11の2462 MHzへ離すと、強い成分の位置が高周波側へ分かれる。
\textbf{同一Ch6が今回最も遅く、隣接が常に最悪という結果ではない}。

同一チャネルでの送信待ち、部分重複による受信妨害、再送、APや端末の処理が候補になる\cite{rf}。
再送やキャリアセンスを測っていないため、画像で原因を決められない。
チャネル別の実負荷量も違い、周波数だけを揃えた因果実験ではない。
'''+fig('two-team-width-compact','他チームCh1の接続幅を20/40 MHzへ変更。副チャネル追加でCh6と名目帯域が重なる。')+r'''
20→40 MHzでp99は'''+val('team-heavy-ch1-w20-b1')+'→'+val('team-heavy-ch1-w40-b1')+r''' ms、期限超過は'''+val('team-heavy-ch1-w20-b1','deadline20_pct')+'→'+val('team-heavy-ch1-w40-b1','deadline20_pct')+r'''\%だった。
今回はp99の明確な悪化を示さず、「広いほど必ず悪い」とは言えない。
接続幅の拡大と、全パケットが40 MHzで送信されることも別である。
\subsection{画像の色は通信性能ではない}
{\small C5：80 MS/s・帯域48 MHz・ゲイン20・FFT1024。
各行は約205 $\mu$s、名目RF観測時間比は約0.4\%。
dBFSは未校正で感度も均一ではない。色を占有率や欠落率へ換算しない。外来信号も含む。}
\newpage
\section{意図的な周期負荷を加える}
所有する実験リンクへ、通常のWi-Fi TCPを2 s ON・2 s OFFで流した。
自チームの大容量通信は維持し、他チームCh6・Ch7・Ch11で各3反復測った。
ON/OFF操作と実受信量を残し、単に「緑が多い」から性能を推測しない。
'''+fig('wifi-burst-single','上：実測FFT。下：同じ試行の応答RTT。緑帯はUARTによるON操作区間。両時計の対応は近似で、パケット単位の同期ではない。')+r'''
波形は連続送信ではなく、TCPのバースト・再送・送信待ちを含む。
下図にない応答は欠落であり、遅い点が減ったことを改善と判断しない。
ON/OFF時刻も個々のRF送信時刻ではないため、マイクロ秒の因果対応は評価していない。

\clearpage
\twocolumn[{
'''+fig('ble-narrow-blue-green','BLE比較のCh6帯域上側2450--2470 MHzを拡大。通知時に短い狭帯域成分が見える。各画像は1反復目、色尺度はこの図内で共通の$-90$--$-60$ dBFS。前ページの同じ色とは電力が異なる。',r'.98\textwidth')+r'''}]
\section{Bluetoothも実通信と合わせて測る}
ESP32-1/2を独立したBLEリンクへ切り替え、Wi-Fi側の端末は同じ構成を保った。
BLE停止、20 ms設定の非接続広告、BLE 1MのGATT通知を、自チーム大容量通信あり・なしで各3反復比較した。
広告は受信機の復号数、通知は実受信bytes、MTU・接続間隔も記録した。
同じチップ内の共存制御やBluetooth音声の試験ではない。
'''+table(blekeys,'外部BLEと操縦応答。期限は20 ms、各3反復。')+r'''
Wi-Fi大容量通信中のp99は、BLE停止'''+val('ble-heavy-off')+r''' ms、広告'''+val('ble-heavy-advert')+r''' ms、通知'''+val('ble-heavy-data')+r''' msだった。
BLE通知の実受信量はWi-Fi待機'''+mean('ble-off-data','delivered_other_mbps')+r''' Mbps、Wi-Fi負荷'''+mean('ble-heavy-data','delivered_other_mbps')+r''' Mbps（試行平均）。
片方の方式だけでなく、両リンクの通信量と操縦の期限超過を確認する。今回はBLE追加でWi-Fiのp99が大幅に増える結果ではなく、BLE通知の到達量の変化が比較の手掛かりになった。
\newpage
\section{細い信号が見えれば、何が分かるか}
BLEの広告は2402・2426・2480 MHz、接続通信はデータチャネルを使う\cite{ble}。
細い成分は広帯域Wi-Fiとの違いを観察する手掛かりになる。
ただしC5は短い取得を間欠的に行うため、全パケットやホッピングの連続軌跡を捕らえたわけではない。
2426 MHz以外の広告周波数は今回のLOから遠く、3広告チャネルを均一感度で比較していない。
外来RFもあり、画像だけで全ての細線をBLEへ同定しない。

この測定からBluetooth全般が無害／有害とは決められない。
通知の負荷、端末、位置、Bluetooth方式が変われば結果も変わる。
今回はClassic、音声、BLE 2M、距離・向き・移動の掃引は未測定である。

\section{会場で比較する時の手順}
\begin{enumerate}
\item 操縦だけで期限超過を測り、まず主リンクの基準を作る。
\item 自分の映像・点群を流し、要求量と実到達量を分ける。
\item 他チームにも通信してもらい、同一・隣接・分離と幅を比較する。
\item Bluetoothなどの別方式も動かし、両方の性能を見る。
\end{enumerate}
設定変更の判断には、各反復の変動と本来の制御周期を使う。
今回の固定室内配置とESP32を含む通信系の数値を、実ロボットや競技用ルーターへそのまま外挿しない。
改善策の候補は映像負荷の制限、古い指令を捨てる処理、通信途絶の検出であり、効果と停止しきい値は別途検証が必要である。

\section{データと再現範囲}
今回の追加実験は'''+str(M['trials'])+r'''試行、'''+f"{M['control_sent']:,}"+r'''送信、'''+f"{M['iq_snapshots_original']:,}"+r''' I/Q取得。
相対時刻・FFT電力・匿名条件・取得用コードと詳細版を公開した。
先行実験は構成が異なる補足として詳細版へ統合し、今回の表と混ぜていない。
\url{https://github.com/Raptor-zip/esp-sdr-robotics-wifi}
\begin{thebibliography}{9}\small
\bibitem{rf} \href{https://www.cisco.com/c/en/us/td/docs/wireless/controller/9800/technical-reference/wireless-rf-reference-guide.html}{Cisco, Wireless RF Reference Guide.}
\bibitem{ble} \href{https://www.bluetooth.com/bluetooth-le-primer/}{Bluetooth SIG, Bluetooth LE Primer.}
\end{thebibliography}
\end{document}
'''
p.write_text(preamble+body)
# Retain all previous measurements, explicitly separated by topology.
p=R/'reports/full.tex';t=p.read_text();marker='% BEGIN TWO TEAM STUDY';endmarker='% END TWO TEAM STUDY'
if marker in t:t=t[:t.index(marker)]+t[t.index(endmarker)+len(endmarker):]
abstract=r'''\begin{abstract}
ロボコンで操縦・映像・点群が同じWi-Fiを共有する状況を模し、STA→AP→STAのUDP応答と大容量TCPを、他チームも通信中の条件で比較した。同一・隣接・分離チャネル、20/40 MHz幅、通常Wi-Fiの周期負荷、独立した外部BLEリンクを変え、実測I/Qの青〜緑画像と応答遅延・期限超過・欠落・実受信量を対応づける。追加69試行を、構成の異なる先行56通信試行および115受信観測系列と区別して統合した。実ROS 2や実ロボットの試験ではなく、未校正の間欠SDRとUDP/TCP模擬負荷による固定室内配置の比較である。
\end{abstract}'''
a=t.index(r'\begin{abstract}');b=t.index(r'\end{abstract}',a)+len(r'\end{abstract}');t=t[:a]+abstract+t[b:]
# These macros reuse the old supplemental values; leave their contents intact.
pos=t.index(r'\section{目的：操縦通信にとっての無線品質}')
full=marker+r'''
\section{主実験：両チームが通信するロボコンの構成}
本稿の主実験は、スマートフォンとロボットPCがルーターを通して指令・映像・点群を送る状況に近づけるため、UDPとTCPをいずれもSTA→AP→STAへ通した。自チームは観測PC（Intel BE200）をCh6・20 MHz AP、ESP32-3をコントローラー役、ラップトップ2（MT7921E）をロボットPC役とする。他チームはESP32-2 AP→ESP32-1 STAの独立した飽和TCP通信である。ラップトップ1（Intel AX210）のインターネット共有は有線で維持した。
\plot{../two-team/two-team-setup}{1}{主実験の構成。自チームの指令と大容量模擬データはAPによる無線中継を通る。}
実スマートフォン、ROS 2/DDS、実画像、点群内容、モーターは使っていない。100 Hz・64 byteのUDPを反射し、ESP32-3の同じ1 $\mu$s刻み時計で予定送信、実送信、応答時刻を記録する。RTTはアプリケーション往復時間で、片道遅延や制御応答ではない。3,000送信後に1秒の猶予を設け、返らなかった応答を欠落とする。p99は届いた応答だけ、20 ms期限超過は欠落も含む。20 msは比較用目標で安全停止のしきい値ではない。

大容量データは192 KiBを10 Hzで送ろうとする要求15.73 MbpsのTCP模擬負荷である。逆圧で送れない場合は送信側が待ち、要求速度を達成したとは扱わない。自チームの受信bytesは30 sの計測窓で数え、他チームは前後のカウンタ差とホスト区間で数えた。他チームの窓には終了猶予やテレメトリ取得も含まれ、窓は完全一致しない。自チームのデータは無線を2回、他チームは1回通るので、アプリケーションMbpsから同じ空中時間を仮定できない。

ESP32-1/2間75 cm、C5から両ボードへ約40 cm・90 cm、観測PCとラップトップ2間約30 cm。距離とボード番号の対応、ESP32-3の距離は未測定であり、距離掃引ではない。自チーム負荷あり・なし、他チーム負荷あり・なし、Ch6・Ch7・Ch11の12条件に、両負荷のCh1・20/40 MHzを加えた14条件・3反復、計42試行を実施した。各30 s、各3,000送信、固定種で反復内の順序を無作為化した。他チーム待機にもAPビーコンとTCP接続は残す。

C5は80 MS/s、16,380 I/Q、48 MHzアナログ帯域、手動ゲイン20、FFT1024、DC除去とHann窓を使用した。全取得と時刻ダンプのCRC32を照合した。LOは2442 MHz、Ch1の幅比較だけ2427 MHz。dBFSは未校正で、RF観測時間比は約0.4\%。ESP時計とホストのUART開始時計は近似的に対応づけるため、パケット単位のI/Qとの一致判定には使わない。

\section{同一・隣接・分離：両チーム負荷の結果}
\begin{table}[htbp]\centering\small\caption{両チーム比較。各条件3反復9,000送信。自TCP・他TCPは各試行実受信Mbpsの範囲。期限は20 ms。}\begin{tabular}{llrrrrr}\toprule 自負荷 & 他条件 & p99 ms & 超過\% & 欠落\% & 自TCP & 他TCP\\\midrule
'''
for k,v in S.items():
 if not k.startswith('team-') or k.endswith('b2'):continue
 own='あり' if '-heavy-' in k else 'なし';c=k.split('-ch')[1].split('-')[0];w=k.split('-w')[1].split('-')[0];other='負荷' if k.endswith('b1') else '待機';aa=v['delivered_own_mbps'];bb=v['delivered_other_mbps'];full+=f'{own} & Ch{c}/{w}/{other} & {val(k)} & {val(k,"deadline20_pct")} & {val(k,"loss_pct")} & {min(aa):.2f}--{max(aa):.2f} & {min(bb):.2f}--{max(bb):.2f}'+r'\\'+'\n'
full+=r'''\bottomrule\end{tabular}\end{table}
\plot{../two-team/two-team-blue-green}{1}{同一・隣接・分離の実測スペクトル。各画像は1反復目、RTT注記は3反復統合値。白破線は自チームの名目帯域、色尺度とゲインは共通。}
自チーム大容量通信中、他チームの負荷によるp99の増分はCh6で'''+f"{S['team-heavy-ch6-w20-b1']['pooled_p99_ms']-S['team-heavy-ch6-w20-b0']['pooled_p99_ms']:.1f}"+r''' ms、Ch7で'''+f"{S['team-heavy-ch7-w20-b1']['pooled_p99_ms']-S['team-heavy-ch7-w20-b0']['pooled_p99_ms']:.1f}"+r''' ms、Ch11で'''+f"{S['team-heavy-ch11-w20-b1']['pooled_p99_ms']-S['team-heavy-ch11-w20-b0']['pooled_p99_ms']:.1f}"+r''' msだった。20 ms期限超過の増分も同一・隣接で大きい。一方、欠落率は両負荷Ch6/Ch7で待機より小さく、欠落だけで通信の良否を判定すると期限超過の悪化を見落とす。p99も受信応答に条件づけた指標なので、欠落と併せて評価する。

Ch6とCh7の中心差は5 MHzで20 MHz幅の通信は大きく重なる。画像で重なる領域と、Ch11で分かれる領域を見られる。ただし同一Ch6が今回最も遅く、部分重複がいつでも最悪とは言えない。同一チャネルの送信待ち、部分重複の受信妨害、RF再送、APや端末の処理は候補になる\cite{ciscoRF}が、今回の測定はそれらを原因分離していない。他チームの受信量もCh6約2.5--4.7、Ch7約2.3--3.8、Ch11約1.0--1.3 Mbpsと異なり、等しい空中時間の周波数比較ではない。

\subsection{基準が悪いと、干渉だけでは説明できない}
操縦のみ・他待機でもp99は117--120 ms、20 ms期限超過は47--49\%であり、この系は既に目標を満たさない。自チーム模擬TCPは要求15.73 Mbpsに対して約0.6--1.6 Mbpsしか到達していない。これは今回の構成の処理・伝送限界を含む値で、競技用ルーターやPC同士のROS 2の上限を示すものではない。他チームの効果は同じ自負荷・他チャネルの待機との差として論じ、全遅延を干渉へ帰属しない。ユーザーが使う実システムでは、まず単独で期限を満たす基準を作り、双方が実負荷を流した時の差を見る手順が有用である。
\plot{../two-team/two-team-interaction}{1}{各反復のp99と統合期限超過。自負荷なし・ありを分け、他負荷の効果と反復変動を確認する。}

\section{帯域幅：スペクトルの拡大と操縦性能は別に確認する}
\plot{../two-team/two-team-width}{1}{他チームCh1の20/40 MHz。クライアントの接続幅と副チャネルを読み出した。}
Ch1の20 MHzとCh6は名目帯域が分かれるが、上側副チャネルを加えた40 MHzはCh6へ重なる。主実験の統合p99は20 MHz '''+val('team-heavy-ch1-w20-b1')+r''' ms、40 MHz '''+val('team-heavy-ch1-w40-b1')+r''' ms、期限超過はそれぞれ'''+val('team-heavy-ch1-w20-b1','deadline20_pct')+'\%、'+val('team-heavy-ch1-w40-b1','deadline20_pct')+r'''\%だった。p99の明確な悪化は確認しなかった。他チーム実受信量も20 MHz約0.9--1.2、40 MHz約0.4--0.8 Mbpsと違うため、「広いほど速い」「広いほど必ず操縦が悪い」のどちらもこの結果から言えない。

幅の拡大は1送信あたりの情報量と隣のリンクへ残る帯域の両方を変える\cite{ciscoRF}。実接続40 MHzでも全パケットが40 MHz波形になるとは限らない。重なりを避けやすい設定と、実際に期限を守る設定を区別し、自分の通信負荷と他チーム負荷の組で測る必要がある。

\section{通常Wi-Fiの周期負荷による意図的なストレス試験}
自チームの大容量通信を保ち、他チームの通常TCP負荷を2 s ON・2 s OFFで操作した。Ch6・Ch7・Ch11、各3反復、計9試行。UARTコマンドの前後時刻と実受信bytesを保存した。所有リンクへの通常のデータ通信を使った試験である。
\plot{../two-team/wifi-burst-blue-green}{1}{周期負荷の実測FFTと同じ試行のRTT。緑帯はON操作区間で、RF送信の厳密な開始時刻ではない。}
\begin{table}[htbp]\centering\small\caption{周期負荷30 s全体。ON/OFFを含み、各9,000送信。}\begin{tabular}{lrrr}\toprule 条件 & p99 ms & 20 ms超過\% & 欠落\%\\\midrule
'''+rows(burstkeys)+r'''\bottomrule\end{tabular}\end{table}
TCP送信は負荷ONでもバーストや再送を含み、連続したRFではない。画像の取得窓と指令の時刻対応は近似であり、個々のパケットがどのRFへ妨げられたかは特定していない。欠落した応答はRTT点として図に出ないため、遅い点の減少だけを改善と扱わない。実装上の波形ON/OFF操作と、通信性能を同時に記録する例として位置付ける。

\section{独立したBluetooth LEリンクとの比較}
ESP32-1/2をBLE専用送受信機へ切り替え、Wi-Fi端末とAPは保った。BLE停止、20 ms設定の非接続広告、BLE 1MのGATT通知を、自チーム大容量通信なし・ありで各3反復、計18試行比較した。広告は受信側で実際の復号回数、通知は受信bytesと件数を残す。GATT MTU、接続間隔、送信API受付量とエラーも読み出した。BLEの負荷を2 ms周期で要求するが、実到達量は受信カウンタで評価する。送信APIの受付エラーはスタックの逆圧も含み、PHYパケット損失率へ読み替えない。
\plot{../two-team/ble-blue-green}{1}{BLE停止・広告・通知と、自チームWi-Fi大容量通信の有無。実測FFTを共通色尺度で表示。}
\plot{../two-team/ble-narrow-blue-green}{1}{Ch6の上側2450--2470 MHzを拡大。弱い成分を読むため、この図内で共通の$-90$--$-60$ dBFS尺度を使用する。前図とは同じ色が同じ電力を示さない。細線の全てをBLEへ帰属しない。}
\begin{table}[htbp]\centering\small\caption{外部BLEとWi-Fi操縦性能。BLE受信は試行平均Mbps。広告は復号件数を個別JSONに保存。}\begin{tabular}{lrrrr}\toprule 条件 & p99 ms & 20 ms超過\% & 欠落\% & BLE受信\\\midrule
'''
for k,label in blekeys:full+=label+' & '+val(k)+' & '+val(k,'deadline20_pct')+' & '+val(k,'loss_pct')+' & '+mean(k,'delivered_other_mbps')+r'\\'+'\n'
full+=r'''\bottomrule\end{tabular}\end{table}
Wi-Fi大容量通信中のp99はBLE停止'''+val('ble-heavy-off')+' ms、広告'+val('ble-heavy-advert')+' ms、通知'+val('ble-heavy-data')+r''' ms。BLE通知の実受信量はWi-Fi待機'''+mean('ble-off-data','delivered_other_mbps')+' Mbps、Wi-Fi負荷'+mean('ble-heavy-data','delivered_other_mbps')+r''' Mbpsだった。Wi-Fiの悪化だけを探すのでなく、BLE側の受信量と両方式の性能を併せて見る比較である。今回のBLE追加ではWi-Fiのp99が大幅に増える結果ではなかったが、BLE通知の実受信量はWi-Fi負荷の有無で変わった。どちらのリンクへ影響が出るかは、方式と負荷の組合せで確認する必要がある。因果評価には同じ方式・負荷・配置の反復が必要で、この少数反復の室内結果からBluetooth全般を無害または有害と決めない。

BLEの広告は2402・2426・2480 MHz、接続通信はデータチャネルを使う\cite{blePrimer}。細い信号と広帯域Wi-Fiの違いが観察の手掛かりになる。ただし間欠取得からホッピングの連続軌跡や全パケットを復元したとは扱わない。LO2442 MHzでは2426 MHz以外の広告周波数が遠く、全広告チャネルを均一感度で観測していない。室内外来信号が混ざるため細線の全てをBLEへ帰属しない。これは外部の独立BLEリンクの比較であり、同一チップ内の共存制御、Bluetooth Classic、音声、BLE 2Mの測定ではない。

\section{主実験の結論と公開データの範囲}
両チームが負荷を流す今回の固定配置では同一・隣接チャネルで操縦期限超過が増え、分離Ch11では増分が小さかった。帯域の重なりをSDRで見ながら、待機との差、実受信量、RTTと欠落を同時に比較する方法を示した。ただし主リンクの単独基準も不良であり、端末構成とRFを原因分離せずに競技場へ外挿できない。帯域幅の比較は単調な悪化を示さず、Bluetooth比較も指定のBLE負荷と配置に限定する。

ロボコンでは単独時の期限をまず満たし、自分の映像・点群と他チーム通信を同時に動かす。その時の期限超過や最長応答間隔に基づいて、負荷制限・古い指令の破棄・通信途絶の検出などを検討する。それらの改善効果と安全な停止しきい値は本実験では検証していない。

主比較42、周期Wi-Fi9、BLE18の計'''+str(M['trials'])+'試行、'+f"{M['control_sent']:,}"+'送信、'+f"{M['control_received']:,}"+'応答、'+f"{M['iq_snapshots_original']:,}"+r''' I/Q取得を追加した。公開した相対時刻から統計を独立再計算し、全ファイルSHA-256を確認する。元I/Qとホストログ、元フラッシュは非公開保管する。公開FFTから図、公開時刻から表を再生成できるが、RF復号や元I/Qからの再FFTは公開ファイルだけでは再現できない。

\clearpage
\section{先行実験の位置付け：構成が異なる補足}
以下は先行56通信試行と115受信観測系列を保持した補足である。先行の別AP比較では主リンクが操縦中心であり、本稿前半の両チーム負荷とSTA→AP→STA構成とは異なる。数値を同じ群へ統合せず、設定依存性とSDR画像の読み方を支える結果として参照する。先行BLE観測だけでは性能劣化を評価していなかったが、前半には独立BLEリンクとWi-Fi性能の同時比較を追加した。
'''+endmarker+'\n'
t=t[:pos]+full+t[pos:];t=t.replace(r'\usepackage{amsmath,graphicx,booktabs,siunitx,hyperref,float,tikz}',r'\usepackage{amsmath,graphicx,booktabs,siunitx,hyperref,float,tikz,caption}')
t=re.sub(r'^\\bibitem\{blePrimer\}.*\n','',t,flags=re.M)
t=t.replace(r'\bibitem{blePrimer} \href{https://www.bluetooth.com/bluetooth-le-primer/}{Bluetooth SIG, Bluetooth LE Primer.}'+'\n','')
t=t.replace(r'\begin{thebibliography}{99}',r'\begin{thebibliography}{99}'+'\n'+r'\bibitem{blePrimer} \href{https://www.bluetooth.com/bluetooth-le-primer/}{Bluetooth SIG, Bluetooth LE Primer.}')
t=t.replace("20 MHz '' ", '20 MHz ')
p.write_text(t)
print('Updated full.tex and twitter.tex from',M['trials'],'actual trials')
p=R/'README.md';t=p.read_text();a=t.index('## 実験から得られたこと');b=t.index('## ディレクトリ',a)
t=t[:a]+'''## 実験から得られたこと

- 自チームの大容量通信中、他チーム負荷によるRTT p99の増分は、同一Ch6で約23 ms、隣接Ch7で約9 ms、分離Ch11で約1 msでした。今回の固定配置の結果で、他チームの実通信量も異なります。
- 操縦だけでもp99が117–120 msで、20 ms目標を満たしていません。全遅延を他チーム干渉へ帰属せず、同じ条件の待機との差で考察します。
- 20/40 MHzの比較はp99の単調な悪化を示しませんでした。帯域の重なり、実受信量、期限超過を一緒に見る必要があります。
- 通常Wi-Fiの2秒ON/OFF負荷と、独立したBLEの停止・広告・GATT通知を比較しました。BLEは実際の広告復号・通知受信を確認し、Wi-Fi操縦応答と同時に記録しています。

追加は'''+str(M['trials'])+'試行（主42・周期Wi-Fi9・BLE18）、'+f"{M['control_sent']:,}"+'送信、'+f"{M['iq_snapshots_original']:,}"+''' I/Q取得です。構成の異なる先行56通信試行、115受信観測系列も詳細版へ補足として保持しました。実ROS 2や映像コーデックではなく、UDP/TCP模擬負荷のアプリケーション測定です。

青〜緑は未校正の相対FFT電力（dBFS）です。各行は約205 µsの間欠取得で、連続時間や占有率ではありません。[測定方法と限界](docs/two-team-method.md)も参照してください。

'''+t[b:]
t=t.replace('チャンネルの重なり、20/40 MHzの幅、同じAPでの映像相当負荷が、操縦の応答にどう現れるかを調べました。','指令と大容量通信がAPを中継する構成で、他チームも通信中のチャネル・幅・外部Bluetoothの影響を調べました。').replace('experiments/figures/robotics/robotics-blue-green.png','experiments/figures/two-team/two-team-blue-green.png').replace('| `experiments/firmware/robotics/` | 追加ESP32の通信実験ファームウェア |','| `experiments/firmware/` | ESP32の通信負荷・コントローラー・BLEファームウェア |').replace('`robotics`は操縦通信の比較です。','`robotics`は先行操縦通信、`two-team`は両チーム負荷・周期Wi-Fi・BLE比較です。')
p.write_text(t)
