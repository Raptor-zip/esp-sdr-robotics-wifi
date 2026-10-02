# 実験資料

実験日によるフォルダー分けを廃止し、`data`・`figures`・`scripts`・`firmware`に統合しています。レポートのLaTeXはリポジトリ直下の`reports/full.tex`と`reports/twitter.tex`の2本です。

- `baseline`: チャネル、負荷、ゲイン、サンプルレート、FFT長、5 GHzの基礎観測。
- `receiver`: LO応答、送信電力設定、間欠サンプリング、PCAP時刻照合、BLE、5 GHz分割取得などの補足評価。
- `robotics`: 操縦相当UDPと同じAPの負荷、独立APの同一・隣接・分離チャネル、20/40 MHz比較。

[条件](../docs/experiments.md) · [データ形式](../docs/data-format.md) · [再生成方法](../docs/reproduction.md)
