import {Composition} from 'remotion';
import {Test} from './Test';
import {Reel, REEL_FRAMES} from './Reel';

export const Root: React.FC = () => (
  <>
    <Composition id="Test" component={Test} durationInFrames={210} fps={30} width={1080} height={1920} />
    <Composition id="Reel" component={Reel} durationInFrames={REEL_FRAMES} fps={30} width={1080} height={1920} />
  </>
);
