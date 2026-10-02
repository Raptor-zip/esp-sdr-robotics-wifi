# 再生成と実機取得

## 公開データからの再生成

リポジトリ直下で`make check`を実行すると、公開データの全SHA-256を確認し、56試行のRTT p99、損失率、20 ms期限超過、送信ジッターおよび19条件群の統計を相対時刻から再計算します。原集計と一致しない場合はエラーになります。

`make figures`は操縦通信の主要な青・緑パネルと遅延比較図を、公開した実測FFT電力とJSONから生成します。取得反復1の画像と全反復の集計値を明記しています。基礎観測・受信系の既存図はそのまま添付しています。公開データだけで生I/QのFFT長変更、STF探索、生PCAPとの照合をやり直すことはできません。

`make reports`で自己完結した2本のLaTeXをLuaLaTeXで各2回コンパイルします。必要パッケージはluatexja、fontspec、geometry、graphicx、booktabs、siunitx、hyperref、TikZ、titlesec、placeinsなどです。見出しの英字・日本語はHaranoAjiGothic-Mediumで統一しています。著者名は貝淵蒼馬、紙面の日付はありません。`make images`はX用3ページのPDFを300 dpi PNGへ書き出します。

## 実機取得コード

`experiments/scripts/acquisition/`には使用した取得コードを、ホスト名や元Wi-Fiプロファイルを設定で渡す形に整理してあります。移行後の検証はオフラインの構文確認と解析整合性確認です。実機実験を再実行した結果ではありません。

- `capture.py`: ESP32-C5のCRC付きI/Q取得。終了時にシリアルのVMIN/VTIMEを復元。
- `timed_capture.py`: `CLOCK?`と`CAPTIME?`を使った時刻付き取得。
- `control.py`: UDP echoの100 Hz計測。
- `load_client.py`, `interferer_client.py`, `udp_client.py`: 通信負荷の受信クライアント。
- `run.py`, `run_udp.py`: 反復・条件順序・同時SDR取得を行う実験ドライバー。
- `board.py`: 追加ESP32へのUARTコマンド。
- `nm_network.py`: 事前に起動したNetworkManager実験APの状態取得と終了時の復元。
- `pcap_read.py`: 旧PCAP評価用パーサー。PCAP自体は配布しません。

実験ドライバーは、事前に設定されたCh6/20 MHzの実験AP、有線インターネット共有、負荷用ラップトップのSSH、追加ESP32の実験ファームウェアを前提とします。NetworkManagerの新規AP作成まで自動で行う手順ではありません。ラップトップが実験APへ移る間はインターネットが切れるため、自律終了・元接続への復帰が必要です。上流回線を担うラップトップ1を負荷クライアントにしない構成を使用しました。

| 設定 | 用途 |
| --- | --- |
| `ESP_SDR_OUTPUT_ROOT` | 生計測の保存先（既定`/tmp/esp-sdr-acquisition`） |
| `ESP_SDR_CLIENT_SSH` | ラップトップ2のSSH先（既定SSH別名`laptop2`） |
| `ESP_SDR_ARCHIVE_DEST` | ラップトップ2へ転送する保存先 |
| `ESP_SDR_ORIGINAL_WIFI` | 実験後に復元する接続プロファイル。NM操作前に必須 |
| `ESP_SDR_WIFI_IFACE` | 無線インターフェース名（既定`wlan0`） |
| `ESP_SDR_ETH_IFACE` | 有線インターフェース名（既定`eth0`） |
| `ESP_SDR_CONTROL_MAC` | DHCP leaseから操縦用ESP32を識別するMAC |
| `C5_DATA` | 単独C5取得の生データ保存先 |

各PCの設定を先に確認してください。実験用SSIDとパスフレーズは実験専用のサンプル値で、利用者の通常ネットワークとは別です。生データの既定保存先は一時領域なので、必要な計測は実験後に永続ストレージへコピーしてください。

## ファームウェア

C5の上流ファームウェアは`docs/upstream.md`、受信制御は`docs/rx-controls.md`を参照してください。`main/families/c5_c6_c61/receiver.c`の時計・取得区間応答と初期帯域選択の変更を保持しています。

追加ESP32の実験コードは`experiments/firmware/robotics/main/`にあります。`lab.c`とv4/v5のソース、実験で使ったアプリケーションイメージ、測定済みイメージのハッシュを保管しています。v3/v5などの履歴イメージをすべて現在の`lab.c`から再生成できるわけではありません。利用者が元から書き込んでいた全フラッシュのバックアップは公開していません。

```sh
cd experiments/firmware/robotics
idf.py set-target esp32
idf.py build
# 接続先を確認した上で、必要な場合にだけ書き込む
idf.py -p /dev/ttyUSB0 flash
```

## 初回公開のローカル成果物

整理前の資料は、ローカルの`artifacts/private-originals.tar`にまとめています。このバックアップは公開対象に含めません。公開用コミットの`artifacts/publication.bundle`と`artifacts/publication.patch`もローカルで保存します。

この作業環境では元リポジトリの`.git`が読取専用で、端末からGitHubへ接続できませんでした。公開用コミットは別のGit作業コピーで作成しています。通常の端末で次を実行すると、認証中の個人アカウントへ公開フォークを作成し、検証済みコミットをpushできます。既に同じ上流のフォークを所有していて新規フォークを作れない場合は、履歴を保持した新規公開リポジトリを作ります。元の作業ツリーを変更する処理はありません。

```sh
bash scripts/publish.sh
```

既定のリポジトリ名は`esp-sdr-robotics-wifi`です。既存の同名リポジトリが非公開、または別プロジェクトの場合は中止します。公開済みリポジトリをcloneした環境には、これらのローカルbundleや非公開バックアップは付属しません。
