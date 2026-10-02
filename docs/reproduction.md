# 再生成と実機取得

## 公開データからの再生成

リポジトリ直下で`make check`を実行すると、公開データの全SHA-256を確認し、先行56試行と追加87試行のRTT p99、損失率、20 ms期限超過、送信ジッターおよび条件群の統計を相対時刻から再計算します。原集計と一致しない場合はエラーになります。

`make figures`は操縦通信の主要な青・緑パネルと遅延比較図を、公開した実測FFT電力とJSONから生成します。主比較は反復1の画像と全反復の集計値を区別しています。ESP-NOWの反復変動図は同一条件の全3反復、X用小図は反復1・3を明記します。基礎観測・受信系の既存図はそのまま添付しています。公開データだけで生I/QのFFT長変更、STF探索、生PCAPとの照合をやり直すことはできません。

`make reports`で自己完結した2本のLaTeXをLuaLaTeXで各2回コンパイルします。必要パッケージはluatexja、fontspec、geometry、graphicx、booktabs、siunitx、hyperref、TikZ、titlesec、placeinsなどです。見出しの英字・日本語はHaranoAjiGothic-Mediumで統一しています。著者名は貝淵蒼馬、紙面の日付はありません。`make images`はX用3ページのPDFを300 dpi PNGへ書き出します。

## 実機取得コード

`experiments/scripts/acquisition/`には使用した取得コードを、ホスト名や元Wi-Fiプロファイルを設定で渡す形に整理してあります。先行取得コードと、追加の両チーム・周期負荷・BLE実機測定コードを含みます。測定構成の違いは[主実験の方法](two-team-method.md)を参照してください。

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

計測時のC5ソースはコミット`4d990f76538109a7769b632471a411a186b97a8e`に残っています。これは`ff1966a`に局所的な時計応答・初期帯域選択の修正を加えた版です。現在の`main`は上流の更新を統合しているため、計測実行版とは区別してください。公開整理時の上流統合自体ではC5へ再書込みしていません。今回の追加通信試験にも、この既存C5ファームウェアを使用しています。

元資料はローカルの`artifacts/private-originals.tar`へ非公開で保管しています。公開用コミットの`artifacts/publication.bundle`と`artifacts/publication.patch`もローカルに保存します。GitHubからcloneした環境には、これらのバックアップは付属しません。

`scripts/publish.sh`は、ローカルのGit bundleから個人アカウントの公開フォークへ資料を送るための補助スクリプトです。既存の`main`をfetch・mergeしてからpushします。競合があれば作業コピーの場所を表示して終了します。通常の更新は公開リポジトリでコミットし、`git push origin main`を実行してください。

## 両チーム通信・周期Wi-Fi・BLEの再測定

`team_traffic.py`はロボット側のUDP echoとTCP模擬データ、`team_robot_wrapper.py`は一時NetworkManager接続と期限付きの元Wi-Fi復帰を担当します。観測PCにはCh6・20 MHz、192.168.8.1/24、SSID `ESP-SDR-TEAM-A`のAP接続 `sdr-team-a-controller`を事前作成します。SSID、IP、ポートは取得コードとファームウェアの実験定数です。実機のインターフェースや元接続は各環境で確認します。

元のフラッシュを退避し、ESP32-1/2はrobotics v3/v5、ESP32-3はteam-controller、C5は時刻付きSDRを使用します。`TWO_TEAM_ROOT`で非公開の計測保存先を指定し、`evidence/http-token`へ認証用文字列を600権限で保存します。ロボット側へ同じ値を渡します。秘密と元I/Qは公開ツリーへ置きません。

```sh
python3 experiments/scripts/acquisition/run_two_team.py
python3 experiments/scripts/acquisition/run_radio_coexist.py burst
# この段階でESP32-1/2をble-linkへ書き換える
python3 experiments/scripts/acquisition/run_radio_coexist.py ble --pilot
python3 experiments/scripts/acquisition/run_radio_coexist.py ble
python3 experiments/scripts/analyze_two_team.py --raw /非公開の保存先/raw
make check
make figures
make report-sources
make reports images
```

USB割当は取得コード既定でESP32-1=ttyUSB0、2=ttyUSB1、3=ttyUSB2、C5=ttyACM0です。変わった場合は必ず識別して合わせます。実験終了後にHTTP `/stop`でロボット側を復帰させてから観測PCの一時APを終了・削除し、元接続を戻します。ESP32の電波出力と負荷を停止し、C5を通常表示用設定へ戻します。

主実験の相対時刻とFFTからは統計・図を再生成できます。時刻とI/Qの厳密なパケット一致、連続占有率、元I/Qの再FFT、ROS 2トピックの評価は再現範囲に含みません。

## ESP-NOW指令の追加測定

[ESP-NOWの測定条件](espnow-method.md)を参照してください。ESP32-1/2を`espnow-link`へ書き換え、UART115200で動作させます。ESP32-3は`team-controller`の460800 baudです。独立Wi-Fi負荷用のAPとロボットhelperを起動してから、`run_espnow.py --pilot`、`run_espnow.py`を実行します。MACはUARTで取得してその場でpeer設定し、公開時には除去します。元フラッシュと元I/Qは非公開保管します。

公開処理は`analyze_espnow.py --raw /非公開の保存先/raw`、検算は`make check`、画像は`make figures`、表と考察の数値反映は`make report-sources`、組版は`make reports images`です。読み出しのUARTが遅くても、ベンチマーク時刻はESP内部で記録します。追加ESP-NOWの負荷helperはkeepaliveを加えた版で、先行69試行で使用した版はコミット`b5af98b`に保持しています。
