// Пробный кусок на Remotion: рисованный фон из tools/doodle.py + «настоящие» вставки поверх.
import {useEffect, useMemo, useState} from 'react';
import {
  AbsoluteFill, OffthreadVideo, continueRender, delayRender, interpolate, spring, staticFile,
  useCurrentFrame, useVideoConfig,
} from 'remotion';
import {ThreeCanvas} from '@remotion/three';
import * as THREE from 'three';
import {SVGLoader} from 'three/examples/jsm/loaders/SVGLoader.js';
import {CLAUDE_PATH} from './claudePath';
import words from './words.json';

const ORANGE = '#D97757';
const FONT = 'InterX';

const useFonts = () => {
  const [handle] = useState(() => delayRender('шрифты'));
  useEffect(() => {
    const f = new FontFace(FONT, `url(${staticFile('Inter-ExtraBold.ttf')})`);
    f.load().then((ff) => { document.fonts.add(ff); continueRender(handle); });
  }, [handle]);
};

// время слова по тексту (первое вхождение)
const at = (w: string) => (words as [string, number][]).find(([x]) => x === w)![1];

const useSpring = (startSec: number, cfg: {damping?: number; mass?: number} = {damping: 12, mass: 0.8}) => {
  const frame = useCurrentFrame(); const {fps} = useVideoConfig();
  return spring({frame: frame - Math.round(startSec * fps), fps, config: cfg});
};

// ---------- 3D-логотип Клода ----------
const Logo3D: React.FC<{from: number; to: number}> = ({from, to}) => {
  const frame = useCurrentFrame(); const {fps} = useVideoConfig();
  const t = frame / fps;
  const geom = useMemo(() => {
    const data = new SVGLoader().parse(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="${CLAUDE_PATH}"/></svg>`);
    const shapes = data.paths.flatMap((p) => SVGLoader.createShapes(p));
    const g = new THREE.ExtrudeGeometry(shapes, {depth: 2.2, bevelEnabled: true, bevelThickness: 0.35, bevelSize: 0.25, bevelSegments: 4, curveSegments: 10});
    g.center(); g.scale(1, -1, 1); g.computeVertexNormals();
    return g;
  }, []);
  const kin = spring({frame: frame - Math.round(from * fps), fps, config: {damping: 10, mass: 0.7}});
  const kout = interpolate(t, [to - 0.25, to], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const k = kin * kout;
  if (t < from || t > to) return null;
  const spin = (1 - kin) * Math.PI * 2.2 + t * 1.4;
  return (
    <AbsoluteFill style={{top: 90, height: 620}}>
      <div style={{position: 'absolute', left: 340, top: 470, width: 400, height: 60, borderRadius: '50%',
        background: 'radial-gradient(ellipse, rgba(80,40,20,0.35), transparent 70%)', transform: `scale(${k})`}} />
      <ThreeCanvas width={1080} height={620} camera={{position: [0, 0, 42], fov: 35}}>
        <ambientLight intensity={0.7} />
        <directionalLight position={[8, 10, 14]} intensity={2.2} />
        <pointLight position={[-12, -6, 10]} intensity={60} color="#ffd7c4" />
        <mesh geometry={geom} rotation={[0.25 * Math.sin(t * 2), spin, 0]} scale={k * 0.72}>
          <meshPhysicalMaterial color={ORANGE} roughness={0.28} metalness={0.15} clearcoat={1} clearcoatRoughness={0.15} />
        </mesh>
      </ThreeCanvas>
    </AbsoluteFill>
  );
};

// ---------- глянцевый номер ----------
const Badge: React.FC<{text: string; from: number; x: number; y: number}> = ({text, from, x, y}) => {
  const k = useSpring(from, {damping: 9, mass: 0.6});
  const frame = useCurrentFrame();
  if (k <= 0.001) return null;
  return (
    <div style={{position: 'absolute', left: x - 68, top: y - 68 + 6 * Math.sin(frame / 10), width: 136, height: 136, borderRadius: '50%',
      transform: `scale(${k}) rotate(${(1 - k) * -90}deg)`,
      background: `radial-gradient(circle at 34% 28%, #ffd2bd 0%, #f08f68 22%, ${ORANGE} 52%, #a8492b 100%)`,
      boxShadow: '0 18px 30px rgba(150,60,30,0.35), inset 0 -6px 14px rgba(120,40,20,0.35)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: FONT, fontSize: 76, color: 'white', textShadow: '0 3px 6px rgba(120,40,20,0.5)'}}>
      {text}
    </div>
  );
};

// ---------- световая вспышка из угла ----------
const Flare: React.FC<{from: number; dur: number}> = ({from, dur}) => {
  const frame = useCurrentFrame(); const {fps} = useVideoConfig();
  const a = frame / fps - from;
  if (a < 0 || a > dur) return null;
  const g = Math.sin(Math.PI * a / dur);
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div style={{position: 'absolute', right: -700, top: -700, width: 1400, height: 1400, borderRadius: '50%', opacity: g,
        background: `radial-gradient(circle, rgba(255,190,150,0.95) 0%, rgba(217,119,87,0.55) 25%, transparent 60%)`}} />
      <div style={{position: 'absolute', right: -600, top: -600, width: 1200, height: 1200, borderRadius: '50%', opacity: g * 0.8,
        transform: `rotate(${a * 60}deg)`, filter: 'blur(6px)',
        background: 'repeating-conic-gradient(rgba(255,220,200,0.9) 0deg 4deg, transparent 4deg 30deg)',
        WebkitMaskImage: 'radial-gradient(circle, black 10%, transparent 55%)'}} />
    </AbsoluteFill>
  );
};

// ---------- стеклянная карточка в 3D ----------
const GlassCard: React.FC<{from: number; subFrom: number; priceFrom: number}> = ({from, subFrom, priceFrom}) => {
  const frame = useCurrentFrame(); const {fps} = useVideoConfig();
  const k = useSpring(from, {damping: 13, mass: 1});
  const sub = useSpring(subFrom, {damping: 200});
  const price = useSpring(priceFrom, {damping: 8, mass: 0.6});
  if (k <= 0.001) return null;
  const t = frame / fps;
  return (
    <div style={{position: 'absolute', left: 90, top: 330, width: 900, height: 300, perspective: 1200}}>
      {/* цветное свечение под стеклом */}
      <div style={{position: 'absolute', left: -40, top: -50, width: 420, height: 320, borderRadius: '50%', background: 'rgba(255,150,100,0.75)', filter: 'blur(60px)', opacity: k}} />
      <div style={{position: 'absolute', right: -30, bottom: -60, width: 460, height: 300, borderRadius: '50%', background: 'rgba(120,170,255,0.7)', filter: 'blur(60px)', opacity: k}} />
      <div style={{position: 'absolute', inset: 0, borderRadius: 48,
        transform: `translateY(${(1 - k) * 420}px) rotateX(${(1 - k) * 50 + 6}deg) rotateY(${4 * Math.sin(t * 1.6)}deg) scale(${0.8 + 0.2 * k})`,
        background: 'linear-gradient(160deg, rgba(255,255,255,0.75), rgba(255,255,255,0.35))',
        backdropFilter: 'blur(26px) saturate(170%)', WebkitBackdropFilter: 'blur(26px) saturate(170%)',
        border: '2px solid rgba(255,255,255,0.9)', boxShadow: '0 30px 60px rgba(40,30,80,0.22), inset 0 1px 0 white',
        display: 'flex', alignItems: 'center', padding: '0 56px', gap: 40, opacity: Math.min(1, k * 1.5)}}>
        <img src={staticFile('claude-color.svg')} style={{width: 130, height: 130, filter: 'drop-shadow(0 8px 10px rgba(150,60,30,0.3))'}} />
        <div style={{fontFamily: FONT}}>
          <div style={{fontSize: 70, color: '#16161a'}}>Старт бесплатно</div>
          <div style={{fontSize: 42, color: '#6b6d78', marginTop: 10, opacity: sub, transform: `translateX(${(1 - sub) * 30}px)`}}>нужен только браузер</div>
        </div>
        <div style={{position: 'absolute', right: 40, bottom: -30, padding: '10px 26px', borderRadius: 40, fontFamily: FONT, fontSize: 46, color: 'white',
          background: 'linear-gradient(180deg, #5fd38a, #2fa560)', boxShadow: '0 10px 20px rgba(30,120,60,0.35)',
          transform: `scale(${price}) rotate(${8 - 8 * price}deg)`}}>0 ₽</div>
      </div>
    </div>
  );
};

// ---------- эмодзи на стеклянной плитке ----------
const EmojiTile: React.FC<{emoji: string; from: number; x: number; y: number}> = ({emoji, from, x, y}) => {
  const k = useSpring(from, {damping: 9, mass: 0.6});
  const frame = useCurrentFrame();
  if (k <= 0.001) return null;
  return (
    <div style={{position: 'absolute', left: x - 95, top: y - 95 + 8 * Math.sin(frame / 9), width: 190, height: 190, borderRadius: 54,
      transform: `scale(${k}) rotate(${(1 - k) * 25}deg)`,
      background: 'linear-gradient(150deg, rgba(255,255,255,0.8), rgba(255,255,255,0.35))',
      backdropFilter: 'blur(18px)', border: '2px solid rgba(255,255,255,0.95)', boxShadow: '0 20px 40px rgba(40,30,80,0.2)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 110}}>
      {emoji}
    </div>
  );
};

// ---------- субтитры: слово подсвечивается в момент произнесения ----------
const CHUNKS = [[0, 3], [3, 5], [5, 6], [6, 7], [7, 10], [10, 13]]; // по фразам сценария
const Captions: React.FC = () => {
  const frame = useCurrentFrame(); const {fps} = useVideoConfig();
  const t = frame / fps; const W = words as [string, number][];
  const ci = CHUNKS.findIndex(([a, b], i) => t >= W[a][1] - 0.05 && (i === CHUNKS.length - 1 || t < W[CHUNKS[i + 1][0]][1] - 0.05));
  if (ci < 0) return null;
  const [a, b] = CHUNKS[ci];
  const pop = spring({frame: frame - Math.round((W[a][1] - 0.05) * fps), fps, config: {damping: 14, mass: 0.5}});
  const zoomed = t < 1.7;
  return (
    <div style={{position: 'absolute', left: 40, right: 40, top: zoomed ? 330 : 680, display: 'flex', flexWrap: 'nowrap', justifyContent: 'center',
      gap: 8, transform: `scale(${0.85 + 0.15 * pop})`, opacity: pop}}>
      {W.slice(a, b).map(([w, ts], i) => {
        const active = t >= ts && (a + i + 1 >= W.length || t < W[a + i + 1][1]);
        const said = t >= ts;
        return (
          <span key={i} style={{fontFamily: FONT, fontSize: 64, padding: '4px 16px', whiteSpace: 'nowrap', borderRadius: 18,
            color: active ? 'white' : said ? '#16161a' : 'rgba(22,22,26,0.45)',
            background: active ? ORANGE : 'transparent', boxShadow: active ? '0 8px 18px rgba(217,119,87,0.45)' : 'none',
            transform: `scale(${active ? 1.08 : 1})`,
            textShadow: active ? 'none' : '0 0 12px white, 0 0 4px white'}}>{w}</span>
        );
      })}
    </div>
  );
};

// ---------- маленький крутящийся логотип в углу ----------
const CornerLogo: React.FC = () => {
  const frame = useCurrentFrame();
  const k = Math.min(1, frame / 18);
  return <img src={staticFile('claude-color.svg')} style={{position: 'absolute', left: 905, top: 190, width: 120, height: 120, opacity: k,
    transform: `rotate(${frame * 0.6}deg) scale(${0.6 + 0.4 * k})`, filter: 'drop-shadow(0 8px 8px rgba(120,50,20,0.3))'}} />;
};

export const Test: React.FC = () => {
  useFonts();
  return (
    <AbsoluteFill style={{background: 'white'}}>
      <OffthreadVideo src={staticFile('bg.mp4')} muted />
      <Logo3D from={at('нейросеть')} to={at('Первое') - 0.05} />
      <Flare from={at('Первое') - 0.15} dur={0.9} />
      <Badge text="1" from={at('Первое')} x={150} y={250} />
      <GlassCard from={at('начать')} subFrom={at('нужен')} priceFrom={at('бесплатно')} />
      <EmojiTile emoji="🌐" from={at('браузер')} x={870} y={930} />
      <Captions />
      <CornerLogo />
    </AbsoluteFill>
  );
};
