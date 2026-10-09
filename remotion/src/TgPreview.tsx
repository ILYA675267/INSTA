// Превью карточки Telegram поверх кадра с персонажем (для проверки дизайна).
import {AbsoluteFill, OffthreadVideo, staticFile} from 'remotion';
import {TgCard, useFonts} from './Reel';

export const TgPreview: React.FC = () => {
  useFonts();
  return (
  <AbsoluteFill style={{background: 'white'}}>
    <OffthreadVideo src={staticFile('reel_bg.mp4')} muted startFrom={1500} />
    <TgCard e={{t0: 0, t1: 4}} />
  </AbsoluteFill>
  );
};
