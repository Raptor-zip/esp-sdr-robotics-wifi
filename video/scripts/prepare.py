#!/usr/bin/env python3
"""Generate VOICEVOX audio, an exact timeline and views of measured FFT data."""
import argparse
import json
import math
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np
import requests
from PIL import Image

VIDEO = Path(__file__).resolve().parents[1]
REPO = VIDEO.parent
OUT = VIDEO/'public/generated'
FPS = 30
RATE = 24000
HOST = 'http://127.0.0.1:50021'


def normalize(path):
    with wave.open(str(path)) as w:
        sr, ch = w.getframerate(), w.getnchannels()
        a = np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(float)/32768
    chunks = a[:len(a)//480*480].reshape(-1,480)
    levels = np.sqrt(np.mean(chunks**2,axis=1))
    speech = levels[levels>max(levels.max()*0.15,0.002)]
    level = speech.mean()
    a *= 0.15/max(level,1e-6)
    a = .94*np.tanh(a/.94)
    with wave.open(str(path),'wb') as w:
        w.setnchannels(ch);w.setsampwidth(2);w.setframerate(sr)
        w.writeframes((a*32767).astype('<i2').tobytes())


def voices():
    script = json.loads((VIDEO/'src/narration.json').read_text())
    (OUT/'audio').mkdir(parents=True,exist_ok=True)
    frame = 0
    scenes = []
    for index, line in enumerate(script):
        path = OUT/'audio'/f'{line["id"]}.wav'
        query = requests.post(HOST+'/audio_query',params={'speaker':3,'text':line['text']},timeout=120).json()
        query.update(speedScale=1.5,pitchScale=.015,intonationScale=1.2,
                     prePhonemeLength=.045,postPhonemeLength=.07,outputSamplingRate=RATE)
        r = requests.post(HOST+'/synthesis',params={'speaker':3},json=query,timeout=120)
        r.raise_for_status();path.write_bytes(r.content);normalize(path)
        with wave.open(str(path)) as w:
            duration = w.getnframes()/w.getframerate()
        count = math.ceil(duration*FPS)
        if not scenes or scenes[-1]['id']!=line['scene']:
            if scenes:
                frame+=4;scenes[-1]['duration']=frame-scenes[-1]['from']
            scenes.append({'id':line['scene'],'from':frame,'duration':0})
        line.update(fromFrame=frame+2,durationFrames=count,seconds=duration)
        frame+=count+4
        print(line['id'],f'{duration:.2f}s',line['text'],flush=True)
    frame+=12;scenes[-1]['duration']=frame-scenes[-1]['from']
    t={'fps':FPS,'durationInFrames':frame,'speedScale':1.5,
       'engineVersion':requests.get(HOST+'/version',timeout=10).json(),
       'speaker':'VOICEVOX:ずんだもん（ノーマル）','speakerId':3,'scenes':scenes,'lines':script}
    (VIDEO/'src/generated').mkdir(exist_ok=True)
    (VIDEO/'src/generated/timeline.json').write_text(json.dumps(t,ensure_ascii=False,indent=2)+'\n')
    print('Total',round(frame/FPS,3),'seconds',flush=True)


def assets():
    """Input art/fonts stay tracked. Only derived measurement views are ignored."""
    for name in ('noto-sans-jp.woff2',):
        assert (VIDEO/'public/fonts'/name).exists(), f'Missing tracked font input: {name}'
    OUT.mkdir(parents=True,exist_ok=True)
    figures=[('two-team/two-team-blue-green.png','measurement-overview.png'),
             ('coexistence/ble-mutual-narrow-blue-green.png','ble-overview.png'),
             ('receiver/5g-stitch.png','5ghz-overview.png')]
    for rel,name in figures:shutil.copy2(REPO/'experiments/figures'/rel,OUT/name)
    stats=json.loads((REPO/'experiments/data/two-team/summary.json').read_text())
    metrics=[]
    for ch in (6,7,11):
        off,on=[stats[f'team-heavy-ch{ch}-w20-b{x}'] for x in (0,1)]
        metrics.append({'channel':ch,'before':off['pooled_p99_ms'],
                        'after':on['pooled_p99_ms'],
                        'increase':on['pooled_p99_ms']-off['pooled_p99_ms']})
    (VIDEO/'src/generated/metrics.json').write_text(json.dumps(metrics,indent=2)+'\n')
    # The pixel values come from measured FFT bin powers, without synthesizing RF.
    stops=np.array([[7,19,33],[9,44,112],[7,91,204],[0,138,187],[0,189,137],[100,237,105]],float)
    for ch in (6,7,11):
        name=f'team-heavy-ch{ch}-w20-b1-r1'
        z=np.load(REPO/'experiments/data/two-team'/f'{name}-spectrum.npz')
        m=(z['frequency_mhz']>=2410)&(z['frequency_mhz']<=2480)
        p=z['power_dbfs'][:,m]
        rgb=np.stack([np.interp(np.clip((p+90)/45,0,1),np.linspace(0,1,len(stops)),stops[:,c]) for c in range(3)],axis=-1).astype('uint8')
        Image.fromarray(rgb).resize((900,650),Image.Resampling.NEAREST).save(OUT/f'sdr-ch{ch}.png')
        rolling_movie(rgb,OUT/f'sdr-ch{ch}.mp4')
    for mode in ('off','advert','data'):
        z=np.load(REPO/'experiments/data/coexistence'/f'bidirectional-ble-wifiheavy-{mode}-r1-spectrum.npz')
        m=(z['frequency_mhz']>=2450)&(z['frequency_mhz']<=2470)
        p=z['power_dbfs'][:,m]
        rgb=np.stack([np.interp(np.clip((p+90)/30,0,1),np.linspace(0,1,len(stops)),stops[:,c]) for c in range(3)],axis=-1).astype('uint8')
        Image.fromarray(rgb).resize((500,600),Image.Resampling.NEAREST).save(OUT/f'ble-{mode}.png')
    print('Measured SDR images, movies and pooled latency changes prepared.',flush=True)


def rolling_movie(rgb,path):
    width,height=900,600
    rows=160
    proc=subprocess.Popen(['ffmpeg','-v','error','-y','-f','rawvideo','-pixel_format','rgb24',
                          '-video_size',f'{width}x{height}','-framerate','30','-i','-',
                          '-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',
                          '-movflags','+faststart',str(path)],stdin=subprocess.PIPE)
    for frame in range(180):
        stop=int(np.interp(frame,[0,179],[rows,len(rgb)]))
        im=Image.fromarray(rgb[max(0,stop-rows):stop]).resize((width,height),Image.Resampling.NEAREST)
        proc.stdin.write(im.tobytes())
    proc.stdin.close()
    if proc.wait()!=0:raise RuntimeError('Measured waterfall movie encoding failed')


def music():
    t=json.loads((VIDEO/'src/generated/timeline.json').read_text())
    sr=48000;duration=t['durationInFrames']/FPS
    a=np.zeros((int((duration+1)*sr),2),float)
    rng=np.random.default_rng(61);beat=60/148
    # Original synthesized bed, no third-party music samples.
    chords=[(57,60,64),(53,57,60),(48,52,55),(55,59,62)]
    def add(mono,start,level,pan=0):
        i=int(start*sr);j=min(len(a),i+len(mono))
        if j>i:
            a[i:j,0]+=mono[:j-i]*level*(1-pan*.4)
            a[i:j,1]+=mono[:j-i]*level*(1+pan*.4)
    for b in range(math.ceil((duration+1)/beat)):
        chord=chords[(b//8)%4]
        q=np.arange(int(sr*.15))/sr
        kick=np.sin(2*np.pi*(65*q+4*(1-np.exp(-q*28))))*np.exp(-q*30)
        if b%2==0:add(kick,b*beat,.045)
        q=np.arange(int(sr*.07))/sr;noise=rng.normal(0,1,len(q));noise=np.diff(noise,prepend=0)*np.exp(-q*90)
        add(noise,b*beat+beat*.5,.006,(-1)**b)
        for offset in (0,.5):
            note=chord[(b+int(offset*2))%3]+12
            hz=440*2**((note-69)/12);q=np.arange(int(sr*.27))/sr
            pluck=(np.sin(2*np.pi*hz*q)+.18*np.sin(4*np.pi*hz*q))*np.exp(-q*14)
            add(pluck,(b+offset)*beat,.019,(-1)**b*.5)
        if b%4==0:
            hz=440*2**((chord[0]-12-69)/12);q=np.arange(int(sr*beat*2))/sr
            add(np.sin(2*np.pi*hz*q)*np.sin(np.pi*np.clip(q/(beat*2),0,1))**2,b*beat,.025)
    a*=np.minimum(1,np.arange(len(a))/(sr*.15))[:,None]
    tail=np.clip((duration-np.arange(len(a))/sr)/.5,0,1);a*=tail[:,None]
    write_wave(OUT/'music.wav',a,sr)
    q=np.arange(int(.13*sr))/sr
    pop=np.sin(2*np.pi*(760*q-1100*q*q))*np.exp(-q*35)*.065
    write_wave(OUT/'pop.wav',pop,sr)
    print('Original music bed and transition sound prepared.',flush=True)


def write_wave(path,a,sr):
    with wave.open(str(path),'wb') as w:
        w.setnchannels(1 if a.ndim==1 else a.shape[1]);w.setsampwidth(2);w.setframerate(sr)
        w.writeframes((np.clip(a,-1,1)*32767).astype('<i2').tobytes())


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--only',choices=['voices','assets','music']);args=parser.parse_args()
    for key,fn in [('voices',voices),('assets',assets),('music',music)]:
        if not args.only or args.only==key:fn()
