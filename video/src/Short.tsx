import React from 'react';
import {AbsoluteFill, Audio, Easing, Img, OffthreadVideo, Sequence, interpolate,
  spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {loadFont} from '@remotion/fonts';
import timeline from './generated/timeline.json';
import metrics from './generated/metrics.json';
import clips from './generated/clips.json';

export const fontReady = Promise.all([
  loadFont({family:'Dela',url:staticFile('fonts/DelaGothicOne-Regular.ttf')}),
  loadFont({family:'Noto',url:staticFile('fonts/noto-sans-jp.woff2')}),
]);
const C={bg:'#FAF7F0',panel:'#FFFDF8',ink:'#242721',blue:'#2167AD',green:'#38754B',red:'#CC4935',gold:'#A76B14',muted:'#71736C'};
const FONT='Noto, sans-serif';
const HEAD='Dela, Noto, sans-serif';
type SceneId = typeof timeline.scenes[number]['id'];
const clamp={extrapolateLeft:'clamp',extrapolateRight:'clamp'} as const;
const ease=Easing.bezier(.16,1,.3,1);
const enter=(f:number,delay=0)=>interpolate(f,[delay,delay+12],[0,1],{...clamp,easing:ease});

const CONTENT:Record<string,{title:string[];tag:string;accent:string;note:string}>= {
 hook:{title:['チャンネル変えた。','でも、ラグい。'],tag:'01 / 見えない重なり',accent:C.red,note:'通信経路の模式図｜同じWi-Fiに指令・映像・点群'},
 sensor:{title:['見えない電波を、','見える化。'],tag:'02 / ESP32-C5 × SDR',accent:C.green,note:'実測FFT電力｜共通色尺度 −90〜−45 dBFS（未校正）'},
 overlap:{title:['番号が違う。','でも帯域は重なる。'],tag:'03 / チャネルの落とし穴',accent:C.gold,note:'名目20 MHzの模式図｜周波数の重なりは縮尺に対応'},
 results:{title:['他チームの通信で','指令はどれだけ遅れる。'],tag:'04 / 重い通信 × 重い通信',accent:C.red,note:'自Ch6・20 MHz／TCP負荷／各30秒×3反復｜室内・固定配置'},
 width:{title:['帯域幅を2倍。','重なりも広がる。'],tag:'05 / 20 MHz → 40 MHz',accent:C.gold,note:'自Ch6／他Ch1＋副Ch5｜実受信量も変化した比較'},
 queue:{title:['分離した。','それでも遅れる。'],tag:'06 / 自チームの負荷も見る',accent:C.red,note:'待ち行列は模式図・原因候補｜実ROS 2で模擬画像・点群を追加'},
 radios:{title:['固定とホッピング。','どちらも油断できない。'],tag:'07 / ESP-NOW ＋ BLE',accent:C.blue,note:'独立リンク／端末ログ3反復平均（BLE停止→接続通知）｜ホッピングは模式図'},
 sampling:{title:['1行は約205 µs。','時間の大半は未記録。'],tag:'08 / 画像の読み方',accent:C.gold,note:'80 MS/sのI/Q取得｜色だけで衝突や通信成功を判断しない'},
 end:{title:['速度だけでなく、','指令の遅れを測る。'],tag:'09 / ロボコンで使うなら',accent:C.green,note:'構成・負荷・配置に依存する室内結果｜詳細な条件は論文へ'},
};

const SmallTag:React.FC<{children:React.ReactNode;color?:string}>=({children,color=C.blue})=><div style={{display:'inline-flex',alignItems:'center',padding:'11px 19px',border:`2px solid ${color}`,borderRadius:5,color,background:'#fffdf8',fontSize:29,fontWeight:900,letterSpacing:.5}}>{children}</div>;

const ManimClip:React.FC<{name:keyof typeof clips;duration:number;style?:React.CSSProperties}>=({name,duration,style})=><OffthreadVideo src={staticFile(`generated/${name}.mp4`)} muted
 playbackRate={clips[name]/(duration/30)} style={{width:'100%',height:'100%',objectFit:'contain',...style}}/>;

const Legend:React.FC<{narrow?:boolean}>=({narrow})=><div style={{display:'flex',gap:18,alignItems:'center',fontSize:27,color:C.muted,justifyContent:'center'}}>
 <span>弱い</span><div style={{width:340,height:14,borderRadius:7,background:'linear-gradient(90deg,#071321,#075bcc,#008abb,#64ed69)'}}/><span>強い</span><span style={{fontSize:23}}>−90 → {narrow?'−60':'−45'} dBFS</span>
</div>;

const Spectrum:React.FC<{channel?:number;moving?:boolean;duration?:number;height?:number}>=({channel=6,moving=false,duration=180,height=550})=>{
 const f=useCurrentFrame();
 return <div style={{position:'relative',height,margin:'0 20px',background:C.panel,border:`1px solid ${C.blue}50`,overflow:'hidden',borderRadius:12}}>
 {moving?<OffthreadVideo src={staticFile(`generated/sdr-ch${channel}.mp4`)} muted playbackRate={180/duration} style={{width:'100%',height:'100%',objectFit:'fill'}}/>:<Img src={staticFile(`generated/sdr-ch${channel}.png`)} style={{width:'100%',height:'100%',objectFit:'fill'}}/>}
 {[2427,2447].map(x=><div key={x} style={{position:'absolute',top:0,bottom:0,left:`${(x-2410)/70*100}%`,borderLeft:'2px dashed rgba(255,255,255,.65)'}}/>)}
 <div style={{position:'absolute',top:20,left:20,fontSize:27,fontWeight:800,color:'white',background:'#071321bb',padding:'7px 12px',borderRadius:8}}>実測 · 他チームCh{channel}</div>
 {moving&&<div style={{position:'absolute',right:16,bottom:18,fontSize:24,background:'#071321dd',padding:9,borderRadius:8,color:C.muted}}>保存した取得列を順に表示</div>}
 </div>;
};

const C5Chip:React.FC=()=> <svg width="158" height="160" viewBox="0 0 160 160">
 {Array.from({length:7},(_,i)=><g key={i} stroke={C.green} strokeWidth="6"><path d={`M ${28+i*17} 5 v18 M ${28+i*17} 137 v18 M 5 ${28+i*17} h18 M 137 ${28+i*17} h18`}/></g>)}
 <rect x="23" y="23" width="114" height="114" rx="10" fill="#EAF0E2" stroke={C.green} strokeWidth="4"/>
 <text x="80" y="77" fill={C.ink} textAnchor="middle" style={{fontFamily:FONT,fontSize:18,fontWeight:900}}>ESP32</text><text x="80" y="113" fill={C.green} textAnchor="middle" style={{fontFamily:HEAD,fontSize:40}}>C5</text>
 </svg>;

const Hook:React.FC<{duration:number}>=({duration})=>{
 const f=useCurrentFrame();return <>
 <div style={{height:730}}><ManimClip name="RadioField" duration={duration}/></div>
 <div style={{position:'absolute',left:140,right:140,bottom:38,textAlign:'center',transform:`scale(${spring({frame:f-67,fps:30,config:{damping:12,stiffness:190}})})`,fontFamily:HEAD,fontSize:73,color:C.red}}>まだ、重なってる。</div>
 </>;
};

const Sensor:React.FC<{duration:number}>=({duration})=>{
 const f=useCurrentFrame();return <>
 <div style={{display:'flex',gap:30,alignItems:'center',padding:'26px 28px 20px',height:180}}><C5Chip/><div><div style={{color:C.green,fontFamily:HEAD,fontSize:48}}>ESP32-C5-WROOM-1</div><div style={{fontSize:31,color:C.muted,marginTop:12}}>I/Qを取得 → FFTで周波数別に表示</div></div></div>
 <div style={{transform:`scale(${1+interpolate(f,[0,duration],[0,.025],clamp)})`}}><Spectrum moving duration={duration} height={480}/></div>
 <div style={{display:'flex',justifyContent:'space-between',padding:'12px 26px',fontSize:29,color:C.muted}}><span>2410</span><span>2440</span><span>2480 MHz</span></div><Legend/>
 <div style={{fontSize:26,color:C.muted,textAlign:'center',marginTop:15}}>取得番号で表示／連続したRF時間の再生ではない</div>
 </>;
};

const Results:React.FC=()=>{
 const f=useCurrentFrame();return <>
 <div style={{display:'flex',gap:12,padding:'20px 20px 0'}}>{[6,7,11].map((c,i)=><div key={c} style={{flex:1}}><div style={{textAlign:'center',fontWeight:900,fontSize:30,color:[C.red,C.gold,C.green][i],marginBottom:12}}>{['同一','隣接','分離'][i]} Ch{c}</div><div style={{height:150,overflow:'hidden',borderRadius:5}}><Img src={staticFile(`generated/sdr-ch${c}.png`)} style={{width:'100%',height:'100%',objectFit:'fill'}}/></div></div>)}</div>
 <div style={{fontWeight:900,fontSize:43,color:C.ink,margin:'28px 25px 4px'}}>他チーム負荷による追加遅延</div>
 <div style={{fontSize:26,color:C.muted,margin:'0 25px 16px'}}>往復応答のRTT p99差（99%点）・3反復を統合</div>
 {metrics.map((m,i)=>{const p=enter(f,99+i*17);return <div key={m.channel} style={{display:'flex',alignItems:'center',height:100,padding:'0 26px',gap:18}}>
 <div style={{fontSize:36,fontWeight:900,width:136,color:[C.red,C.gold,C.green][i]}}>{['同一','隣接','分離'][i]}<div style={{fontSize:29}}>Ch{m.channel}</div></div>
 <div style={{width:410,position:'relative',height:42,background:'#E7E4DC',borderRadius:4}}><div style={{height:'100%',width:Math.max(8,m.increase/23*410)*p,background:[C.red,C.gold,C.green][i],borderRadius:4}}/></div>
 <div style={{fontFamily:HEAD,fontSize:68,color:[C.red,C.gold,C.green][i],opacity:p}}>+{Math.round(m.increase)}<span style={{fontFamily:FONT,fontSize:32}}> ms</span></div>
 </div>})}
 <div style={{margin:'18px 25px 0',padding:'16px 18px',borderRadius:6,color:C.ink,background:'#FBECC6',border:'1px solid #B88A36',fontSize:32,fontWeight:900}}>追加 +1 ms ≠ 応答 1 ms<div style={{fontSize:28,fontWeight:600,marginTop:6,color:C.muted}}>分離後もRTT p99 約127 ms。元の遅延は残る。</div></div>
 </>;
};

const Radios:React.FC<{duration:number}>=({duration})=><>
 <div style={{height:550}}><ManimClip name="RadioProtocols" duration={duration}/></div>
 <div style={{display:'flex',gap:14,margin:'-2px 26px 0',alignItems:'center'}}>{['off','data'].map((mode,i)=><div key={mode} style={{flex:1}}><div style={{fontSize:28,fontWeight:900,color:i?C.green:C.muted,marginBottom:8}}>{i?'BLE接続通知':'BLE停止'} · 実測</div><Img src={staticFile(`generated/ble-${mode}.png`)} style={{width:'100%',height:100,objectFit:'fill',borderRadius:5}}/></div>)}</div>
 <div style={{fontSize:23,color:C.muted,textAlign:'center',marginTop:11}}>2450–2470 MHz拡大／広告3周波数・Wi-Fi Ch6帯域の外</div>
 <div style={{fontSize:29,fontWeight:900,color:C.red,textAlign:'center',marginTop:13}}>Wi-Fi指令20 ms超過：0.067 → 0.483%</div>
 </>;

const End:React.FC=()=>{
 const f=useCurrentFrame();return <>
 {['他チームと帯域を分ける','映像・点群の量を見直す','指令の遅れ・欠落を測る'].map((t,i)=><div key={t} style={{display:'flex',gap:24,alignItems:'center',margin:'25px 24px',padding:'28px 24px',background:'#EAF0E2',border:'1px solid #AABB9F',borderRadius:8,opacity:enter(f,i*19),transform:`translateY(${(1-enter(f,i*19))*26}px)`}}><div style={{fontFamily:HEAD,fontSize:57,color:C.green}}>{i+1}</div><div style={{fontWeight:900,fontSize:47,color:C.ink}}>{t}</div></div>)}
 <div style={{display:'flex',gap:12,margin:'38px 26px 0'}}>{[6,7,11].map(c=><Img key={c} src={staticFile(`generated/sdr-ch${c}.png`)} style={{flex:1,width:255,height:146,objectFit:'cover',borderRadius:10}}/>)}</div>
 <div style={{fontFamily:HEAD,fontSize:44,color:C.green,textAlign:'center',marginTop:36}}>詳しい条件・結果は論文へ</div>
 </>;
};

const Scene:React.FC<{id:SceneId;duration:number}>=({id,duration})=>{
 const f=useCurrentFrame();const info=CONTENT[id];
 const body=()=>{
 switch(id){
  case 'hook':return <Hook duration={duration}/>;
  case 'sensor':return <Sensor duration={duration}/>;
  case 'results':return <Results/>;
  case 'overlap':return <ManimClip name="ChannelOverlap" duration={duration}/>;
  case 'width':return <ManimClip name="Bandwidth" duration={duration}/>;
  case 'queue':return <><ManimClip name="QueueSplit" duration={duration}/><div style={{position:'absolute',left:30,right:30,bottom:25,fontSize:29,fontWeight:900,color:C.gold,textAlign:'center'}}>模擬Image・PointCloud2追加で指令が悪化</div></>;
  case 'radios':return <Radios duration={duration}/>;
  case 'sampling':return <ManimClip name="Sampling" duration={duration}/>;
  case 'end':return <End/>;
  default:return null;
 }};
 return <AbsoluteFill style={{opacity:id==='hook'?1:enter(f),transform:`translateY(${id==='hook'?0:(1-enter(f))*24}px)`}}>
  <div style={{position:'absolute',top:198,left:70,right:88}}><SmallTag color={info.accent}>{info.tag}</SmallTag><div style={{fontFamily:HEAD,fontSize:id==='results'?77:79,lineHeight:1.28,marginTop:23,color:C.ink,letterSpacing:-2}}>{info.title.map((l,i)=><div key={l} style={{color:i===1?info.accent:C.ink,whiteSpace:'nowrap'}}>{l}</div>)}</div></div>
  <div style={{position:'absolute',left:62,top:510,width:918,height:824,borderRadius:12,overflow:'hidden',border:`2px solid ${C.ink}`,background:C.panel,boxShadow:'5px 6px 0 #DCD7CC'}}>{body()}</div>
  <div style={{position:'absolute',top:1356,left:70,width:865,color:C.muted,fontSize:24,lineHeight:1.35}}>{info.note}</div>
 </AbsoluteFill>;
};

export const Short:React.FC=()=>{
 const f=useCurrentFrame();const {fps}=useVideoConfig();
 const active=timeline.lines.find(l=>f>=l.fromFrame&&f<l.fromFrame+l.durationFrames+4)
   ??timeline.lines.filter(l=>l.fromFrame<=f).at(-1)??timeline.lines[0];
 const local=f-active.fromFrame;
 const talk=local>=0&&local<active.durationFrames;
 const bounce=talk?1+.012*Math.sin(local*.67):1;
 return <AbsoluteFill style={{fontFamily:FONT,color:C.ink,background:C.bg}}>
  <div style={{position:'absolute',left:69,top:106,fontFamily:HEAD,fontSize:35,color:C.red}}>ESP32-C5 × ロボコン通信</div>
  <div style={{position:'absolute',right:91,top:112,fontSize:26,color:C.muted}}>実測＋図解</div>
  <div style={{position:'absolute',left:70,top:168,width:864,height:4,background:'#DCD7CC',borderRadius:1}}><div style={{width:`${f/timeline.durationInFrames*100}%`,height:'100%',background:C.red,borderRadius:1}}/></div>
  {timeline.scenes.map(s=><Sequence key={s.id} from={s.from} durationInFrames={s.duration}><Scene id={s.id} duration={s.duration}/></Sequence>)}
  <div style={{position:'absolute',left:55,top:1431,width:719,minHeight:164,padding:'22px 20px',borderRadius:8,background:'#FFFDF8',border:`2px solid ${C.ink}`}}>
   <div style={{fontSize:23,color:C.green,marginBottom:10,fontWeight:800}}>ずんだもん / 1.5倍速</div>
   <div style={{fontWeight:900,fontSize:53,lineHeight:1.35,letterSpacing:-1}}>{active.caption.split('\n').map((l,i)=><div key={l} style={{color:i===1?C.red:C.ink,whiteSpace:'nowrap'}}>{l}</div>)}</div>
  </div>
  <div style={{position:'absolute',left:774,top:1420,width:227,height:324,transform:`scale(${bounce}) rotate(${talk?Math.sin(local*.12)*1.3:0}deg)`,transformOrigin:'50% 90%'}}><Img src={staticFile(`character/${active.pose}.png`)} style={{width:'100%',height:'100%',objectFit:'contain'}}/></div>
  <div style={{position:'absolute',left:70,top:1698,fontSize:24,color:C.muted,lineHeight:1.5}}>音声：VOICEVOX：ずんだもん<div style={{fontSize:21}}>立ち絵：東北ずん子・ずんだもんプロジェクト公式素材</div></div>
  <Audio src={staticFile('generated/music.wav')} volume={.82}/>
  {timeline.scenes.map(s=><Sequence key={'pop'+s.id} from={s.from} durationInFrames={5}><Audio src={staticFile('generated/pop.wav')} volume={.7}/></Sequence>)}
  {timeline.lines.map(l=><Sequence key={l.id} from={l.fromFrame} durationInFrames={l.durationFrames}><Audio src={staticFile(`generated/audio/${l.id}.wav`)}/></Sequence>)}
 </AbsoluteFill>;
};
