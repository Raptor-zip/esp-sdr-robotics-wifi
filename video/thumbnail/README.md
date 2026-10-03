# YouTubeサムネイル

`youtube-wifi-interference.jpg`（投稿用）と `youtube-wifi-interference.png`（保存用）：横16:9、1672×941。明るい写真合成と大きな日本語見出し。

提供された実物ロボット写真と、室内SDR取得画像を参考に内蔵imagegenで制作した告知画像。図や配置は編集表現で、科学データの原本として使わない。元画像は `../public/input/robot-competition.jpg` と `../public/generated/sdr-ch6.png`。

見出し、日本語表記、対象機器の外観を目視確認した。選択した完成画像は追跡し、再生成時は別名で保存する。

生成プロンプト：

```text
Create a finished, exceptionally attention-grabbing Japanese YouTube thumbnail for a fast 58-second robotics Wi-Fi explainer. Edit/composite these two source images into ONE landscape 16:9 thumbnail, ideally 1920x1080. Use case: ads-marketing, photomontage editorial thumbnail.
Input image 1: the USER'S REAL STUDENT ROBOCON ROBOT photograph. Cut out this exact robot from its room background, preserving all physical geometry, red faceted panels, white markings, wheels, exposed wiring and antenna/sensor hardware. It must remain this photographed machine, not an illustrated or invented robot. Dominant hero robot occupies the right half, dynamic slight tilt, photographic detail, bold white cutout outline. Do not invent damage, fire, smoke, crashes, or show it as actually broken.
Input image 2: genuine blue and green measured SDR waterfall. Use a substantial rectangular inset in lower left, exact scientific image as supplied, only resizing/cropping permitted. Don't repaint it, add fake signals, invent numbers, or make the robot appear experimentally measured in the same setup. Label the inset "実測SDR".
HEADLINE exact Japanese typography, very large extra-black condensed Japanese sans, left/top, 2 lines: "そのWi-Fi、" and "かぶってる！". First line nearly black; second vivid vermilion with thick off-white outline. Must be perfectly spelled and legible at smartphone size; don't add small prose.
Small but readable top-left context label: "ロボコン × 無線干渉". Small badge near waterfall: "ESP32-C5で可視化".
Composition cohesive and energetic, NOT a two-panel comparison. Large bold coral overlapping Wi-Fi arcs behind the robot plus one graphic arrow toward the waterfall, understood as editorial schematic decoration. Bright warm ivory paper/cream background, bold sunny yellow shape accents and vermilion, authentic blue-green only in waterfall. Japanese enthusiast/maker magazine feel, punchy clean cut-paper collage with subtle halftone accents, purposeful asymmetric layout, contrast and breathing room. No dark mode, black background, neon purple gradients, lens glow, AI cyberpunk feel. No people, faces, presenter, anime character, invented logos, personal names, watermarks, percentage claims, dates or URLs. Text and robot don't obscure waterfall's central measured bands. All important elements well inside edges with safe margins.
```
