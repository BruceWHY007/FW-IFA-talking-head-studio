import React from 'react';
import {Composition} from 'remotion';
import {Film} from './Film';
import tl from './timeline.json';

export const Root: React.FC = () => (
  <Composition id="Film" component={Film} durationInFrames={(tl as any).durationInFrames} fps={(tl as any).fps}
    width={(tl as any).width} height={(tl as any).height} />
);
