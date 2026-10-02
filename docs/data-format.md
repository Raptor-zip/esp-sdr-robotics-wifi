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

青・緑の色尺度は全比較で−90〜−45 dBFS。各行は1つの間欠取得で、取得番号の軸を実時間の連続ウォーターフォールとして解釈しないでください。dBFSはdBmへの校正値でもチャネル占有率でもありません。

## 両チーム・周期Wi-Fi・BLE (`two-team`)

`*-control.npz`はESP32-3のBENCH開始を基準としたns単位の`sent_ns`・`planned_ns`・`received_ns`です。**このデータ群の欠落印は`received_ns == -1`**で、先行`robotics`の0とは異なります。元のµs時計をnsへ変換しただけで1 ns精度にはなりません。空の`bulk_records`は互換のための形状で、センサー時刻列は測っていません。

`*-spectrum.npz`はRFの`frequency_mhz`、取得行×1024 binのfloat32 `power_dbfs`、`capture_start_s`と`capture_end_s`です。取得時刻はホストUARTコマンド開始からの相対秒で、ESP時計との対応は近似です。パケットとFFTの厳密な同期には使えません。

試行JSONには`condition`、`rtt_ms`、`loss_pct`、`missed_deadline_pct`、`delivered_payload_mbps`（自チーム実受信）、`source_payload_mbps`（TCP送信受付）、`other_delivered_mbps`（他チーム実受信）、SDR設定とCRC照合結果があります。周期Wi-Fiには`load_transitions`（ON/OFF、操作前後の相対秒）、BLEには送受信状態、広告復号数、MTUと接続間隔が加わります。BLE接続間隔の`interval_units`は1.25 ms単位です。送信APIエラー率はPHYパケット損失率とは違います。

`summary.json`は各条件の反復数、全応答を統合したp99、期限超過、各反復のp99・実受信速度を残します。要求15.73 Mbpsを実到達量と置換していません。`manifest.json`の`two_team`は主42・周期9・BLE18試行を先行群と分けて集計します。`make check`が全SHA-256と時刻からの独立再計算を行います。
