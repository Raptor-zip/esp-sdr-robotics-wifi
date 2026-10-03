import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {Short, fontReady} from './Short';
import timeline from './generated/timeline.json';

const Root: React.FC = () => <Composition id="C5RoboconShort" component={Short}
  width={1080} height={1920} fps={30} durationInFrames={timeline.durationInFrames}
  calculateMetadata={async () => {await fontReady;return {};}} />;

registerRoot(Root);
