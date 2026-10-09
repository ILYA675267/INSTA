import {Composition} from 'remotion';
import {Test} from './Test';

export const Root: React.FC = () => (
  <Composition id="Test" component={Test} durationInFrames={210} fps={30} width={1080} height={1920} />
);
