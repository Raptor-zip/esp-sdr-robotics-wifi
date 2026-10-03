# 流量制限実験の他チーム用Wi-Fiファームウェア

ESP32-1をTCP受信STA、ESP32-2をTCP送信APとして使用する。`STATUS` の `version` は7。接続時にSTAのnonce、APの新規challenge、その応答を交換して現在の相手を確認する。両端の `tcp_nonce`・`tcp_challenge` が一致し、`tcp_peer_ready` が成立してから測定する。送信試行数・EAGAIN・実ソケット受付量・実受信byte数・負荷設定と残り時間も保存する。TCP送信待ちを切断として扱わず、STOP/AP/STAで旧接続を終了する。この対策が無線の性能低下をなくすとは仮定しない。

ESP-IDF環境でリポジトリルートからビルドする。

```sh
idf.py -C experiments/firmware/operational-wifi -B build-operational-wifi build
```

UARTは115200 baud。測定に使用するバイナリと設定は `binaries/`、SHA-256は `binaries/sha256.json`。ESP32-2への書込み速度も115200 baudとする。元フラッシュは公開せず、別途バックアップする。

```sh
python -m esptool --chip esp32 --port /dev/ttyUSB1 --baud 115200 write_flash \
  0x1000 experiments/firmware/operational-wifi/binaries/bootloader.bin \
  0x8000 experiments/firmware/operational-wifi/binaries/partition-table.bin \
  0x10000 experiments/firmware/operational-wifi/binaries/app.bin
```

使用例は `AP 7 20 76`、`STA ESP-SDR-INTERFERER SdrLab2026TestOnly 192.168.4.1 20`、`LOAD 1000 44`、`STATUS`、`STOP`。LOADは通常のTCP通信で、期間終了後に送信を停止する。測定条件・実受信量・接続状態は取得スクリプトで保存する。
