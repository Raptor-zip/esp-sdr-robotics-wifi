# 公開データ形式

元の計測値を変えず、ネットワーク名、個人のホスト名、MACアドレス、認証URL、生PCAP、復号可能なI/Qを公開対象から外しています。原データと旧資料は非公開の保管先に保持しています。公開版ではファイル名に計測条件・反復を残し、フォルダー名で日付を分けません。

| ファイル | 内容 |
| --- | --- |
| `data/manifest.json` | 公開データのSHA-256、計測件数、公開範囲 |
| `baseline/*-spectrum.npz` | `frequency_mhz`、線形電力の`mean`と`maximum` |
| `baseline/*.json` | 基礎観測の条件と相対電力・飽和・取得割合の統計 |
| `receiver/*.npz`, `*.json` | 補足評価の既存導出スペクトル・統計 |
| `robotics/*-control.npz` | `sent_ns`、`received_ns`、`planned_ns`の相対単調時計 |
| `robotics/*-spectrum.npz` | `frequency_mhz`、各取得の`power_dbfs`、線形`mean`・`maximum` |
| `robotics/*.json` | 各試行の遅延・送受信数・設定・負荷のカウンター |
| `robotics/runs.json` | 主解析56試行の一覧 |
| `robotics/summary.json`, `summary.csv` | 条件群別の集計 |
| `robotics/udp-load.json` | UDP要求・受付・到達速度とアプリケーション欠落率 |

操縦時刻は各試行の最初の送信を0とするns単位です。`received_ns == 0`は未受信の印で、最初の`sent_ns == 0`は有効な送信です。`planned_ns`には基準より前の負値があり得ます。時間差・RTT・送信ジッターは原記録と一致します。絶対ホスト時刻や生ネットワーク状態のログは遅延計算に必要ありません。

FFT電力はDC除去・Hann窓・窓和の二乗による規格化・区間の線形電力平均を用います。C5の符号規約に合わせRF周波数はLOからベースバンド周波数を引いています。`power_dbfs`は保存容量のためfloat32で、図の表示に必要な精度を保持します。FFTから元の位相やWi-Fiフレームは復元できません。

主要な青・緑比較は−90〜−45 dBFS。BLEの狭帯域拡大図だけは弱い信号を見るため−90〜−60 dBFSで、図内の共通尺度を明記します。各行は1つの間欠取得で、取得番号の軸を実時間の連続ウォーターフォールとして解釈しないでください。dBFSはdBmへの校正値でもチャネル占有率でもありません。

## 両チーム・周期Wi-Fi・BLE (`two-team`)

`*-control.npz`はESP32-3のBENCH開始を基準としたns単位の`sent_ns`・`planned_ns`・`received_ns`です。**このデータ群の欠落印は`received_ns == -1`**で、先行`robotics`の0とは異なります。元のµs時計をnsへ変換しただけで1 ns精度にはなりません。空の`bulk_records`は互換のための形状で、センサー時刻列は測っていません。

`*-spectrum.npz`はRFの`frequency_mhz`、取得行×1024 binのfloat32 `power_dbfs`、`capture_start_s`と`capture_end_s`です。取得時刻はホストUARTコマンド開始からの相対秒で、ESP時計との対応は近似です。パケットとFFTの厳密な同期には使えません。

試行JSONには`condition`、`rtt_ms`、`loss_pct`、`missed_deadline_pct`、`delivered_payload_mbps`（自チーム実受信）、`source_payload_mbps`（TCP送信受付）、`other_delivered_mbps`（他チーム実受信）、SDR設定とCRC照合結果があります。周期Wi-Fiには`load_transitions`（ON/OFF、操作前後の相対秒）、BLEには送受信状態、広告復号数、MTUと接続間隔が加わります。BLE接続間隔の`interval_units`は1.25 ms単位です。送信APIエラー率はPHYパケット損失率とは違います。

`summary.json`は各条件の反復数、全応答を統合したp99、期限超過、各反復のp99・実受信速度を残します。要求15.73 Mbpsを実到達量と置換していません。`manifest.json`の`two_team`は主42・周期9・BLE18試行を先行群と分けて集計します。`make check`が全SHA-256と時刻からの独立再計算を行います。

## ESP-NOW (`espnow`)

時刻NPZの欠落印は`received_ns == -1`で、相対ns単位、実時計の分解能は1µsです。`radio`には送信側・echo側・独立Wi-Fi受信側の前後カウンタ、実チャネル、受信rate・sig_modeがあります。MACは除去します。`wifi_delivered_mbps`を実受信bytes差と`counter_window_seconds`で検算します。`sent`はAPI受付失敗を含む送信要求数で、欠落をそのままPHY損失率としません。FFTとSDR設定は`two-team`と同じ形式です。`manifest.espnow`と`summary.json`は先行群と分けた18試行の集計です。

## 運用評価 (`operational`)

`limit`は45試行の流量制限、`shape`は36試行の生成周期比較です。UDP指令の欠落印は`received_ns == -1`、予定・実送信・応答は指令機の単一時計で記録しています。要求生成量、TCP送信受付、実受信、別チームの実配送と現行接続確認を区別して保存します。旧取得やpilotを正式行列へ追加しません。

`ros2`は45試行の実ROS 2（指令側Humble・ロボット側Jazzy、双方CycloneDDS）のQoS比較、`power`は24試行の省電力ON／OFF比較です。`*-control.npz`には全予定slot、publish、応答の相対時刻、`*-echo.npz`にはロボット時計内だけのcallback・publish時刻、`*-sensors.npz`には生成／publish／初回受信の相対イベント列があります。各roleの時計の起点は独立で、列同士を引いて未同期PC間の片道遅延やセンサの古さを推定できません。指令のRTTは指令側の時計だけで算出します。センサ更新間隔は各unique sequenceの初回受信間隔で、古いsequenceの遅着を除く下記ESP-NOWの更新指標とは異なります。

`espnow-long`には19試行・各600秒・8条件を2〜3反復した全アプリイベントを保存しました。`*-events.npz`の各イベントは種別、sequence、送信機の相対µs時刻、引数の4列です。種別は送信呼出し1、応答callback2、飛ばした予定slot3、終了4。`block_event_counts`と`block_received_ns`はUARTのブロック数とホスト側の相対受信時間で、アプリ時刻とは違います。`*-control.npz`はこれを相対nsへ換算した全予定・送信・初回応答・API結果で、未送信／未受信は−1です。nsへの換算はµs時計の精度を増やしません。UART CRC・END・全slot被覆・trace drop=0・実機カウンタを検算してから欠落を算出します。MAC成功／失敗は集計値であり、個々のsequenceへ対応づけません。

長時間系列の`timeline`は10秒窓のp99・全予定指令の20 ms期限超過です。最新sequenceへの最長更新途絶では、順序が戻った応答を新しい情報の更新に数えません。`counter_samples`は10秒ごとの実負荷と最後に受信したRSSIで、RSSIの全パケット分布ではありません。`manifest.operational.espnow-long.status`の`stopped_at_user_request`は、使用者の終了希望で進行中試行を保存後に終了したことを表します。予定24試行の完全行列とは呼ばず、残り5試行を補完しません。

`placement`は使用者が変更・確認したESP32間の短い配置比較用です。各試行10秒、100 Hz、監視2秒、`layout.placement`に中心間距離cm・回転角・遮蔽物と距離の注記を残します。私有の確認返答原文は公開しません。短い配置系列と600秒系列を同じ安定性集計へ混ぜません。

保存待ち超過で最終設定が揃わなかった600秒試行は`operational/supplemental/espnow-storage-timeout*`に全12000送信／応答を保持しています。未確認の終了設定・負荷量は補完せず、正式19試行には含めません。`manifest.supplemental`の別集計です。旧有効試行を消したり、悪い通信結果を理由に再測定へ置き換えたりしていません。
