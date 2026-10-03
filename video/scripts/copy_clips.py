#!/usr/bin/env python3
"""Publish generated Manim clips and their exact durations to Remotion."""
import json,shutil,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
names=['RadioField','SensorPipeline','ChannelOverlap','LatencyBars','Bandwidth','QueueSplit','RadioProtocols','Sampling']
durations={}
for name in names:
 src=root/'out/manim/videos/diagrams/1920p30'/f'{name}.mp4'
 dest=root/'public/generated'/src.name
 assert src.exists(),name
 shutil.copy2(src,dest)
 durations[name]=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(dest)],text=True).strip())
(root/'src/generated/clips.json').write_text(json.dumps(durations,indent=2)+'\n')
print(durations)
