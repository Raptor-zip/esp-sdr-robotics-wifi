#!/usr/bin/env python3
"""Normalize the final audio, export two H.264 copies and write subtitles."""
import json,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'out'
timeline=json.loads((ROOT/'src/generated/timeline.json').read_text())


def run(*cmd):
    subprocess.run(list(cmd),check=True)


def timestamp(frame):
    ms=round(frame/30*1000)
    hours,ms=divmod(ms,3600000);minutes,ms=divmod(ms,60000);seconds,ms=divmod(ms,1000)
    return f'{hours:02}:{minutes:02}:{seconds:02},{ms:03}'


def main():
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
    run('ffmpeg','-v','error','-y','-i',str(OUT/'master.mp4'),'-c:v','copy','-af',af,
        '-c:a','aac','-b:a','192k','-ar','48000','-movflags','+faststart',str(OUT/'wifi-robocon-short.mp4'))
    run('ffmpeg','-v','error','-y','-i',str(OUT/'wifi-robocon-short.mp4'),'-c:v','libx264',
        '-preset','slow','-crf','23','-maxrate','6M','-bufsize','12M','-pix_fmt','yuv420p',
        '-c:a','copy','-movflags','+faststart',str(OUT/'wifi-robocon-short-x.mp4'))
    subtitles=[]
    for i,line in enumerate(timeline['lines'],1):
        subtitles.append(f'{i}\n{timestamp(line["fromFrame"])} --> {timestamp(line["fromFrame"]+line["durationFrames"])}\n{line["caption"]}\n')
    (OUT/'wifi-robocon-short.srt').write_text('\n'.join(subtitles))
    run('ffmpeg','-v','error','-y','-ss','2.8','-i',str(OUT/'wifi-robocon-short.mp4'),
        '-frames:v','1',str(OUT/'cover.png'))
    manifest={'seconds':duration,'width':1080,'height':1920,'fps':30,'voice':'VOICEVOX:ずんだもん',
              'speedScale':1.5,'engineVersion':timeline['engineVersion'],
              'files':[{ 'name':name,'bytes':(OUT/name).stat().st_size}
                        for name in ('wifi-robocon-short.mp4','wifi-robocon-short-x.mp4','wifi-robocon-short.srt','cover.png')],
              'loudness_before_normalization':measured,
              'notes':'FFT image values are measured. Manim diagrams are illustrative. Acquisition playback omits unrecorded RF intervals.'}
    (OUT/'delivery.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(manifest,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
