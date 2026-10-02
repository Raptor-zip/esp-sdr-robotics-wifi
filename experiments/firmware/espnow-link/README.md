# ESP-NOWアプリ応答の取得

ESP-IDF6.2・ESP32・CPU240MHz・省電力なしの測定版です。同じファームウェアをESP32-1/2へ書き込み、UART115200でpeerと役割を設定します。1Mbps long preamble、未暗号化unicastです。実際の受信rate・sig_modeも状態へ保存します。

`STATUS`でMACを取得し、相手のMACを`PEER xx:xx:xx:xx:xx:xx`で設定します。`ROLE 1`はecho、`ROLE 2`は送信、`CHANNEL 6|7|11`でチャネルを変えます。`BENCH ID 3000`で64byte・100Hzを測り、`DUMP`でµs時刻列をCRC32付きで取得します。`STOP`で役割と送信を停止します。

MAC送信callback成功とアプリ応答を区別します。送信API受付失敗も記録し、要求した指令に応答がなかった割合を評価します。受信callbackではechoをキューへ入れ、別タスクで応答を送ります。アプリ再送は行いません。

`binaries/`は測定したapp、bootloader、partition-table、sdkconfigとSHA-256です。配置は0x10000、0x1000、0x8000、DIO・40MHz・4MBです。元フラッシュは公開対象外に退避しています。ソースは`idf.py set-target esp32`、`idf.py build`でビルドできます。UARTの高速設定は一部の測定基板で安定しなかったため、115200を使用します。
