# ロボコンの操縦通信とWi-Fi干渉の可視化

貝淵蒼馬

ESP32-C5で受信したスペクトルと、操縦を模した100 Hz UDP通信の遅延を対応づけた室内実験です。指令と大容量通信がAPを中継する構成で、他チームも通信中のチャネル・幅・外部Bluetoothの影響を調べました。

[詳細版PDF](reports/full.pdf) · [X用3ページPDF](reports/twitter.pdf) · [投稿画像](reports/images) · [詳細版LaTeX](reports/full.tex) · [X用LaTeX](reports/twitter.tex)

![同一・隣接・分離チャンネルの実測スペクトル](experiments/figures/two-team/two-team-blue-green.png)

## 実験から得られたこと

- 自チームの大容量通信中、他チーム負荷によるRTT p99の増分は、同一Ch6で約23 ms、隣接Ch7で約9 ms、分離Ch11で約1 msでした。今回の固定配置の結果で、他チームの実通信量も異なります。
- 操縦だけでもp99が117–120 msで、20 ms目標を満たしていません。全遅延を他チーム干渉へ帰属せず、同じ条件の待機との差で考察します。
- 20/40 MHzの比較はp99の単調な悪化を示しませんでした。帯域の重なり、実受信量、期限超過を一緒に見る必要があります。
- 通常Wi-Fiの2秒ON/OFF負荷と、独立したBLEの停止・広告・GATT通知を比較しました。BLEは実際の広告復号・通知受信を確認し、Wi-Fi操縦応答と同時に記録しています。

追加は69試行（主42・周期Wi-Fi9・BLE18）、207,000送信、39,149 I/Q取得です。構成の異なる先行56通信試行、115受信観測系列も詳細版へ補足として保持しました。実ROS 2や映像コーデックではなく、UDP/TCP模擬負荷のアプリケーション測定です。

青〜緑は未校正の相対FFT電力（dBFS）です。各行は約205 µsの間欠取得で、連続時間や占有率ではありません。[測定方法と限界](docs/two-team-method.md)も参照してください。

## ディレクトリ

| 場所 | 内容 |
| --- | --- |
| `reports/` | 詳細版とX用の2種類のLaTeX、PDF、投稿画像 |
| `experiments/data/` | 匿名化した解析統計・FFT電力・操縦UDP相対時刻 |
| `experiments/figures/` | 基礎観測・受信評価・操縦通信・概要の図 |
| `experiments/scripts/` | 図の生成、結果検算、実機取得コード |
| `experiments/firmware/` | ESP32の通信負荷・コントローラー・BLEファームウェア |
| `docs/` | 実験条件・データ形式・再生成方法 |
| `main/`, `components/` | 上流ESP-SDRとC5用の変更 |

実験は日付別に分けず、役割別に整理しました。`baseline`は基礎観測、`receiver`は受信系の補足評価、`robotics`は先行操縦通信、`two-team`は両チーム負荷・周期Wi-Fi・BLE比較です。

## 再生成

LuaLaTeX、luatexja、Harano Ajiフォント、Poppler、Pythonが必要です。

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
make check        # 公開データのハッシュと遅延統計を検算
make figures      # 実測FFT電力から青・緑の図を再生成
make reports      # full.tex と twitter.tex をコンパイル
make images       # X用PDFを300 dpi PNGへ変換
```

図の日本語表示にはNoto Sans CJK JPを使用します。既存のPDF・PNGはそのまま閲覧できます。公開データから再現できる範囲と実機実験の準備は[再生成方法](docs/reproduction.md)を参照してください。

## 上流とライセンス

[ESPARGOS/esp-sdr](https://github.com/ESPARGOS/esp-sdr)を基にしています。上流の履歴、GPL-3.0の[LICENSE](LICENSE)、ファームウェア文書を保持しています。[上流README](docs/upstream.md)に元のプロジェクト説明があります。測定値を引用する際は、試行数・条件・間欠観測の制約も併記してください。
