# ESP-NOW連続取得ファームウェア

自分たちの2台を使う未暗号化unicastの64 byte指令・応答を、20・50・100・200 Hzで連続取得するためのソース。既存`espnow-link`の3000行固定バッファとは別に保存する。PHYは設定1 Mbps・long preamble、STAモード、APへの接続なし、省電力OFF。測定前にビルド・実機pilot・UART無欠落確認を必要とし、ソースがあるだけでは実測済みと扱わない。

`PEER`、`CHANNEL`、`ROLE`を設定し、送信側`ROLE 2`で`RUN <run_id> <Hz> <秒>`を実行する。応答側は`ROLE 1`。秒数は1〜1200。予定時刻を逃したslotは送信し直してcatch-upせず、未送信として記録する。送信APIエラー、予定未送信、応答欠落、重複を区別する。終了後2秒を応答猶予とする。

Wi-Fi callbackからUARTへ直接書かず、非blocking queueを使う。UARTの各blockは`EVT <byte数> <CRC32>`の行に続いて、16 byteのlittle-endian eventを送る。eventは`[kind, sequence, relative_us, argument]`。

| kind | 内容 | argument |
| --- | --- | --- |
| 1 | 指令のsend API呼出し、送信側時刻 | esp_now_sendの戻り値 |
| 2 | 指令への応答callback、送信側時刻 | 応答に入った元の送信時刻 |
| 3 | 予定送信slotの欠落 | 欠落slot数 |
| 4 | 連続記録の終了 | run_id |

送信時刻と応答時刻は送信側の同じ時計。UART host時刻はSDRとの近似対応にのみ使い、UARTの転送待ちを無線RTTへ含めない。終了marker、全block CRC、`trace_drops == 0`、送信・応答event数とSTATUSカウンタを照合して初めて取得が完全と判断する。queueに捨てたログを無線損失として扱わない。

MAC callback成功／失敗は累積カウンタとして保存する。複数の送信が進行し得るため、MAC callback結果を個々のsequenceに割り当てない。アプリ応答はsequenceと元の送信時刻で照合する。

測定時のv2バイナリ・設定は`binaries/`、SHA256は`binaries/sha256.json`に保存する。両ボードへの書込時に記録した4ファイルのハッシュと一致することを確認した。ソースからの将来の再ビルドが同じバイナリになることまでは保証しない。元のフラッシュ全体のバックアップは非公開保管する。
