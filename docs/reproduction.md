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

## 公開リポジトリとローカル保管

公開先は [Raptor-zip/esp-sdr-robotics-wifi](https://github.com/Raptor-zip/esp-sdr-robotics-wifi) です。`origin`は個人公開フォーク、`upstream`は`ESPARGOS/esp-sdr`です。上流の更新と実験資料の履歴を両方保持しています。

計測時のC5ソースはコミット`4d990f76538109a7769b632471a411a186b97a8e`に残っています。これは`ff1966a`に局所的な時計応答・初期帯域選択の修正を加えた版です。現在の`main`は上流の更新を統合しているため、計測実行版とは区別してください。公開整理時の統合に伴う実機への再書込みや再測定は行っていません。

元資料はローカルの`artifacts/private-originals.tar`へ非公開で保管しています。公開用コミットの`artifacts/publication.bundle`と`artifacts/publication.patch`もローカルに保存します。GitHubからcloneした環境には、これらのバックアップは付属しません。

`scripts/publish.sh`は、ローカルのGit bundleから個人アカウントの公開フォークへ資料を送るための補助スクリプトです。既存の`main`をfetch・mergeしてからpushします。競合があれば作業コピーの場所を表示して終了します。通常の更新は公開リポジトリでコミットし、`git push origin main`を実行してください。
