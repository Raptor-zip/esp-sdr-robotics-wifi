#!/usr/bin/env python3
"""Normalize the final audio and export one H.264 file without subtitles."""
import json,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'out'
timeline=json.loads((ROOT/'src/generated/timeline.json').read_text())


def run(*cmd):
    subprocess.run(list(cmd),check=True)


def main():
    # Same-name sidecars can be loaded automatically by a local video player.
    for stem in ('wifi-robocon-short','wifi-robocon-short-x',
                 'wifi-robocon-short-no-subs','wifi-robocon-short-x-no-subs'):
        for extension in ('srt','vtt','ass'):
            (OUT/f'{stem}.{extension}').unlink(missing_ok=True)
    for name in ('wifi-robocon-short-x.mp4', 'wifi-robocon-short-x-no-subs.mp4'):
        (OUT/name).unlink(missing_ok=True)
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams',
                                            '-of','json',str(OUT/'master.mp4')],text=True))
    duration=float(probe['format']['duration'])
    assert duration<60,duration
    # Two-pass loudness correction keeps synthetic speech and music consistent.
    result=subprocess.run(['ffmpeg','-hide_banner','-i',str(OUT/'master.mp4'),'-af',
        'loudnorm=I=-14:TP=-1.5:LRA=8:print_format=json','-f','null','-'],capture_output=True,text=True,check=True)
    measured=json.loads(result.stderr[result.stderr.rfind('{'):])
    af=('loudnorm=I=-14:TP=-1.5:LRA=8:linear=true:measured_I='+measured['input_i']
        +':measured_TP='+measured['input_tp']+':measured_LRA='+measured['input_lra']
        +':measured_thresh='+measured['input_thresh']+':offset='+measured['target_offset'])
    run('ffmpeg','-v','error','-y','-i',str(OUT/'master.mp4'),'-map','0:v:0','-map','0:a:0','-sn','-c:v','copy','-af',af,
        '-c:a','aac','-b:a','192k','-ar','48000','-movflags','+faststart',str(OUT/'wifi-robocon-short-no-subs.mp4'))
    cover_scene=next(s for s in timeline['scenes'] if s['id']=='hook')
    cover_time=(cover_scene['from']+int(cover_scene['duration']*.65))/30
    run('ffmpeg','-v','error','-y','-ss',str(cover_time),'-i',str(OUT/'wifi-robocon-short-no-subs.mp4'),
        '-frames:v','1',str(OUT/'cover.png'))
    manifest={'seconds':duration,'width':1080,'height':1920,'fps':30,'voice':'VOICEVOX:ずんだもん',
              'speedScale':1.5,'engineVersion':timeline['engineVersion'],
              'visual_mode':'content-only','manim_diagrams':8,
              'captions_burned_in':False,'subtitle_sidecars':False,'character_overlay':False,
              'supplied_images':['robot-competition.jpg','wifi-router.jpg','competition-wifi-analyzer.png'],
              'files':[{ 'name':name,'bytes':(OUT/name).stat().st_size}
                        for name in ('wifi-robocon-short-no-subs.mp4','cover.png')],
              'loudness_before_normalization':measured,
              'notes':'FFT image values are measured. Manim diagrams are illustrative. Acquisition playback omits unrecorded RF intervals.'}
    (OUT/'delivery.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(manifest,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
