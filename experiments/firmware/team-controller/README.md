# コントローラー役のUDP/TCP通信

ESP-IDF 6.2、ESP32 targetで取得に使用したソースと、実際に書き込んだバイナリです。`binaries/sha256.json`にSHA-256、`sdkconfig.measured`に測定版の設定を保存しています。

```sh
idf.py set-target esp32
idf.py build
```

計測用バイナリの配置はbootloader 0x1000、partition-table 0x8000、app 0x10000、DIO・40 MHz・4 MBです。USB基板の識別と元フラッシュの非公開バックアップを済ませてから書き込みます。C5受信用ファームウェアとは別です。

UARTは460800 baud。既定の実験SSID `ESP-SDR-TEAM-A`、192.168.8.10のSTAとして動作します。相手PCは192.168.8.20、UDP 5140でecho、TCP 5003で模擬大容量データを送信します。`BENCH ID 3000`、`STATUS`、`DUMP`、`STOP`で制御します。DUMPの時刻はµs、CRC32付き。受信量と応答時刻は同じESP時計の窓で数えます。
