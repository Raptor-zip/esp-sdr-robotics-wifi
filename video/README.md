# ESP32-C5とロボコン通信のショート動画

54.8秒、1080×1920、30 fps。Remotionで合成し、Manimによる8本の縦画面図解と、実測FFTの画像・動く取得列を組み合わせる。
音声はVOICEVOXずんだもん（ノーマル、話者ID 3）、`speedScale=1.5`。各場面は音声ファイルの実測長に同期する。
白地・黒文字・朱色・青を基本とし、実測スペクトルの青緑だけを受信強度の色尺度として使う。
図解と測定画像のみを画面いっぱいに構成する。タイトル帯・章番号・字幕枠・立ち絵・画面外注記は表示しない。

## 書き出し

必要環境：Node.js、npm、uv、Python 3.12、FFmpeg、Cairo／Pango、Noto Sans CJK JP。
VOICEVOX Engineを `http://127.0.0.1:50021` で起動しておく。

```bash
bash video/scripts/build.sh --stills # 音声・素材・Manim・代表フレームまで
bash video/scripts/build.sh          # 字幕なし動画、軽量版、表紙も生成
```

全工程の再実行が不要な場合：

```bash
cd video
npm run dev         # Remotion Studio
npm run check
npm run stills
npm run render
.venv/bin/python scripts/deliver.py
.venv/bin/python scripts/verify.py
```

`out/wifi-robocon-short-no-subs.mp4` は高画質版、`out/wifi-robocon-short-x-no-subs.mp4` は軽量版。
両方ともH.264／AAC、先頭に再生メタデータを配置する。字幕の焼き込みは行わない。
字幕ファイルは生成せず、旧版の同名SRT／VTT／ASSも書き出し時に削除する。表紙は `out/cover.png`。
`verify.py` は両MP4を最後までデコードし、尺・解像度・音声・先頭メタデータ・字幕トラックと同名字幕ファイルの不在を検査する。
実際の動画から冒頭・末尾・各場面の確認画像を `out/final-review/` に書き出す。

## 内容と根拠

| 場面 | 内容 | 根拠 |
| --- | --- | --- |
| 1–2 | Wi-Fiが重なる導入、ESP32-C5の受信画像 | 実測I/QからのFFT。機器・経路は模式図 |
| 3 | Ch6とCh7の中心差5 MHz、名目幅20 MHz | 周波数に対応するManim図解 |
| 4 | 他チームの追加負荷によるp99増分、約23／9／1 ms | `experiments/data/two-team/summary.json`、Ch6/7/11の負荷−待機。3反復の統合値 |
| 5 | Ch1・20→40 MHzの名目帯域の拡大 | 主Ch1＋上側副Ch5。遅延は単純には悪化しなかった |
| 6 | 自チームの映像・点群を載せた場合も指令が悪化 | ROS 2の合成Image／PointCloud2。待ち行列は原因候補の模式図 |
| 7 | ESP-NOWは固定、BLE接続データはホッピング | 独立リンクの共存系列。Wi-Fi20 ms超過0.067→0.483%は端末ログの3反復平均 |
| 8 | 1行約205 µsの間欠取得 | 80 MS/s、16,380 I/Q。50 ms間隔の図は説明用の例 |
| 9 | 帯域分離、データ量、指令遅延の確認 | 上記の室内・固定配置の比較に基づく運用上の考察 |

図4の値は全往復遅延ではなく、他チーム負荷を追加した時の増分。分離後もp99約127 msが残る。
他チームの実受信量は条件によって異なる。約23／9／1 msを任意の機器・会場での保証値にはしない。
SDR動画は保存した短い取得列の表示で、未記録時間を省いている。実時間の連続受信を再構成していない。
BLE拡大画像は2450–2470 MHzで、Wi-Fi Ch6帯域と広告3周波数の外。細線から干渉や成功率を算出しない。

## 入力素材と生成物

`public/fonts/` のフォントと、初稿用に取得した `public/character/` の立ち絵は入力素材として追跡する。現在の動画では立ち絵を使用しない。
`public/generated/` の音声・FFT画像・Manimクリップと `src/generated/` の尺台帳は、コードと実測データから再生成する。
`out/`、依存関係、仮想環境を含め、これらの生成物のみGitで無視する。

音声クレジット：VOICEVOX：ずんだもん。
素材の出典は各入力ディレクトリのクレジットを参照。音声クレジットは投稿文へ記載する。BGMと効果音はこの制作コードによる合成音である。

参照：
[VOICEVOX利用規約](https://voicevox.hiroshiba.jp/term/) ·
[キャラクター素材ガイドライン](https://zunko.jp/guideline.html) ·
[Remotion](https://www.remotion.dev/docs/) ·
[Manim](https://docs.manim.community/)
