import React from 'react';
import {AbsoluteFill, Audio, Img, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {loadFont} from '@remotion/fonts';
import timeline from './generated/timeline.json';
import clips from './generated/clips.json';

export const fontReady=loadFont({family:'Noto',url:staticFile('fonts/noto-sans-jp.woff2')});
const C={paper:'#FFFDF8',ink:'#242721',blue:'#2167AD',green:'#38754B',red:'#CC4935',gold:'#A76B14',muted:'#71736C'};
const FONT='Noto, sans-serif';
const clamp={extrapolateLeft:'clamp',extrapolateRight:'clamp'} as const;
type SceneId=typeof timeline.scenes[number]['id'];

const Manim:React.FC<{name:keyof typeof clips;duration:number}>=({name,duration})=><OffthreadVideo
 src={staticFile(`generated/${name}.mp4`)} muted playbackRate={clips[name]/(duration/30)}
 style={{position:'absolute',inset:0,width:'100%',height:'100%',objectFit:'contain'}}/>;

const Waterfall:React.FC<{channel:number;height:number;duration?:number;moving?:boolean}>=({channel,height,duration=180,moving=false})=><div style={{height,overflow:'hidden',borderRadius:5}}>
 {moving?<OffthreadVideo src={staticFile(`generated/sdr-ch${channel}.mp4`)} muted playbackRate={180/duration} style={{width:'100%',height:'100%',objectFit:'fill'}}/>
 :<Img src={staticFile(`generated/sdr-ch${channel}.png`)} style={{width:'100%',height:'100%',objectFit:'fill'}}/>}
</div>;

const Sensor:React.FC<{duration:number}>=({duration})=><>
 <Manim name="SensorPipeline" duration={duration}/>
 <div style={{position:'absolute',left:65,top:960,width:950}}>
  <div style={{fontSize:42,fontWeight:900,color:C.green,marginBottom:18}}>実測FFT電力</div>
  <Waterfall channel={6} moving duration={duration} height={710}/>
  <div style={{display:'flex',justifyContent:'space-between',fontSize:37,color:C.ink,marginTop:18}}><span>2410</span><span>2440</span><span>2480 MHz</span></div>
  <div style={{display:'flex',alignItems:'center',justifyContent:'center',gap:22,fontSize:37,marginTop:28}}><span style={{color:C.blue}}>青：弱い</span><div style={{width:300,height:19,background:'linear-gradient(90deg,#075BCC,#008ABB,#64ED69)'}}/><span style={{color:C.green}}>緑：強い</span></div>
 </div>
</>;

const Results:React.FC<{duration:number}>=({duration})=><>
 <Manim name="LatencyBars" duration={duration}/>
 <div style={{position:'absolute',left:55,top:115,width:970,display:'flex',gap:16}}>{[6,7,11].map((ch,i)=><div key={ch} style={{flex:1}}>
  <div style={{fontSize:39,fontWeight:900,color:[C.red,C.gold,C.green][i],textAlign:'center',marginBottom:22}}>{['同一','隣接','分離'][i]} Ch{ch}</div>
  <Waterfall channel={ch} height={300}/>
 </div>)}</div>
</>;

const Radios:React.FC<{duration:number}>=({duration})=><>
 <Manim name="RadioProtocols" duration={duration}/>
 <div style={{position:'absolute',left:55,top:1090,width:970}}>
  <div style={{display:'flex',gap:20}}>{['off','data'].map((mode,i)=><div key={mode} style={{flex:1}}>
   <div style={{fontSize:38,fontWeight:900,color:i?C.green:C.muted,marginBottom:20}}>{i?'BLE接続通知':'BLE停止'}</div>
   <Img src={staticFile(`generated/ble-${mode}.png`)} style={{width:'100%',height:415,objectFit:'fill',borderRadius:5}}/>
  </div>)}</div>
  <div style={{fontSize:36,color:C.muted,textAlign:'center',marginTop:23}}>2450–2470 MHz · 実測FFT</div>
  <div style={{fontSize:44,fontWeight:900,color:C.ink,textAlign:'center',marginTop:40}}>Wi-Fi指令：20 ms超過</div>
  <div style={{fontSize:67,fontWeight:900,color:C.red,textAlign:'center',marginTop:10}}>0.067 → 0.483%</div>
 </div>
</>;

const End:React.FC<{duration:number}>=({duration})=>{
 const f=useCurrentFrame();
 return <>
 {['他チームと\n帯域を分ける','映像・点群の\n量を見直す','指令の遅れ・欠落を\n測る'].map((t,i)=>{
  const p=interpolate(f,[i*22,i*22+12],[0,1],clamp);
  return <div key={t} style={{position:'absolute',left:70,top:225+i*265,width:940,display:'flex',alignItems:'center',gap:34,opacity:p,transform:`translateY(${(1-p)*25}px)`}}>
   <div style={{fontSize:114,color:C.green,fontWeight:900,width:100}}>{i+1}</div>
   <div style={{fontSize:66,fontWeight:900,lineHeight:1.35,color:C.ink}}>{t.split('\n').map(l=><div key={l}>{l}</div>)}</div>
  </div>;
 })}
 <div style={{position:'absolute',left:65,top:1160,width:950,display:'flex',gap:18}}>{[6,7,11].map((ch,i)=><div key={ch} style={{flex:1}}>
  <div style={{fontSize:40,fontWeight:900,color:[C.red,C.gold,C.green][i],marginBottom:22,textAlign:'center'}}>Ch{ch}</div>
  <Waterfall channel={ch} height={510} moving duration={duration}/>
 </div>)}</div>
 </>;
};

const Scene:React.FC<{id:SceneId;duration:number}>=({id,duration})=>{
 const f=useCurrentFrame();
 let body:React.ReactNode;
 switch(id){
  case 'hook':body=<Manim name="RadioField" duration={duration}/>;break;
  case 'sensor':body=<Sensor duration={duration}/>;break;
  case 'overlap':body=<Manim name="ChannelOverlap" duration={duration}/>;break;
  case 'results':body=<Results duration={duration}/>;break;
  case 'width':body=<Manim name="Bandwidth" duration={duration}/>;break;
  case 'queue':body=<Manim name="QueueSplit" duration={duration}/>;break;
  case 'radios':body=<Radios duration={duration}/>;break;
  case 'sampling':body=<Manim name="Sampling" duration={duration}/>;break;
  case 'end':body=<End duration={duration}/>;break;
 }
 return <AbsoluteFill style={{opacity:id==='hook'?1:interpolate(f,[0,4],[0,1],clamp)}}>{body}</AbsoluteFill>;
};

export const Short:React.FC=()=> <AbsoluteFill style={{fontFamily:FONT,background:C.paper,color:C.ink}}>
 {timeline.scenes.map(s=><Sequence key={s.id} from={s.from} durationInFrames={s.duration}><Scene id={s.id} duration={s.duration}/></Sequence>)}
 <Audio src={staticFile('generated/music.wav')} volume={.82}/>
 {timeline.scenes.map(s=><Sequence key={'pop'+s.id} from={s.from} durationInFrames={5}><Audio src={staticFile('generated/pop.wav')} volume={.7}/></Sequence>)}
 {timeline.lines.map(l=><Sequence key={l.id} from={l.fromFrame} durationInFrames={l.durationFrames}><Audio src={staticFile(`generated/audio/${l.id}.wav`)}/></Sequence>)}
</AbsoluteFill>;
