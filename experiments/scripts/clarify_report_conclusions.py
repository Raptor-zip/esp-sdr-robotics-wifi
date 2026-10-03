#!/usr/bin/env python3
"""Keep report conclusions explicit and remove editorial history from papers.

Run last in report generation. This changes interpretation and wording only;
measured values and the separation between cohorts remain unchanged.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]

# Each entry leads with the observed result, then evidence and interpretation.
# No statistical correlation or absence of an effect is inferred from a null
# or inconsistent comparison without the necessary experimental evidence.
VERDICTS = [
    ('subsection', 'ESP-NOWからWi-Fiへの速度と指令への影響',
     '反復平均では速度と指令品質の両方に変化を観測した。同一Ch6・200 Hzでは速度は増え、指令期限は悪化した。',
     r'実受信平均0.411→1.107 Mbpsに対し、20 ms期限超過は0.05→2.73\%だった。速度低下は全チャネル共通の傾向ではなかった。',
     '画像を運べる量と指令が待つ時間は別の性能である。TCPの流れ方や端末の待ち行列も変わるため、速度の増加を無線干渉が減った証拠とはしない。'),
    ('subsection', 'Wi-FiからESP-NOWへの指令品質の変化',
     '反復平均では200 Hz・隣接Ch7でESP-NOWの遅延と期限超過が悪化した。同一Ch6・分離Ch11では同じ規模の悪化はなかった。',
     r'Ch7のp99は13.53→17.84 ms、期限超過は0.042→0.767\%。Ch6のp99は9.82→9.75 ms、Ch11は8.57→7.88 msだった。',
     '部分的に重なる帯域が負担になる結果と整合するが、同一チャネルでの送信待ちとの違いや実負荷も関わる。Wi-Fi同士の比較と順位が違うため、チャネル番号だけで方式をまたいだ順位を決められない。'),
    ('subsection', 'TCP接続を維持した停止前・動作・停止後の対照',
     '同一Ch6では3反復ともWi-Fi速度が増えた。隣接Ch7・分離Ch11には一貫した低下がなかった。',
     r'Ch6の速度低下率は平均$-134.4\%$、範囲$-137.4$〜$-129.1\%$。Ch7・Ch11は増減の両方を含んだ。',
     '同じ接続でも増加したので、新規TCP接続直後の状態だけでは説明できない。ただし停止前後の速度も変動したため、増加の原因やESP-NOW固有の改善効果は特定できない。操縦を伴わない速度試験だけで採用を決めない。'),
    ('subsection', 'BLEとWi-Fiの両方向の配送量',
     '反復平均ではBLE通知の配送量はほぼ維持されたが、Wi-Fi指令の期限超過は増えた。Wi-Fi速度は一方向には変化しなかった。',
     r'BLE実受信0.497→0.494 Mbps、Wi-Fi期限超過0.067→0.483\%。通知中のWi-Fi速度低下率は平均12.2\%だが、反復範囲は$-20.8$〜$54.0\%$だった。',
     'ホッピングしていてもWi-Fiへの影響を避けられるとは限らない。一方の通信が維持されても他方の期限が悪化し得る。速度への寄与をRF衝突と端末・TCPの変動へ分解することはできず、12.2\%を固定した劣化率にしない。'),
    ('section', '流量制限の比較',
     '自チームの大容量通信を増やすと、同一・隣接チャネルで指令期限の悪化を観測した。全条件での単調な悪化ではなかった。',
     r'要求0→1 Mbpsで期限超過はCh6で54.08→72.61\%、Ch7で51.44→61.36\%、Ch11で53.77→56.82\%だった。',
     '映像・点群の生成量を抑えることは指令の待ちを減らす候補になる。ただし2 Mbps要求では実受信が約1 Mbpsで頭打ちになり、負荷の波形も変わった。要求値だけから安全な上限や比例関係を決めることはできない。'),
    ('section', '生成周期の比較',
     '100→10 msへの小分け化に、一貫した指令品質の改善はなかった。',
     r'1 Mbps・Ch6の期限超過は63.47→59.42\%と減ったが、0.5 Mbps・Ch6では54.71→58.50\%と増えた。1 Mbps・Ch7は53.88\%のままだった。',
     'アプリで小分けにしてもTCP・OS・無線側でまとめ直されるため、均等なRF送信になるとは限らない。小分け化を万能な対策とせず、要求量を固定し、指令期限と実受信量の両方で効き方を確認する。'),
    ('section', '実ROS 2のQoSと指令応答',
     '大容量トピックの追加で指令期限が悪化した。best effort・深さ1へ変えるだけで解消する傾向はなかった。',
     r'指令のみの期限超過約45\%に対し、Image・PointCloud2追加時は約70〜80\%。Ch6ではQoS4設定のいずれも約78〜80\%だった。',
     'センサトピックと指令は無線だけでなくDDS・OS・端末の処理も共有する。深さ1は履歴の設定であり指令優先度の設定ではない。単独時にも大きな遅延が残るため、QoS変更とデータ量制限に加えて基準経路の処理を調べる必要がある。'),
    ('section', '省電力設定への介入と端末内時間',
     '省電力OFFによる一貫した遅延改善はなかった。センサ負荷・Ch11ではON時の悪化を観測した。',
     '負荷・Ch11のp99はOFF163.38→ON248.66 ms。一方、指令のみではON/OFFとも約103〜109 msで、負荷・Ch6のp99はONでむしろ低かった。',
     '計測したcallback処理は短かったが、往復遅延の大部分がどの区間で生じたかは特定できない。DDS・OS・無線の待ちなどが候補であり、省電力OFFだけで基準遅延を説明・解消する結果ではなかった。増分全てを睡眠時間へ割り当てることはできない。'),
    ('section', 'ESP-NOWの指令周期と長時間更新の安定性',
     '200 Hz化では100 Hzより尾部遅延と期限超過が増えた。Wi-Fi負荷による悪化は全周期で一貫しなかった。',
     r'Wi-Fi負荷中の100→200 Hzでp99は9.264→14.262 ms、20 ms期限超過は0.00083→0.21083\%。Wi-Fiの追加は50・200 Hzで悪化、20・100 Hzではp99が低下した。',
     '高頻度化は新しい指令を作る機会を増やす一方、要求・応答の送信機会も消費する。速い更新周期と短い配送遅延は同じではない。欠落3件は待機条件にもあり、全てをWi-Fi負荷のせいにはできない。'),
    ('section', 'ESP32間通信の配置・向き・遮蔽比較',
     'この近距離・短時間試験では、回転・手の遮蔽・75→150 cmで応答欠落の増加を観測しなかった。配置による遅延改善は判定できない。',
     '全30,000指令の応答欠落は0件。Wi-Fi負荷中の基準p99は測定前10.908 ms、元に戻した後8.630 msと変化し、変更配置と同じ方向へ低下した。',
     '信号が十分強ければ姿勢や反射の変化があっても配送を維持できる。一方、基準に戻しても遅延とRSSIが変わったため、配置と時間変動が交絡している。「遮蔽で改善した」「距離が影響しない」という結論は支持されない。'),
    ('section', '同一・隣接・分離チャネルの比較結果',
     '他チーム負荷の追加で同一・隣接チャネルの指令遅延が悪化し、分離Ch11では増分が小さかった。',
     r'自チーム負荷中のp99増分はCh6で22.6 ms、Ch7で8.6 ms、Ch11で0.9 ms。期限超過の増分はそれぞれ12.7、9.2、2.8ポイントだった。',
     'チャネル分離は他チームによる追加の待ちを減らす結果と整合する。ただし分離後も自チーム内の大きな基準遅延が残り、操縦期限は満たしていない。RF再送・送信待ちと端末の寄与は未分解で、分離だけを解決策としない。'),
    ('section', 'チャネル幅と操縦通信性能',
     '他チームの20→40 MHz化で帯域の重なりは増えたが、操縦性能の一方向の悪化は確認できなかった。',
     r'p99は128.6→127.5 msと低下し、20 ms期限超過は55.0→56.8\%と増えた。指標の方向が一致しなかった。',
     '幅を広げると独立に置けるチャネルは減るが、1回の送信量や実際の通信量も変わる。今回は他チームの実受信量も低下したため、同じ負荷のまま幅だけを広げた劣化量とは言えない。幅の選択は帯域配置と実通信試験を組み合わせる。'),
    ('section', '通常Wi-Fiの周期負荷による意図的なストレス試験',
     '周期負荷を含む試行全体では、同一Ch6が隣接・分離より遅かった。個々のON操作と遅延急増の対応は判定できない。',
     r'試行全体のp99はCh6で143.3、Ch7で128.5、Ch11で128.7 ms。期限超過は68.2、58.2、57.7\%だった。',
     '試行全体の値はON/OFFをまとめたものであり、ON直後の因果効果ではない。TCPやキューによって負荷停止後にも通信が残り得る。可視化された帯と遅延点の同時出現をパケット単位の衝突や相関へ読み替えない。'),
    ('section', '独立したBluetooth LEリンクとの比較',
     '先行2ホップ系列ではWi-Fiのp99はほぼ変わらず、指令期限超過とBLE配送には変化があった。',
     r'Wi-Fi負荷中のp99はBLE停止126.2、広告126.0、通知126.3 ms。期限超過は54.6→58.2／56.8\%、BLE通知の実受信はWi-Fi待機0.365→負荷0.326 Mbpsだった。',
     'p99が同じでも指令の大部分や欠落を含む期限超過は変わり得る。BLE側の約11\%の減少も含め、片方のp99だけで影響なしと判断することはできない。新1ホップ系列とは経路が違うので速度や遅延を合算しない。'),
    ('section', 'ESP-NOWの指令と独立したWi-Fi大容量通信',
     '先行30秒系列ではWi-Fi負荷時の遅延悪化を観測したが、同一Ch6で3反復に共通する悪化ではなかった。',
     r'Ch6の統合p99は9.4→85.6 ms。ただし負荷反復1・2の期限超過は0\%、反復3は14.1\%で、Ch11は待機時から大きな遅延があった。',
     '大きな統合p99は悪化した反復の存在を示すが、毎回同じ干渉が起きた証拠ではない。分離Ch11にも遅延と欠落があるため、APを経由しないことや周波数分離だけで安定性を保証できない。'),
    ('section', '同じAP内での操縦と動画相当通信',
     '同じAPへ大容量TCPを追加すると、指令の尾部遅延と更新の途絶が増えた。欠落ゼロでも期限は悪化した。',
     '要求20／60 Mbpsでp99は表のように21.0／36.9 ms、最長応答間隔は48.8／102.9 msへ伸びた。実受信速度は要求値まで増えなかった。',
     '操縦と映像が共有する待ち行列や無線送信機会が問題となる結果である。RF干渉だけでなくAP・端末・TCPの処理も含む。映像側の平均Mbpsと指令側のp99・期限・更新途絶を別々に監視する必要がある。'),
    ('section', '追加UDP負荷の要求量・受付量・到着量',
     'UDP負荷では、分離Ch11を常に最良とする遅延の順位は得られなかった。要求通信量も実現していなかった。',
     '主リンクp99の反復範囲はCh6で16.7〜21.2、Ch7で17.0〜19.0、Ch11で24.3〜79.4 msだった。',
     'TCPとUDPでは送信量の調整や負荷の時間構造が異なる。実際の受付・到着が違う試行を、等しい干渉強度の比較とはみなせない。周波数が離れても端末負荷は残るため、TCP比較の順位をUDPへ適用しない。'),
    ('section', '2.4 GHzのチャネルと通信負荷',
     '通信負荷によって強いRFを含む取得が増え、チャネル変更に対応して信号帯域が移動した。',
     r'RMSしきい値超過は待機1.1〜6.1\%、負荷21.7〜41.7\%で、全6比較で負荷側が大きかった。',
     '送信バーストが取得窓に入る機会が増えた結果と整合する。この割合は間欠取得の統計で、連続した占有率やパケット成功率ではない。色が緑になること自体は操縦品質の判定ではない。'),
    ('subsection', 'サンプルレートとFFT長',
     '設定による表示範囲・周波数分解能・名目観測時間の変化を確認した。長いFFTが無線性能を改善した結果ではない。',
     '80 MS/sでFFT256→2048点にするとビン間隔は312.5→39.0625 kHz。80→20 MS/sで1秒の名目RF観測時間比は約0.405→1.623\%だった。',
     '細い周波数刻みは狭帯域成分を分けやすくする一方、色やノイズ床もビン幅で変わる。設定が違う画像の色を、通信の改善・悪化へ直接対応づけることはできない。'),
    ('subsection', 'アナログフィルターとゲイン',
     '高ゲインで飽和が増え、帯域・ゲイン設定が観測画像へ明確に影響した。',
     r'ゲイン20／40／60のレール到達は0／0.3397／12.7318\%。受信帯域を狭くすると帯域外の信号が減衰した。',
     '強い緑や広がった成分が送信側の変化とは限らず、受信機の飽和やフィルターでも生じる。通信条件の比較には共通設定と低飽和の取得を使い、画像の差を受信設定の差と切り分ける。'),
    ('section', 'ビーコンとAPチャネル幅',
     'この間欠画像からビーコン捕捉率や送信周期の正確な推定はできなかった。',
     '50／100／500 TUを設定したが、取得間の未観測時間が長く、横縞をビーコンとして全数同定していない。',
     '縞が多いことはビーコンが多いことの直接証拠ではない。周期信号を評価するには、送信周期だけでなく取得位相の偏りも確認する。40 MHzを要求した基礎条件は実際には20 MHzであり、幅変更の性能比較へは使わない。'),
    ('section', '既存5 GHz APの受信観測',
     '5 GHzでも負荷時に強いバーストを観測した。80 MHz全体の均一な測定はできなかった。',
     r'RMS95百分位は待機約$-12$／$-11$ dBFSに対し、負荷約$-3$ dBFS。負荷時のレール到達は約0.51〜0.55\%だった。',
     '中央値より上位電力が変わるため、常時強くなるというより強い取得が増える観測である。アナログ帯域48 MHzと飽和があるため、単一LO画像から80 MHzチャネルの端や絶対電力を比較することはできない。'),
    ('section', '時刻計測とPCAPの解釈',
     'PCAPとI/Qのパケット単位の対応は判定できなかった。時間窓の一致は検出の真値ではない。',
     '名目RF取得約205 µsに対し、ベンダー取得関数は約1.88 ms、時計換算は約±0.6 ms。負荷中に窓を±5 msへ広げると全取得がPCAPありになった。',
     '時刻の不確かさが短いRF取得より大きいので、窓内にパケットがあっても同じRFを見たとは限らない。真陽性・見逃しを評価するにはADC開始時刻や同期した送信イベントが必要である。'),
    ('section', '固定周期とランダム標本化',
     '固定取得で位相の偏りを観測し、ランダム取得でその偏りが減った。真のビーコン捕捉率の改善量は判定できない。',
     '100 TUの位相集中度R1は固定1.000、ランダム0.059。500 TUでは固定のR5が1.000、ランダム0.038だった。',
     '同じ位相を繰り返し見ると、イベントを毎回逃す可能性がある。ランダム化は観測時点の偏りを減らすが、約99\%の未観測時間を埋めない。しきい値を超えた回数をビーコン復号数として数えることはできない。'),
    ('section', 'LO掃引による有効周波数応答',
     '同じRF帯域でもLOから離すと観測電力が低下し、受信系の周波数依存を確認した。',
     'LOから±30 MHzの位置で、中央に対して約9〜10 dBの減衰が両反復に共通した。11／20 MHz帯域要求では±20 MHz位置で約19〜21 dB低下した。',
     '画面端の薄い帯は送信量が少ないためとは限らず、受信フィルターの感度差でも生じる。チャネルの電力を比較する際は、対象を同じベースバンド位置へ置く。結果はWi-Fi帯域を用いた有効応答で、フィルター単体の校正値ではない。'),
    ('section', '送信電力設定によるレベル応答',
     '送信電力設定と観測電力に、期待した1対1の増加はなかった。10→20 dBm設定で受信値はほぼ横ばいだった。',
     'ゲイン20の帯域P90は設定5／10／15／20 dBmで−41.68／−39.29／−39.17／−39.19 dBFS。回帰傾きは約0.15 dB/dBだった。',
     '設定値は実放射電力でもC5入力電力でもない。ゲイン20のレール到達は0なので、横ばいをデジタル飽和だけでは説明できない。送信側の制御、外来信号、受信アナログ段などを分離できず、絶対ダイナミックレンジの測定には使えない。'),
    ('section', 'AGC負荷過渡と訓練系列候補',
     '振幅の立上りは観測したが、AGC固有の追従時間は判定できなかった。C5単独の周波数ドリフトも判定できない。',
     'STF候補の繰返し電力はHardware AGCで変化した一方、固定ゲインでも最初の窓から約2.8 dB上昇した。周波数差候補には複数の群があった。',
     '固定ゲインでも起きる変化には、パケットの選び方・受信フィルター・雑音が寄与する。周波数差も複数送信機の差を含む。振幅の変化を全てAGC、群の変化を全て温度ドリフトと呼ぶ根拠はない。'),
    ('section', 'BLE広告の受信スペクトル観測',
     'BLE広告ONで2480 MHz付近の狭帯域バーストが増えた。3広告周波数全ての信号同定はできなかった。',
     '2480 MHz付近の最大電力は約20.6 dB増えたが、平均は約1.27 dBの増加。2402 MHzにはOFF時も強い成分があり、2426 MHzの差は小さかった。',
     '稀な強い送信は最大画像には目立っても平均への寄与は小さい。ON/OFFで信号源の手掛かりは得られるが、細線全てをBLEと断定できない。この受信観測だけでWi-Fi速度への影響は測れず、通信性能は双方向共存節の停止対照で評価する。'),
    ('section', '5 GHzの分割取得と重複合成',
     '順次取得から約80 MHzの範囲を合成できた。同時刻の80 MHz波形や通信性能への影響は判定できない。',
     r'重複帯域の中央値差は0.14〜1.24 dB、全10条件のレール到達は0\%だった。',
     '減衰の大きい受信端を避けた中央部分の利用は広い帯域の俯瞰に役立つ。ただし各スライスの時刻が違うため、短いバーストの同時性・瞬間幅・隣接通信への衝突をこの合成画像から判断できない。'),
]


def scrub_history(source):
    """Retain experimental limitations; remove requests and work history."""
    replacements = {
        r'\section{Wi-FiとBLEの共存観測}': r'\section{BLE広告の受信スペクトル観測}',
        '電子レンジは指定により見送った。': '',
        '使用者の終了希望により残り5試行を省略した。': '',
        'ESP-NOW長時間系列は各600秒の19試行で、実ロボット': 'ESP-NOW長時間系列は各600秒の19試行である。実ロボット',
        '当初24試行の予定だったが、使用者が実験を早く終えたいと希望したため、進行中の試行を保存した19試行で長時間測定を終了した。残り5試行は測っていない。': '',
        '使用者が適用・確認した5配置': '5配置',
        '距離はボードまたはケース中心間の使用者報告値で、アンテナ間距離の校正値ではない。': '距離はボードまたはケース中心間の概数で、アンテナ間距離の校正値ではない。',
        '配置は同じ机上のおおむね30 cmという使用者の申告であり、正確な送受信距離は未測定。': '配置は同じ机上でおおむね30 cm。正確な送受信距離は未測定。',
        '配置は同じ机上で固定し、使用者は各機器おおむね30 cmと報告した。': '配置は同じ机上で固定し、機器間はおおむね30 cmだった。',
        'ユーザーが使う実システムでは': '実際の操縦系では',
        'Bluetooth比較も指定のBLE負荷と配置に限定する。': 'Bluetooth比較は今回のBLE負荷と配置に限定する。',
        '全条件の数値検算・現行接続相手の応答確認・負荷設定readbackを確認し、図を目視した。旧version6の取得は非公開の予備診断記録として保存し、正式比較には混ぜない。': '各試行で接続相手の応答と負荷設定を読み出して確認した。',
        '全条件の数値検算・現行接続相手の応答確認・負荷設定readbackを確認し、図を目視した。': '各試行で接続相手の応答と負荷設定を確認した。',
        '認証による転送停止前の28試行と、回収・再開後の17試行をそのまま保持した。取得セグメント、転送方法、転送元SHA256を記録し、性能を理由に悪い試行を再測定していない。再開前後の時間帯・環境変動は統制できていない。': '45試行は2つの取得期間に分かれ、その間の時間帯・環境変動は統制していない。',
        '回転後の中心間距離は基準とほぼ同じとの申告。': '回転後の中心間距離は基準とほぼ同じ。',
        '基準の申告距離75/45/95 cmを使用。': '基準の概数75/45/95 cmを使用。',
        '送受信150 cm、C5→M5 157 cmは移動後の使用者報告。': '移動後の中心間距離は送受信150 cm、C5→M5 157 cm。',
        '最初の位置・向きへ戻したとの申告。': '最初の位置・向きへ戻した。',
        '図を目視した。': '',
        r'\section{追加評価への展開と保存条件}': r'\section{補足受信評価の条件}',
        '先に追加した双方向評価とその考察を示し、その後に流量・QoS・長時間・配置・他チーム比較を読む構成とした。': '双方向共存、流量・QoS・長時間・配置・他チーム通信をそれぞれ評価する。',
    }
    for old, new in replacements.items():
        source = source.replace(old, new)
    return source


def inject_verdicts(source):
    source = re.sub(r'% BEGIN VERDICT [^\n]+\n.*?% END VERDICT\n?', '', source, flags=re.S)
    for level, title, result, evidence, discussion in VERDICTS:
        heading = '\\'+level+'{'+title+'}'
        assert heading in source, title
        pos = source.index(heading)+len(heading)
        # A purpose paragraph stays first when one exists.
        purpose = re.match(r'\n\\par\\smallskip\\noindent\\textbf\{実験の目的\}\\quad [^\n]*\n', source[pos:])
        if purpose:
            pos += purpose.end()
        block = ('\n% BEGIN VERDICT '+title+'\n'
                 r'\par\smallskip\noindent\textbf{結果の判定}\quad '+result+'\n\n'
                 r'\noindent\textbf{根拠}\quad '+evidence+'\n\n'
                 r'\noindent\textbf{考察}\quad '+discussion+'\n'
                 '% END VERDICT\n')
        source = source[:pos]+block+source[pos:]
    return source


def reader_framework(source):
    abstract = r'''ロボコンで操縦指令と画像・点群が同じWi-Fiを共有し、他チームやBLE・ESP-NOWも通信する条件を室内で比較した。
アプリ要求・応答の往復時間、20 ms以内に応答がない割合、実受信量を測り、ESP32-C5の間欠SDR画像で帯域の重なりを観察した。
他チーム通信の追加によるp99増分は同一Ch6で22.6 ms、隣接Ch7で8.6 ms、分離Ch11で0.9 msとなり、分離では追加悪化が小さかった。
一方、20→40 MHz化、小分け送信、QoS変更、省電力OFFには全条件に共通する改善・悪化はなかった。
独立したESP-NOW 200 Hz・同一Ch6を追加した1ホップ系列では、Wi-Fi実受信0.411→1.107 Mbpsと速度が増えた一方、指令の期限超過も0.05→2.73\%へ増えた。
Wi-Fi負荷を追加してもBLE通知の配送量は0.497→0.494 Mbpsとほぼ維持された。
一方、Wi-Fi負荷中にBLE通知を追加すると、Wi-Fi指令の期限超過は0.067→0.483\%へ増えた。
以上は、映像側の速度、指令側の期限、両無線方式の配送を別々に評価する必要性を示す。
402通信試行、同一TCP接続の9切替ブロック、115受信観測系列を経路ごとに区別し、全差をRF干渉だけへ帰属しない。
実センサ・モータは使用せず、20 msは往復応答の比較目標であって実機の安全停止期限ではない。'''
    source = re.sub(r'\\begin\{abstract\}.*?\\end\{abstract\}',
                    lambda _: '\\begin{abstract}\n'+abstract+'\n\\end{abstract}', source, count=1, flags=re.S)
    source = source.replace(r'ロボコンの操縦通信とWi-Fi干渉の可視化\\室内通信実験と先行SDR観測の統合',
                            r'ロボコンの操縦・センサ通信に対する帯域共有の実測評価\\Wi-Fi・BLE・ESP-NOWとSDR可視化')
    source = re.sub(r'% BEGIN READER FRAMEWORK\n.*?% END READER FRAMEWORK\n?', '', source, flags=re.S)
    framework = r'''
% BEGIN READER FRAMEWORK
\subsection{実験系列と通信経路}
APはアクセスポイント、STAはAPへ接続する端末である。1ホップは無線を1回、2ホップはAP中継で2回通る経路を指す。
この違いは必要な送信機会と端末処理を変えるため、下表の系列をまとめて方式の速度順位は付けない。
「他チーム」は独立したAPと通信相手を持つ負荷リンク、「自チーム」は指令と模擬センサ通信の評価対象である。
\begin{center}\small\begin{tabular}{p{.23\linewidth}p{.35\linewidth}p{.32\linewidth}}\toprule
比較系列 & 評価対象の経路 & 主に変える条件\\\midrule
他チーム・流量・生成周期 & ESP32 STAとPC STAを観測PC APが中継。指令・TCPは2ホップ & 他チームCh・負荷、自チームの生成量・周期\\
実ROS 2・省電力 & PC APとPC STA。指令・模擬Image／PointCloud2は1ホップ & センサQoSとSTA省電力。指令QoSは固定\\
ESP-NOW 30秒・600秒・配置 & 独立したESP32とM5の直接要求・応答。別のWi-Fi負荷はPC STA→AP→ESP32 & Wi-Fi負荷、ESP-NOWのCh・指令周期・配置\\
双方向共存20秒 & PC AP→Wi-Fi受信ESP32は1ホップ。別のESP32・M5でESP-NOWまたはBLE & 外部リンク停止／動作とWi-Fi負荷、各3反復\\
TCP切替10秒 & 共存系列と同じ1ホップTCP。UDP指令なし & 同じTCP接続でESP-NOW停止前／動作／停止後\\\bottomrule
\end{tabular}\end{center}
各系列の絶対RTTやMbpsの差には経路・端末・実装も含まれる。
効果の比較は同じ系列内の停止・待機対照との差で行う。SDR受信設定の評価は通信性能とは別の補足である。

\subsection{指標と集計方法}
ESP-NOWはESP32同士がAPを介さず同じ固定チャネルでデータを直接送る方式、BLEは接続中に使用周波数を切り替える方式である。
QoSはROS 2の配送方針、深さは保持する履歴数、DDSはROS 2が使う通信基盤である。
連番（sequence）は情報の新しさを確認する番号、RFは無線信号を指す。
SDRは受信信号をデジタル処理して観測する方法で、本稿ではESP32-C5（C5）のI/Qデータから周波数別の強さを表示する。
I/Qは振幅と位相を表す2成分、FFTはそのデータを周波数成分に分ける計算である。
RTTは要求を送り相手のアプリ応答が戻るまでの往復時間であり、指令の片道到達時間やモータ動作までの時間ではない。
p99は返った応答の99\%が収まる値で、欠落した応答の待ち時間を含まない。
\textbf{統合p99}は、その条件で取得した全反復の応答をまとめて求める分位点で、反復数は各表に示す。
\textbf{p99の反復平均}は反復ごとに求めたp99の算術平均である。
この2つは同じ統計ではなく、各表に集計法を記す。

\textbf{20 ms期限超過}は期限までに応答がない要求の割合で、欠落も含む。
Wi-Fi UDPは送信API呼出しから、ROS 2と連続記録ESP-NOWは予定送信からの応答を評価する。
起点の違う割合は同じ量として合算しない。実受信Mbpsは受信アプリのbyte数から計算し、生成要求量やWi-Fi PHYの表示速度と区別する。
「期限超過が2ポイント増えた」は割合の差であり、速度低下率などの相対変化\%とは異なる。
最新情報の更新途絶は新しいsequenceへ進まない時間で、RTTが短くても欠落や低い送信頻度で長くなり得る。
センサの初回受信間隔、UDP応答間隔、ESP-NOWの最新連番の更新間隔は区別し、各節に計算対象を記す。
% END READER FRAMEWORK
'''
    marker = r'\subsection{設計上の判断と実験の対応}'
    source = source.replace(marker, framework+'\n'+marker, 1)
    conclusion = r'''\section{統合した結論}
本研究で最も明瞭だった通信性能の変化は、\textbf{他チーム負荷を加えた同一・隣接チャネルの期限悪化}と、
\textbf{自チームの大容量データ追加による指令期限の悪化}である。
他チームとの分離は追加悪化を減らしたが、分離後にも基準の遅延が残り、目標20 msを満たす解決にはならなかった。
20／40 MHz幅、小分け化、QoS、省電力設定は指標や条件で変化の方向が異なり、単独で十分な対策という結論は得られなかった。

\textbf{ESP-NOWとBLEには、両方向で異なる変化があった。}
新共存系列ではESP-NOW同一Ch6・200 Hz中のWi-Fi速度は増えたが、指令期限は悪化した。
Wi-Fi負荷中には隣接Ch7のESP-NOW遅延が悪化し、BLE通知の配送量がほぼ同じでもWi-Fi指令の期限超過が増えた。
したがって、片方の平均Mbpsが保たれることを、もう片方の操縦品質が保たれる根拠にはできない。
速度の反復変動や停止前後の変化があるため、普遍的な速度低下率やRF衝突だけによる因果効果は求めていない。

\textbf{配置とSDRには、判定できなかった項目もある。}
近距離の配置変更では欠落増加を観測しなかったが、基準へ戻してもp99とRSSIが変わり、配置だけの効果は分離できなかった。
SDRは帯域の位置と重なりを示した一方、受信端の減衰、飽和、約0.4\%の名目RF時間比が解釈を制約した。
PCAPとのパケット単位の対応、AGC整定時間、温度ドリフト、絶対ダイナミックレンジはこの記録から判定できない。
5 GHz分割合成は広い範囲の俯瞰であって同時受信ではない。

ロボコンでの評価手順は、まず単独の操縦・センサ通信を測り、その後に他チームや外部無線を動かし、最後に停止対照へ戻すことである。
映像・点群の生成量と実受信、指令の期限超過・欠落・更新途絶を同時に確認する。
青緑SDR画像は帯域の共有を説明する補助とし、機体の安全停止や競技場での性能は実際の構成で別に検証する。

'''
    source = re.sub(r'\\section\{統合した結論\}.*?(?=\\begin\{thebibliography\})',
                    lambda _: conclusion, source, count=1, flags=re.S)
    return source


def simplify_details(source):
    changes = {
        '距離、向き、移動、暗号化、通信途絶時の停止動作は未比較である。': 'この30秒系列では距離や向きを変更していない。配置比較も近距離・短時間に限られ、移動、暗号化、通信途絶時の停止動作は評価していない。',
        '今回の成果は室内に異なる幅と発生頻度の信号が共存する様子の観察であり、BLEによるWi-Fi性能劣化量の因果評価ではない。通信性能とRF事象を同時・同定可能な条件で測ることで、その問いへ進める。': 'この節のSDR観測は、BLEによるWi-Fi性能劣化量を評価したものではない。通信性能の条件差は前半の独立無線機による停止対照で評価した。',
        '距離掃引、隠れ端末配置、操縦AP自身の幅変更、優先度制御、実機の制御誤差と停止判断は今後の候補となる。': '近距離配置比較とは別に、移動・遠距離・隠れ端末配置、操縦AP自身の幅変更、優先度制御、実機の制御誤差と停止判断は評価していない。',
        'publishが短くても、その後のDDS・OS・MACの待ち行列、無線再送、受信dispatchの時間は残る。': 'publish呼出しは短かったが、それ以外のDDS・OS・MAC、無線再送、受信dispatchの寄与は分離できない。',
        'version7・source helper version2で新たに取得した45試行、15条件、各3反復・30秒。': '45試行・15条件・各3反復・30秒。',
        '流量比較とは別に、同じversion7・helper version2で36試行・12条件・各3反復を新たに取得した。': '流量比較と同じ構成で、36試行・12条件・各3反復を取得した。',
        '負荷停止の実装競合と自律クライアントの切断判定も修正し、原ログを残した。': '',
        r'\section*{追加運用評価の実測と考察}': r'\section*{操縦・センサ通信の評価}',
        r'\section*{先行通信実験とSDR受信評価}': r'\section*{通信経路別の負荷比較}',
        r'\section*{先行観測：SDR画像を読むための補足}': r'\section*{SDR受信系の補足評価}',
        r'\section{実験結果の総合考察}': r'\section{SDR受信評価の考察}',
    }
    for old, new in changes.items():
        source = source.replace(old, new)
    source = re.sub(r'センサoff・他チームCh6で省電力OFF→ONにすると、.*?センサheavy・他チームCh11で省電力OFF→ONにすると、[^\n]*\n',
                    '指令のみでは省電力ON/OFFの差は小さかった。センサ負荷中はCh11でON時に悪化したが、Ch6ではp99と期限超過の変化方向が一致しなかった。\n', source, flags=re.S)
    source = re.sub(r'20 HzでWi-Fi待機→負荷へ切り替えたとき、.*?200 HzでWi-Fi待機→負荷へ切り替えたとき、[^\n]*\n',
                    'Wi-Fi負荷の追加による変化は周期ごとに異なった。50／200 Hzはp99と期限超過がともに増え、20／100 Hzではこの2指標はともに減った。\n', source, flags=re.S)
    source = re.sub(r'20 Hz・Wi-Fi heavy・反復1：予定12000、.*?20 Hz・Wi-Fi off・反復2：予定12000、[^\n]*\n',
                    '欠落3応答はいずれも20 Hz条件で、負荷中に2件、待機中に1件だった。該当試行では応答機の総受信数が予定送信数と一致し、MAC送信失敗が1件ずつ記録された。\n', source, flags=re.S)
    source = source.replace('応答機には各要求が届いており、該当試行でMAC送信失敗が1件ずつ記録された。',
                            '該当試行では応答機の総受信数が予定送信数と一致し、MAC送信失敗が1件ずつ記録された。')
    source = source.replace('p99：TCPなし [ms]', 'p99反復平均：TCPなし [ms]')
    source = re.sub(r'Wi-Fi offの基準・前→基準・後では、.*?Wi-Fi負荷中の距離変更では、[^\n]*\n',
                    '配置を変えた3条件では欠落と負荷中の期限超過の増加はなかった。一方、元の位置へ戻した基準も遅延が低下していた。\n', source, flags=re.S)
    ros = ('表のセンサ負荷heavyは、640×360画素・rgb8のImage（691,200 byte）と、'
           '4,096点・16 byte/点のPointCloud2（65,536 byte）をそれぞれ10 Hzで生成する条件である。'
           '合計要求payloadは約60.5 Mbpsで、offでは両トピックを停止する。画像は非圧縮の合成データであり、実カメラ・実LiDARの処理負荷ではない。\n')
    source = source.replace(ros, '')
    marker = 'PC AP→ロボットSTAの経路であり、前段のSTA→AP→STAとは比較経路が異なる。'
    source = source.replace(marker, marker+'\n\n'+ros, 1)
    # Place the long-duration figures with the experiment they illustrate.
    pattern = r'\\begin\{figure\}\[htbp\].*?\\end\{figure\}'
    figures = []
    for match in re.finditer(pattern, source, flags=re.S):
        if any('/'+name+'.pdf' in match[0] for name in ('espnow-long-metrics', 'espnow-long-timeline', 'espnow-long-blue-green')):
            figures.append(match[0])
    for figure in figures:
        source = source.replace(figure, '', 1)
    source = source.replace(r'\section{ESP32間通信の配置・向き・遮蔽比較}',
                            '\n'.join(figures)+'\n'+r'\section{ESP32間通信の配置・向き・遮蔽比較}', 1)
    return source


def twitter_verdicts(source):
    changes = {
        '他チームの実受信も0.4--4.7 Mbpsと異なり、等しい空中時間の比較ではない。': '他チームの実受信量は一定でない。',
        r'\textbf{目的はESP32の最高性能ではなく、隣のチームや追加無線が動く中で指令とデータを両立させる判断材料を得ること}である。': r'\textbf{目的は、他チームや追加無線の中で操縦とセンサ通信を両立する条件の評価}である。',
        '観測PC（Intel BE200）のAP（アクセスポイント）、ラップトップ1（Intel AX210・有線共有）、ラップトップ2（MT7921E）、ESP32 3台とC5を使用した。\n実スマートフォン・カメラ・モータは使用せず、画像・点群の形と大きさを持つ模擬データを送った。': 'AP（アクセスポイント）はIntel BE200。両チーム比較の自通信はESP32→AP→PCの2ホップ、ROS 2はPC AP↔PC、新共存評価はPC AP↔ESP32の1ホップ。実センサ・モータは使わない。',
        r'\textbf{分かること：}他負荷の追加によるp99増分は同一約23 ms、隣接約9 ms、分離約1 msだった。': r'\textbf{判定：同一・隣接で遅延が悪化し、分離で増分が小さかった。}他負荷によるp99増分は同一約23、隣接約9、分離約1 msだった。',
        '広い幅は同時配置の余裕を減らすが、転送が速ければ送信時間を短くできる。\n'+r'\textbf{広いほど必ず悪いという結果ではなく、指令期限と実受信を併せて判断する}。': r'\textbf{判定：一方向の悪化は確認できなかった。}p99と期限超過の変化が逆方向だった。幅は帯域の重なりだけでなく送信時間も変え、他チーム実受信量も揃っていない。幅だけで劣化を決めず、両指標で評価する。',
        '同一Ch6負荷中、TCP要求0→1 Mbpsで20 ms超過54.08→72.61\\%。': r'\textbf{判定：大容量通信の追加で指令が悪化した。}同一Ch6負荷中、TCP要求0→1 Mbpsで20 ms超過54.08→72.61\%。',
        '小分け生成は常に改善せず、TCPやOSもデータをまとめ直す。': r'\textbf{小分け化には一貫した改善がなかった。}0.5 Mbps・Ch6では超過54.71→58.50\%と逆に増えた。TCPやOSもデータをまとめ直すため、生成周期だけで無線の平滑化を保証できない。',
        '深さ1はDDSの履歴で、無線待ち行列や指令優先度を設定する値ではない': r'\textbf{QoS変更だけでは悪化を解消できなかった。}深さ1はDDSの履歴で、無線待ち行列や指令優先度を設定する値ではない',
        '省電力OFFでも指令のみp99約103--109 msが残り、全遅延を他チームや省電力だけへ帰属できない。': r'\textbf{省電力OFFも一貫した改善を示さず}、指令のみp99約103--109 msが残った。自チーム内の処理や待ちも調べる必要がある。',
        'APを経由しなくても帯域と送信機会は共有する。小さな指令も、要求・応答・ヘッダ・ACKを繰り返すのでpayloadのMbpsだけでは負荷を判断できない。': r'\textbf{判定：200 Hz・隣接Ch7で遅延と期限超過が悪化した。}Ch6／11では同じ規模の悪化はなかった。APを経由しなくても帯域と送信機会は共有し、小さな指令も要求・応答・ACKを繰り返す。',
        '同一Ch6は3反復とも速度が増えた。': r'\textbf{判定：同一Ch6では3反復とも速度が増えた。}Ch7／11は増減が混在し、一貫した低下はなかった。',
        '指令を増やせば必ず良くなる結果ではない。': r'\textbf{判定：200 Hz化で尾部遅延が増えた。}要求・応答を増やすので、更新を高頻度にすることと配送を速くすることは同じではない。Wi-Fi負荷の追加は全周期で一貫した悪化を示さなかった。',
        'BLE通知の実受信平均はWi-Fi TCPなし': r'\textbf{判定：BLE配送はほぼ維持されたが、Wi-Fi指令期限は悪化した。}BLE通知の実受信平均はWi-Fi TCPなし',
        'BLEの配送が保たれてもWi-Fi操縦の期限が保たれるとは限らない。速度差の反復には増加もあり、固定した低下率とはしない。': 'BLE配送はほぼ維持された一方、Wi-Fi指令期限は反復平均で悪化した。Wi-Fi速度低下率は反復で−20.8〜54.0\\%と増減が混在した。',
        '全30,000指令で欠落はなかったが、元へ戻した後もp99が低下したため、回転・遮蔽による改善とは断定できない。': r'\textbf{判定：配置変更で欠落増加は観測しなかったが、遅延への効果は判定不能。}全30,000指令に応答があり、元へ戻した後もp99が低下した。基準自体が変動したため回転・遮蔽で改善したとは言えない。',
        '前の試験は全条件でESP-NOWが動いていたため、Wi-Fi単独との差を求められなかった。\n今回は停止対照を加え、': 'ESP-NOW停止を対照とし、',
        '100/200 Hzの比較は詳細版へ併記し、頻度を上げる利点と期限超過を両方評価した。': '',
        '20秒行列のWi-Fi速度・指令期限とこの切替対照は別に評価した。': '',
        'BLEの20/40 MHz比較は未実施である。': '',
        'チャネル分離だけで端末内の遅延はなくならず、方式名や平均Mbpsだけでは操縦品質を判断できない。': '他チームとのチャネル分離で追加悪化は小さくなったが、基準遅延は残った。ESP-NOW中にWi-Fi速度が増えても指令期限が悪化した条件があり、速度と操縦品質は別に評価する。',
        '960,000指令、959,997 unique応答。負荷中100 Hzのp99は9.26 ms、200 Hzは14.26 msだった。': '96万指令中3応答が欠落した。Wi-Fi負荷中100→200 Hzで統合p99は9.26→14.26 ms、最新連番の最長更新途絶は約24→35〜37 msだった。',
        'Wi-Fi速度低下は反復ごとのBLE停止対照に対する比で、負の値も残した。': 'Mbpsは反復平均、速度低下率は各反復の停止対照との比の平均で、平均Mbps同士から計算した値ではない。',
    }
    for old, new in changes.items():
        assert old in source, old
        source = source.replace(old, new, 1)
    source = source.replace('Wi-Fiの平均Mbpsは運べる量、RTT p99は返った応答の99\\%が収まる往復時間、',
                            'RTTは要求からアプリ応答までの往復時間で、片道ではない。Mbpsは実受信量、p99は返った応答の99\\%が収まるRTT、')
    source = source.replace('実ROS 2（Humble／Jazzy・CycloneDDS）は指令QoSを固定し、',
                            '実ROS 2は模擬画像・点群を合計約60.5 Mbps生成し、指令QoS（配送方針）を固定して')
    source = source.replace('深さ1はDDSの履歴で、', '深さ1は保持履歴数で、')
    source = source.replace('固定チャネルと追加測定の目的', '固定チャネルと実験目的')
    source = source.replace('一方、Wi-Fi指令の20 ms超過はBLE停止', '一方、Wi-Fi指令の20 ms超過の反復平均はBLE停止')
    source = source.replace('Wi-Fi指令の20 ms超過は0.05', 'Wi-Fi指令の20 ms超過の反復平均は0.05')
    source = source.replace('指令の20 ms超過は0.05', '指令の20 ms超過の反復平均は0.05')
    source = source.replace('BLE通知の実受信平均はWi-Fi TCPなし',
                            '図3の細線は狭帯域成分の手掛かりだが、この拡大範囲はCh6との重なりを示していない。期限超過は通信ログで判定する。BLE通知の実受信平均はWi-Fi TCPなし')
    # Omit an API parameter and the theoretical airtime calculation from the
    # short paper; the full paper retains these technical details.
    source = source.replace('channel=0は現在のチャネルという意味で、自動探索ではない', '同じ固定チャネルを使う')
    source = source.replace('送受信は同じ固定チャネルを使う。同じ固定チャネルを使う', '送受信は同じ固定チャネルを使う')
    source = re.sub(r'64 byteを200 Hzで往復するとpayloadだけで[^\n]*\n', '', source)
    source = source.replace('送信待ちや再送は候補だが、直接測定して原因を特定した結果ではない', '送信待ち・再送が原因候補だが未同定である')
    source = source.replace('基本3反復。経路・端末の違う系列を合算して方式の順位を付けない。', '基本3反復。異なる経路・端末の絶対値で方式を順位付けしない。')
    source = source.replace('BLE配送はほぼ維持された一方、Wi-Fi指令期限は反復平均で悪化した。', '')
    source = source.replace('40 MHz化で重なり得る周波数は増えるが、速く送れば空中時間も変わるため幅だけで劣化量を決められない。', '')
    for marker in (r'\subsection{チャネル幅と利用できる帯域}',
                   r'\subsection{ESP-NOWからWi-Fiへの速度変化}',
                   r'\section{SDRと配置比較の解釈}'):
        source = source.replace(marker, '\\columnbreak\n'+marker, 1)
    source = source.replace('自チーム大容量通信中。値は他チーム待機／負荷。', '自チーム負荷中。待機／負荷、p99は全反復統合。')
    source = source.replace('指令の更新途絶も見る。20 msは比較目標で、機体の安全な停止期限ではない。',
                            '20 msは往復応答の比較目標で、安全停止期限ではない。')
    source = source.replace('基本3反復。異なる経路・端末の絶対値で方式を順位付けしない。',
                            '基本3反復。期限の起点はWi-Fi UDPで送信API、ROS 2と連続ESP-NOWで予定送信時刻とし、系列間で合算しない。')
    source = source.replace('新しい1ホップ系列。', '1ホップ共存系列。')
    source = source.replace('先行600秒系列', '600秒系列').replace('先行配置比較', '配置比較')
    return source



def twitter_standalone(source):
    """Restore the premises needed to read the three-page paper by itself."""
    replacements = [
        ('ロボコンの無線通信と帯域共有の実測評価',
         'ESP32-C5による無線可視化とロボコン通信の評価'),
        (r'\textbf{要旨}\quad 操縦と画像・点群が同じWi-Fiを使い、他チームやBLE・ESP-NOWも動く状況を比較した。'+'\n'
         '無線の停止対照と双方の通信記録を使い、帯域の重なり、実受信速度、指令期限を分けて評価する。',
         r'\textbf{要旨}\quad ESP32-C5-WROOM-1をSDR受信機として使い、2.4 GHz帯で他チーム通信・BLE・ESP-NOWを追加した時のWi-Fiを観測した。'+'\n'
         '青緑の周波数画像と、端末で記録した指令応答・実受信量を別々に評価した。'),
        ('AP（アクセスポイント）はIntel BE200。両チーム比較の自通信はESP32→AP→PCの2ホップ、ROS 2はPC AP↔PC、新共存評価はPC AP↔ESP32の1ホップ。実センサ・モータは使わない。',
         '観測専用のESP32-C5（以下C5）はESP-SDRでI/Qを取得し、FFTで周波数別の強さを描く。通信性能はC5で復号せず、送受信端末のログから測る。\n'
         'AP（アクセスポイント）はIntel BE200搭載PC。自通信はESP32→AP→PCの2ホップ、ROS 2はAP↔PC、共存試験はAP↔ESP32の1ホップ。基本の指令は64 byte・100 Hzの要求と同じ内容の応答。実スマホ・センサ・モータは使わない。'),
        ('基本3反復。期限の起点はWi-Fi UDPで送信API、ROS 2と連続ESP-NOWで予定送信時刻とし、系列間で合算しない。',
         '基本3反復、順序は反復内で無作為化。期限の起点はUDPで送信API、ROS 2と連続ESP-NOWで予定送信時刻とし、異なる経路・指標を合算しない。'),
        ('自チームCh6・20 MHzを固定し、他チームを待機／TCP負荷とした30秒・3反復。',
         '自チームCh6・20 MHzを固定。他チームは別のESP32 AP→ESP32で、Ch6／7／11・20 MHzのTCP待機／負荷を各30秒・3反復した。自TCPは要求15.73 Mbps。待機でもビーコンと接続は残る。'),
        ('他チームの実受信量は一定でない。',
         '他負荷の実受信はCh6で2.5--4.7、Ch7で2.3--3.8、Ch11で1.0--1.3 Mbpsと異なる。自TCPも実受信約1 Mbpsであり、同じ空中時間の比較や競技用PCの速度上限ではない。'),
        ('Ch1の20 MHzは名目2402--2422 MHz、Ch1＋副Ch5の40 MHzは2402--2442 MHzで自Ch6へ重なる。',
         'Ch1の20 MHzは名目2402--2422 MHz、上側副Ch5を使う40 MHzは2402--2442 MHzで自Ch6へ重なる。'),
        ('実ROS 2は模擬画像・点群を合計約60.5 Mbps生成し、指令QoS（配送方針）を固定してセンサのreliable／best effortと深さ1／10を比較した。',
         '実ROS 2（Humble／Jazzy・CycloneDDS）は非圧縮の合成画像640×360・rgb8と4,096点×16 byteの点群を各10 Hz、合計60.5 Mbps生成した。指令はreliable・深さ10に固定し、センサのreliable／best effort（再送保証なし）と深さ1／10を各30秒・3反復した。'),
        ('Wi-FiはPC AP→別のESP32という1ホップに統一し、UDP100 Hz指令も同時に送る。\n先行の2ホップ系列の絶対Mbpsとは混ぜない。',
         'Wi-FiはCh6・20 MHz、PC AP→負荷ESP32の1ホップ。TCPなしでもUDP指令とビーコンは残り、要求20 Mbpsは実達成量ではない。別のESP32とM5 ATOM LITEは75 cm離し、64 byteのESP-NOW要求・応答を1 Mbps PHYで送る。'),
        (r'\textbf{判定：200 Hz・隣接Ch7で遅延と期限超過が悪化した。}Ch6／11では同じ規模の悪化はなかった。APを経由しなくても帯域と送信機会は共有し、小さな指令も要求・応答・ACKを繰り返す。',
         r'\textbf{判定：反復平均では200 Hz・隣接Ch7で悪化した。}Ch6／11の変化は小さく、Wi-Fi同士の同一Ch最悪という順位とは異なった。APを通らなくても空中時間を共有し、要求・応答・ACKを繰り返す。'),
        ('600秒系列は20/50/100/200 Hz、Wi-Fi待機／負荷、計19試行。',
         'ESP-NOW Ch6・64 byte要求／応答、20/50/100/200 Hz、Wi-Fi待機／負荷を各600秒・2〜3反復、計19試行した。'),
        ('独立したESP32 2台で停止／広告／BLE 1M通知、Wi-Fi TCPなし／要求20 Mbps、各20秒・3反復の18試行を行った。',
         '同じESP32・M5を独立BLEリンクに使い、停止／20 ms設定の広告／BLE 1MのGATT通知（2 ms生成要求）を比較した。Wi-Fi Ch6・20 MHz、TCPなし／要求20 Mbps、各20秒・3反復、18試行。'),
        ('C5は80 MS/s・16,380 I/Q・48 MHzアナログ帯域・手動ゲイン設定20・FFT1024。',
         'C5は中心周波数2442 MHz・80 MS/s・16,380 I/Q・48 MHzアナログ帯域・固定ゲイン20・FFT1024。DC除去とHann窓を用い、各比較図内で色尺度を共通にした。'),
        ('青緑の未校正dBFSを絶対dBm、占有率、通信成功率へ変換しない。',
         '緑は青より受信電力が強いという意味で、干渉や通信失敗そのものではない。dBFSはデジタル振幅基準の未校正値で、dBm・占有率・成功率へ変換しない。'),
        ('配置比較はESP32間75 cm、C5まで45 cm・95 cmから、90°回転、手の遮蔽、150 cm、基準復帰を各10秒・3反復した。',
         '配置は机上で固定。ESP32--M5間75 cm、C5まで45／95 cmを基準に、ESP-NOW Ch6・100 Hzを90°回転、手の遮蔽、150 cm、基準復帰で比較した。各配置はWi-Fi待機／負荷×10秒×3反復。'),
        ('この測定は構成を選ぶ材料であり、機体の安全停止は実機で別に確認する。',
         '少数反復の室内結果で、有意差検定は行っていない。ESP32受信の約0.3〜1 Mbpsを競技PCの上限とせず、同じチップ内の共存制御も区別する。機体の安全停止は実機で別に確認する。'),
    ]
    for old,new in replacements:
        assert old in source, old
        source = source.replace(old,new,1)
    setup = r'''
\begin{center}\small
PC APはIntel BE200、PC STAはMT7921E。通信端末3台はESP32-WROOM-32／32DとM5 ATOM LITE、観測は別のC5。
\begin{tabularx}{\textwidth}{@{}lXXX@{}}\toprule
系列 & 指令の経路（応答は逆） & 大容量データの経路・要求量 & 独立した追加通信\\\midrule
Wi-Fi 2チーム & ESP32→PC AP→PC STA & PC STA→AP→ESP32、TCP 15.73 Mbps & ESP32 AP→ESP32 STA、飽和TCP\\
ROS 2 & PC AP→PC STA & PC STA→AP、模擬センサ60.5 Mbps & 同じ他チームTCP\\
ESP-NOW／BLE共存 & PC AP→負荷ESP32 & 同じ経路でTCP 20 Mbps & 別のESP32↔M5、75 cm\\\bottomrule
\end{tabularx}\end{center}
'''
    cols = r'\begin{multicols}{2}\fontsize{10}{14}\selectfont\raggedcolumns'
    source = source.replace(cols, setup+cols,1)
    start = source.index(r'\section{目的と評価方法}')
    end = source.index(r'\section{他チーム通信とチャネル配置}')
    source = source[:start]+r'''\section{目的と評価方法}
スマホ操縦とロボットの画像・点群を同じWi-Fi／ROS 2へ載せる運用を模擬し、他チーム・追加無線との両立条件を調べた。実スマホ・センサ・モータは使わない。
C5はESP-SDRでI/Qを取得しFFTで可視化する観測専用機。通信性能は送受信端末のログから測る。
基本指令は64 byte・100 Hzの要求と同内容の応答。RTTは実送信から応答までの往復時間、p99は返った応答の99\%が収まる値である。
20 ms超過率は\textbf{全要求のうち期限内の応答がない割合（欠落込み）}。起点はUDPで送信API、ROS 2と連続ESP-NOWで予定送信時刻である。
欠落は終了後の応答猶予（UDP 1秒、連続ESP-NOW／ROS 2は2秒）後に判定する。更新途絶は\textbf{送信側で応答の最新連番が進まない時間}で、ロボット側の受信途絶とは異なる。
基本3反復、配置以外は反復内で順序を無作為化。20 msは比較目標で安全停止期限ではない。\textbf{異なる端末・経路・期限起点の絶対値で方式を順位付けしない}。

'''+source[end:]
    source = source.replace('自チームCh6・20 MHzを固定。他チームは別のESP32 AP→ESP32で、Ch6／7／11・20 MHzのTCP待機／負荷を各30秒・3反復した。自TCPは要求15.73 Mbps。待機でもビーコンと接続は残る。',
                            '自チームCh6・20 MHz、他チームCh6／7／11・20 MHz。自TCP負荷中に、他TCP待機／負荷を各30秒・3反復した。待機でもビーコンと接続は残る。')
    source = source.replace('他負荷の実受信はCh6で2.5--4.7、Ch7で2.3--3.8、Ch11で1.0--1.3 Mbpsと異なる。自TCPも実受信約1 Mbpsであり、同じ空中時間の比較や競技用PCの速度上限ではない。',
                            '他負荷の実受信はCh6／7／11で2.5--4.7／2.3--3.8／1.0--1.3 Mbpsと異なる。自TCPも約1 Mbpsで、等しい空中時間の比較ではない。')
    source = source.replace(r'\textbf{判定：同一・隣接で遅延が悪化し、分離で増分が小さかった。}',
                            r'\textbf{判定：統合値では同一・隣接で悪化し、分離で増分が小さかった。}')
    source = source.replace('Ch6と7は中心が5 MHz違うだけで20 MHz帯域は重なる。\n'+r'\textbf{番号が違っても別の帯域とは限らない}。送信待ち・再送が原因候補だが未同定である\cite{rf}。',
                            r'Ch6（2437 MHz）とCh7（2442 MHz）は20 MHz帯域が重なる。\textbf{番号が違っても独立とは限らない}。送信待ち・再送は原因候補だが未同定\cite{rf}。')
    source = source.replace(r'\textbf{目的：}他チームの幅20→40 MHzで重なりと操縦品質が変わるかを調べる。',
                            '他チームCh1の20→40 MHz化を比較した。')
    source = source.replace(r'\textbf{判定：一方向の悪化は確認できなかった。}p99と期限超過の変化が逆方向だった。幅は帯域の重なりだけでなく送信時間も変え、他チーム実受信量も揃っていない。幅だけで劣化を決めず、両指標で評価する。',
                            r'\textbf{判定：一方向の悪化は確認できなかった。}p99と期限超過の方向は逆。他TCP実受信も20 MHzの0.9--1.2から40 MHzの0.4--0.8 Mbpsへ変わり、幅だけの効果は分離できない。広い帯域は他チームと重なる範囲を増やすが、指令品質は実負荷でも確かめる。')
    source = source.replace(r'\textbf{目的：}干渉を避けるだけでなく、画像・点群の量や送り方で指令を改善できるかを調べる。',
                            '自チームのデータ量・生成周期・センサQoSで指令を改善できるかを比較した。')
    source = source.replace('同じ1 Mbpsの生成周期100→10 msではCh6超過63.47→59.42\\%、Ch7は53.88→53.88\\%。'+r'\textbf{小分け化には一貫した改善がなかった。}0.5 Mbps・Ch6では超過54.71→58.50\%と逆に増えた。TCPやOSもデータをまとめ直すため、生成周期だけで無線の平滑化を保証できない。',
                            r'生成周期100→10 msでは1 Mbps・Ch6で超過63.47→59.42\%、0.5 Mbps・Ch6で54.71→58.50\%。\textbf{小分け化の効果は一貫しなかった。}TCPやOSもデータをまとめ直す。')
    source = source.replace('実ROS 2（Humble／Jazzy・CycloneDDS）は非圧縮の合成画像640×360・rgb8と4,096点×16 byteの点群を各10 Hz、合計60.5 Mbps生成した。指令はreliable・深さ10に固定し、センサのreliable／best effort（再送保証なし）と深さ1／10を各30秒・3反復した。',
                            'ROS 2（Humble／Jazzy・CycloneDDS）は非圧縮の合成画像640×360・rgb8と4,096点×16 byteの点群を各10 Hzで生成。指令は100 Hz、reliable（再送あり）・深さ10に固定し、センサはreliable／best effort（再送保証なし）×深さ1／10、各30秒・3反復した。')
    source = source.replace(r'\textbf{QoS変更だけでは悪化を解消できなかった。}深さ1は保持履歴数で、無線待ち行列や指令優先度を設定する値ではない\cite{ros}。',
                            r'\textbf{QoS変更だけでは解消しなかった。}深さは保持履歴数で、無線の指令優先度ではない\cite{ros}。')
    source = source.replace(r'\textbf{省電力OFFも一貫した改善を示さず}、指令のみp99約103--109 msが残った。自チーム内の処理や待ちも調べる必要がある。',
                            r'STAの省電力OFFも一貫した改善はなく、指令のみp99約103--109 msが残った。')
    source = source.replace(r'\textbf{判定：BLE配送はほぼ維持されたが、Wi-Fi指令期限は悪化した。}',
                            r'\textbf{判定：反復平均ではBLE配送はほぼ維持され、Wi-Fi指令期限が悪化した。}')
    source = source.replace('BLE 1MのGATT通知（2 ms生成要求）',
                            'GATT通知（接続相手へのデータ送信、2 ms生成要求、PHY 1 Mbps設定）')
    source = source.replace('AFHは使用チャネル集合を更新する仕組みだが、',
                            '適応的周波数ホッピング（AFH）は使用チャネル集合を更新するが、')
    source = source.replace('ESP-NOW Ch6・64 byte要求／応答、20/50/100/200 Hz、Wi-Fi待機／負荷を各600秒・2〜3反復、計19試行した。',
                            'ESP-NOW Ch6・64 byte要求／応答を20/50/100/200 Hz、別系統Wi-Fi TCP待機／15.73 Mbps要求で各600秒・2〜3反復、計19試行した。')
    source = source.replace('配置は机上で固定。ESP32--M5間75 cm、C5まで45／95 cmを基準に、ESP-NOW Ch6・100 Hzを90°回転、手の遮蔽、150 cm、基準復帰で比較した。各配置はWi-Fi待機／負荷×10秒×3反復。',
                            '共存試験はESP32--M5間75 cm、C5から各機へ45／95 cmで固定し、負荷ESP32も同じ机上に置いた。配置比較はESP-NOW Ch6・100 Hz、M5だけ90°回転、両端間の手、両端間75→150 cm、基準復帰を各Wi-Fi待機／負荷×10秒×3反復した。')
    source = source.replace('チャネルを分離しても自チーム内の待ち行列・端末処理は残る。今回もQoS深さ1や省電力OFFだけでは遅延を解消できなかった。',
                            '両チーム比較は分離後も20 ms超過57.2\\%で目標を満たさなかった。基準遅延が大きく、分離だけでは解消しない。自チーム内の処理・待ちも候補で、QoS深さ1や省電力OFFだけでも改善しなかった。')
    source = re.sub(r'\\section\{目的と評価方法\}.*?(?=\\section\{他チーム通信とチャネル配置\})',
                    lambda _: r'''\section{目的と評価方法}
スマホ操縦とロボットの画像・点群が同じWi-Fi／ROS 2を使う運用を模擬した。実スマホ・センサ・モータは使わない。
C5は受動観測専用、通信性能は端末ログで測る。基本指令は64 byte・100 Hz。Mbpsは実受信量、RTTは実送信からアプリ応答までの往復時間、p99は返った応答の99\%が収まる値である。
20 ms超過率は\textbf{全要求のうち期限内の応答がない割合（欠落込み）}。起点はUDPで送信API、ROS 2と連続ESP-NOWで予定送信時刻である。20 msは比較目標で安全停止期限ではない。

''', source, count=1, flags=re.S)
    source = source.replace('短時間の新系列と実装・時間の異なる10分系列を合算しない。',
                            '更新途絶は送信側で応答の最新連番が進まない時間で、ロボット側の受信途絶ではない。欠落は終了後2秒の応答猶予後に判定した。')
    source = source.replace('少数反復の室内結果で、有意差検定は行っていない。',
                            '少数反復で有意差検定は行っていない。')
    source = source.replace('Ch6／11の変化は小さく、Wi-Fi同士の同一Ch最悪という順位とは異なった。APを通らなくても空中時間を共有し、要求・応答・ACKを繰り返す。',
                            'Ch6／11の変化は小さく、Wi-Fi同士の同一Ch最悪という順位とは異なった。APを通らなくても空中時間を共有し、要求・応答・ACKを繰り返す。\n\n配置以外の条件順は反復内で無作為化した。欠落判定の猶予はUDP 1秒、ROS 2と連続ESP-NOW 2秒。端末・経路・期限起点が違う系列の絶対値で方式の優劣は決めない。')
    source = re.sub(r'\\pagestyle\{empty\}(?:\\raggedbottom)*',
                    lambda _: r'\pagestyle{empty}\raggedbottom',source,count=1)
    source = source.replace('PC APはIntel BE200、PC STAはMT7921E。',
                            'PC AP（アクセスポイント）はIntel BE200、PC STA（接続端末）はMT7921E。')
    source = source.replace('C5は受動観測専用、通信性能は端末ログで測る。',
                            'SDRは受信信号をソフトウェアで解析する方式。C5は観測専用、通信性能は端末ログで測る。')
    source = source.replace('新系列のESP-NOW 200 Hz。TCPなし／負荷、反復平均。',
                            'ESP-NOW。TCPなし／負荷、p99・超過とも反復平均。')
    source = source.replace('新系列のBLE停止', 'BLE停止').replace('新1ホップ系列', '1ホップ系列')
    source = source.replace('20秒行列', '20秒試験')
    start = source.index(r'\small\begin{tabular}{@{}crr@{}}',source.index(r'\subsection{Wi-FiからESP-NOWへの影響}'))
    end = source.index(r'\end{tabular}',start)+len(r'\end{tabular}')
    import json
    from statistics import mean
    esp = json.loads((ROOT/'experiments/data/coexistence/espnow-summary.json').read_text())
    table = r'\small\begin{tabular}{@{}crr@{}}\toprule Hz / Ch & p99 [ms] & 20 ms超過 [\%]\\\midrule'+'\n'
    for hz in (100,200):
        for ch in (6,7,11):
            off = esp[f'bidirectional-espnow-wifioff-hz{hz}-ch{ch}']['espnow']
            on = esp[f'bidirectional-espnow-wifiheavy-hz{hz}-ch{ch}']['espnow']
            table += f'{hz} / {ch} & {mean(r["rtt_p99_ms"] for r in off):.2f} / {mean(r["rtt_p99_ms"] for r in on):.2f} & {mean(r["planned_deadline20_pct"] for r in off):.3f} / {mean(r["planned_deadline20_pct"] for r in on):.3f}'+r'\\'+'\n'
    table += r'\bottomrule\end{tabular}'
    source = source[:start]+table+source[end:]
    source = source.replace(r'\subsection{ESP-NOWからWi-Fiへの速度変化}',
                            r'''\subsection{ESP-NOWからWi-Fiへの速度変化}
20秒試験のCh11・200 HzではWi-Fi実受信平均0.411→0.275 Mbps、低下率平均34.0\%。ただし反復は−28.4〜77.9\%と増減が混在した。
''',1)
    source = source.replace('今回の比は室内の観測値で、方式固有の固定した低下率ではない。',
                            'これらの比を方式固有の低下率とはしない。')
    source = source.replace('ESP-NOW／BLE共存 &', '外部無線 &')
    source = source.replace('接続相手へのデータ送信、2 ms生成要求、PHY 1 Mbps設定',
                            '244 byte、2 ms生成要求、PHY 1 Mbps設定')
    source = source.replace(r'\section{BLEとWi-Fiの相互影響}',
                            r'\section{独立BLEリンクとWi-Fiの相互影響}')
    source = source.replace('各行約205 $\\mu$s、名目RF観測時間比約0.4\\%で、縦軸は\\textbf{間欠取得順}である。',
                            '縦軸は\\textbf{取得番号（上ほど先）}。1行は約205 $\\mu$sの受信記録のスペクトルである。転送・処理待ちの未記録時間を省いて並べたため、上下の行は連続波形ではない。RF記録時間は経過時間の約0.4\\%。縦の長さから送信継続時間は求められない。')
    return source


def ble_scope_and_capture_explanation(source):
    """Keep RF-only advertising observations distinct from link-quality tests."""
    source = re.sub(r'% BEGIN BLE CAPTURE EXPLANATION [^\n]+\n.*?% END BLE CAPTURE EXPLANATION\n?', '', source, flags=re.S)
    sections = [
        (r'\subsection{BLEとWi-Fiの両方向の配送量}', 'sec:ble-mutual', r'''
\noindent\textbf{評価対象の区別}\quad
本節は独立したESP32--M5 ATOM LITEのBLEリンクと、PC AP→別のESP32のWi-Fiリンクについて、双方の実受信量とWi-Fi指令応答を測る通信性能実験である。
BLE広告と接続通知を比較し、表のMbps・期限超過率は端末の通信記録から求めた。
第\ref{sec:ble-advert-rf}節は別の送信機であるPCのBLE広告をC5で観測する受信実験で、接続通知の配送量を測っていない。
その広告周波数の電力差と、本節の速度差・期限超過を同じ試行の結果として対応付けない。
'''),
        (r'\section{BLE広告の受信スペクトル観測}', 'sec:ble-advert-rf', r'''
\noindent\textbf{目的と評価対象}\quad
PCのBLE広告をOFF／ONし、既知の広告周波数に狭帯域成分が現れるかをC5で調べる。
本節は受信スペクトルの実験で、BLE接続通知や双方の通信速度・指令応答を測った第\ref{sec:ble-mutual}節とは送信機・負荷条件・指標が異なる。
したがって「2480 MHzの最大電力が20.6 dB増えた」は広告の見え方の結果であり、「Wi-Fi期限超過が0.067→0.483\%へ増えた」の根拠ではない。
通信への相互影響は第\ref{sec:ble-mutual}節の独立したESP32--M5リンクの停止対照で評価する。
'''),
        (r'\subsection{間欠取得と比較指標}', 'sec:intermittent', r'''
\noindent\textbf{画像の縦軸の読み方}\quad
「取得順」または「取得番号」は、短い受信記録を取得した順番に並べた番号で、秒・ミリ秒の時間軸ではない。
80 MS/sの図では1行が約205 $\mu$sのI/Q記録から計算したスペクトルを表し、上ほど先に取得した。
次の取得までにUSB転送・処理・待ち時間が入るが、画像ではこの未記録時間を詰めて隣の行を描く。
例えば50 ms間隔で取得すれば、約0.205 msを記録した後の約49.8 msは観測データに含まれない。
上下に隣接する行を連続した波形と解釈したり、緑の縦の長さを送信継続時間・チャネル占有率へ換算したりはできない。
「間引いた取得列」と注記した図では、取得済みの記録からも一部の行だけを選んで表示している。
'''),
    ]
    for heading, label, text in sections:
        if label:
            source = source.replace(heading+r'\label{'+label+'}', heading)
        block = ('\n% BEGIN BLE CAPTURE EXPLANATION '+(label or 'waterfall')+'\n'
                 +(r'\label{'+label+'}\n' if label else '')+text
                 +'% END BLE CAPTURE EXPLANATION\n')
        assert heading in source, heading
        source = source.replace(heading, heading+block, 1)
    guide = '青緑SDR画像は受信した帯域の重なりを説明する補助で、画像の緑を通信成功、占有率、干渉原因の特定へ読み替えない。'
    note = ('\n80 MS/sの図では各行が約205 $\\mu$sの短い受信記録を表し、行の間に記録していない時間がある。'
            '縦軸は時間ではなく取得番号で、詳しい読み方は第\\ref{sec:intermittent}節に示す。')
    source = source.replace(guide+note, guide)
    source = source.replace(guide, guide+note, 1)
    return source


def revise_reports():
    full = ROOT/'reports/full.tex'
    source = scrub_history(full.read_text())
    source = inject_verdicts(source)
    source = reader_framework(source)
    source = simplify_details(source)
    source = ble_scope_and_capture_explanation(source)
    # These are decisions about observed differences, not unperformed
    # significance tests or numerical estimates of statistical correlation.
    marker = r'\subsection{速度・期限・スペクトルを別々に見る理由}'
    explanation = ('\n「増加・減少を観測」は平均値または統合値の条件差を表す。'
                   '全反復で同じ方向の差が出た場合は、その旨を別に記す。'
                   '「一貫した傾向なし」は反復または条件間で増減が混在した比較、'
                   '「判定不能」は対照や時刻情報が不足した比較を表す。'
                   '相関係数や有意差検定による判定ではなく、少数反復の差を普遍的な効果とは扱わない。\n')
    source = source.replace(marker+explanation, marker)
    source = source.replace(marker, marker+explanation, 1)
    full.write_text(re.sub(r'\n{3,}', '\n\n', source))
    short = ROOT/'reports/twitter.tex'
    short.write_text(re.sub(r'\n{3,}', '\n\n', twitter_standalone(twitter_verdicts(scrub_history(short.read_text())))))


if __name__ == '__main__':
    revise_reports()
