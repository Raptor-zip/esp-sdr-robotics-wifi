import {bundle} from '@remotion/bundler';
import {selectComposition, renderStill, renderMedia} from '@remotion/renderer';
import path from 'node:path';
import fs from 'node:fs/promises';
import {fileURLToPath} from 'node:url';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const timeline=JSON.parse(await fs.readFile(path.join(root,'src/generated/timeline.json'),'utf8'));
await fs.mkdir(path.join(root,'out/stills'),{recursive:true});
const serveUrl=await bundle({entryPoint:path.join(root,'src/index.tsx'),publicDir:path.join(root,'public')});
const composition=await selectComposition({serveUrl,id:'C5RoboconShort',timeoutInMilliseconds:120000});
console.log('Composition',composition.width,composition.height,composition.durationInFrames/30,'seconds');
if (process.argv.includes('--stills')) {
 for (const s of timeline.scenes) {
  const frame=s.from+Math.floor(s.duration*.65);
  await renderStill({serveUrl,composition,output:path.join(root,`out/stills/${s.id}.png`),frame,imageFormat:'png',timeoutInMilliseconds:120000});
  console.log('Reviewed frame candidate',s.id,frame);
 }
} else {
 let last=-1;
 await renderMedia({serveUrl,composition,outputLocation:path.join(root,'out/master.mp4'),codec:'h264',
  crf:18,pixelFormat:'yuv420p',audioCodec:'aac',audioBitrate:'192k',concurrency:3,timeoutInMilliseconds:120000,
  onProgress:({progress})=>{let p=Math.floor(progress*20)*5;if(p!==last){last=p;console.log(`Render ${p}%`);}}});
}
