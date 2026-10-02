# 独立したBLE送受信リンク

ESP-IDF 6.2、ESP32 targetで取得に使用したソースと、実際に書き込んだバイナリです。`binaries/sha256.json`にSHA-256、`sdkconfig.measured`に測定版の設定を保存しています。

```sh
idf.py set-target esp32
idf.py build
```

計測用バイナリの配置はbootloader 0x1000、partition-table 0x8000、app 0x10000、DIO・40 MHz・4 MBです。USB基板の識別と元フラッシュの非公開バックアップを済ませてから書き込みます。C5受信用ファームウェアとは別です。

UARTは115200 baud。`ROLE 0`停止、`ROLE 1`周辺、`ROLE 2`中央、`ROLE 3`非接続広告、`ROLE 4`広告受信。中央から`SUB HANDLE`で通知を購読し、周辺から`LOAD 2 45`で2 ms周期・45 sのGATT通知負荷を要求します。実際の受信bytes、広告復号数、MTU、接続間隔はSTATUSで確認します。BLE専用でWi-Fiを起動しません。Classic、音声、2Mの試験には使っていません。
