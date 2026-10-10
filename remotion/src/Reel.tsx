// Ролик целиком на Remotion: подложка (персонаж + фон из tools/doodle.py) + вставки и субтитры по плану.
// План готовит tools/reel.py → src/reel.json (времена уже в секундах).
import {useEffect, useMemo, useState} from 'react';
import {
  AbsoluteFill, OffthreadVideo, continueRender, delayRender, interpolate, spring, staticFile,
  useCurrentFrame, useVideoConfig,
} from 'remotion';
import {ThreeCanvas} from '@remotion/three';
import data from './reel.json';

const ORANGE = '#D97757';
const INK = '#16161a';
const FONT = 'InterX';
type Ev = any;

export const useFonts = () => {
  const [handle] = useState(() => delayRender('шрифты'));
  useEffect(() => {
    const f = new FontFace(FONT, `url(${staticFile('Inter-ExtraBold.ttf')})`);
    f.load().then((ff) => { document.fonts.add(ff); continueRender(handle); });
  }, [handle]);
};

const useT = () => { const f = useCurrentFrame(); const {fps} = useVideoConfig(); return f / fps; };
const sp = (t: number, from: number, damping = 11, mass = 0.7) =>
  spring({frame: Math.round((t - from) * 30), fps: 30, config: {damping, mass}});
const outK = (t: number, e: Ev, d = 0.25) => interpolate(t, [e.t1 - d, e.t1], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});

const glass: React.CSSProperties = {
  background: 'linear-gradient(155deg, rgba(255,255,255,0.82), rgba(255,255,255,0.38))',
  backdropFilter: 'blur(22px) saturate(170%)', WebkitBackdropFilter: 'blur(22px) saturate(170%)',
  border: '2px solid rgba(255,255,255,0.95)', boxShadow: '0 24px 50px rgba(40,30,80,0.20), inset 0 1px 0 white',
};

const Glow: React.FC<{x: number; y: number; w: number; h: number; k: number}> = ({x, y, w, h, k}) => (
  <>
    <div style={{position: 'absolute', left: x - 40, top: y - 40, width: w * 0.5, height: h * 0.8, borderRadius: '50%', background: 'rgba(255,150,100,0.7)', filter: 'blur(60px)', opacity: k}} />
    <div style={{position: 'absolute', left: x + w * 0.55, top: y + h * 0.35, width: w * 0.5, height: h * 0.8, borderRadius: '50%', background: 'rgba(120,170,255,0.65)', filter: 'blur(60px)', opacity: k}} />
  </>
);

// ---------- глянцевый номер ----------
const Badge: React.FC<{e: Ev}> = ({e}) => {
  const t = useT(); const k = sp(t, e.t0, 9, 0.6) * outK(t, e);
  return (
    <div style={{position: 'absolute', left: e.x - 68, top: e.y - 68 + 6 * Math.sin(t * 3), width: 136, height: 136, borderRadius: '50%',
      transform: `scale(${k}) rotate(${(1 - k) * -90}deg)`,
      background: `radial-gradient(circle at 34% 28%, #ffd2bd 0%, #f08f68 22%, ${ORANGE} 52%, #a8492b 100%)`,
      boxShadow: '0 18px 30px rgba(150,60,30,0.35), inset 0 -6px 14px rgba(120,40,20,0.35)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: FONT, fontSize: 76, color: 'white', textShadow: '0 3px 6px rgba(120,40,20,0.5)'}}>{e.text}</div>
  );
};

// ---------- световая вспышка из угла ----------
const Flare: React.FC<{e: Ev}> = ({e}) => {
  const t = useT(); const a = t - e.t0; const dur = e.t1 - e.t0;
  const g = Math.sin(Math.PI * Math.min(1, Math.max(0, a / dur)));
  const right = e.corner === 'tr' || e.corner === 'br'; const top = e.corner === 'tr' || e.corner === 'tl';
  const pos: React.CSSProperties = {position: 'absolute', [right ? 'right' : 'left']: -700, [top ? 'top' : 'bottom']: -700, width: 1400, height: 1400, borderRadius: '50%'};
  return (
    <AbsoluteFill>
      <div style={{...pos, opacity: g, background: 'radial-gradient(circle, rgba(255,190,150,0.95) 0%, rgba(217,119,87,0.55) 25%, transparent 60%)'}} />
      <div style={{...pos, opacity: g * 0.8, transform: `rotate(${a * 60}deg)`, filter: 'blur(6px)',
        background: 'repeating-conic-gradient(rgba(255,220,200,0.9) 0deg 4deg, transparent 4deg 30deg)',
        WebkitMaskImage: 'radial-gradient(circle, black 10%, transparent 55%)'}} />
    </AbsoluteFill>
  );
};

// ---------- стеклянная карточка в 3D ----------
const Card: React.FC<{e: Ev}> = ({e}) => {
  const t = useT(); const k = sp(t, e.t0, 13, 1) * outK(t, e, 0.3);
  const sub = sp(t, e.subT ?? e.t0 + 0.4, 200);
  const y = e.y ?? 330;
  return (
    <div style={{position: 'absolute', left: 90, top: y, width: 900, height: 280, perspective: 1200}}>
      <Glow x={0} y={0} w={900} h={280} k={k} />
      <div style={{position: 'absolute', inset: 0, borderRadius: 48, ...glass,
        transform: `translateY(${(1 - k) * 420}px) rotateX(${(1 - k) * 50 + 6}deg) rotateY(${4 * Math.sin(t * 1.6)}deg) scale(${0.8 + 0.2 * k})`,
        display: 'flex', alignItems: 'center', padding: '0 50px', gap: 36, opacity: Math.min(1, k * 1.5)}}>
        <div style={{fontSize: 120, filter: 'drop-shadow(0 8px 10px rgba(0,0,0,0.2))'}}>{e.emoji}</div>
        <div style={{fontFamily: FONT}}>
          <div style={{fontSize: e.title.length > 18 ? 52 : e.title.length > 14 ? 58 : 66, color: INK, whiteSpace: 'nowrap'}}>{e.title}</div>
          {e.sub && <div style={{fontSize: 40, color: '#6b6d78', marginTop: 10, opacity: sub, transform: `translateX(${(1 - sub) * 30}px)`}}>{e.sub}</div>}
        </div>
      </div>
    </div>
  );
};

// ---------- эмодзи на стеклянных плитках (по одной на слово), с галочкой или зачёркиванием ----------
const Tiles: React.FC<{e: Ev}> = ({e}) => {
  const t = useT(); const out = outK(t, e);
  return (
    <>
      {e.items.map((it: Ev, i: number) => {
        const k = sp(t, it.t, 9, 0.6) * out;
        if (k <= 0.001) return null;
        const m = it.markT !== undefined ? sp(t, it.markT, 10, 0.5) : 0;
        const size = it.size ?? 190;
        return (
          <div key={i} style={{position: 'absolute', left: it.x - size / 2, top: it.y - size / 2 + 8 * Math.sin(t * 3 + i), width: size,
            transform: `scale(${k}) rotate(${(1 - k) * 25}deg)`}}>
            <div style={{width: size, height: size, borderRadius: size * 0.28, ...glass, display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: size * 0.56, filter: it.mark === 'cross' && m > 0.5 ? 'grayscale(0.7)' : 'none', opacity: it.mark === 'cross' ? 1 - 0.3 * m : 1}}>{it.emoji}</div>
            {it.label && <div style={{fontFamily: FONT, fontSize: 38, color: INK, textAlign: 'center', marginTop: 12, textShadow: '0 0 10px white, 0 0 4px white', whiteSpace: 'nowrap'}}>{it.label}</div>}
            {it.mark === 'cross' && m > 0.001 && (
              <svg width={size} height={size} style={{position: 'absolute', left: 0, top: 0}} viewBox="0 0 100 100">
                <line x1="12" y1="12" x2={12 + 76 * Math.min(1, m)} y2={12 + 76 * Math.min(1, m)} stroke="#e5484d" strokeWidth="9" strokeLinecap="round" />
                <line x1="88" y1="12" x2={88 - 76 * Math.min(1, Math.max(0, m * 1.4 - 0.4))} y2={12 + 76 * Math.min(1, Math.max(0, m * 1.4 - 0.4))} stroke="#e5484d" strokeWidth="9" strokeLinecap="round" />
              </svg>
            )}
            {it.mark === 'check' && m > 0.001 && (
              <div style={{position: 'absolute', right: -14, top: -14, width: 70, height: 70, borderRadius: '50%', transform: `scale(${m})`,
                background: 'radial-gradient(circle at 34% 28%, #a7f0c0, #3dbb6e 55%, #24894b)', boxShadow: '0 8px 16px rgba(30,120,60,0.35)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontSize: 44, fontFamily: FONT}}>✓</div>
            )}
          </div>
        );
      })}
    </>
  );
};

// ---------- кинетический текст по словам, ключевое слово в плашке ----------
const Kinetic: React.FC<{e: Ev}> = ({e}) => {
  const t = useT(); const out = outK(t, e);
  const toks: string[] = e.text.split(' ');
  return (
    <div style={{position: 'absolute', left: 50, right: 50, top: e.y ?? 380, display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '10px 22px', opacity: out}}>
      {toks.map((w, i) => {
        const g = sp(t, e.t0 + (e.wt[i] ?? i * 0.2), 14, 0.5);
        const pill = e.pill && w.replace(/[.,!?]/g, '') === e.pill;
        return (
          <span key={i} style={{fontFamily: FONT, fontSize: e.px ?? 92, lineHeight: 1.15, opacity: Math.min(1, g * 2),
            transform: `translateY(${(1 - g) * 26}px) scale(${0.86 + 0.14 * g})`,
            color: pill ? 'white' : `rgb(${Math.round(175 - 157 * g)},${Math.round(175 - 157 * g)},${Math.round(177 - 157 * g)})`,
            background: pill ? INK : 'transparent', borderRadius: 18, padding: pill ? '0 22px' : 0,
            textShadow: pill ? 'none' : '0 0 14px white, 0 0 5px white'}}>{w}</span>
        );
      })}
    </div>
  );
};

// ---------- стеклянная таблица ----------
const Table: React.FC<{e: Ev}> = ({e}) => {
  const t = useT(); const k = sp(t, e.t0, 14, 0.9) * outK(t, e, 0.3);
  const y = e.y ?? 220; const rowH = 150;
  const h = 150 + rowH * e.rows.length;
  return (
    <div style={{position: 'absolute', left: 70, top: y, width: 940, height: h, transform: `translateY(${(1 - k) * 80}px) scale(${0.9 + 0.1 * k})`, opacity: k}}>
      <Glow x={0} y={0} w={940} h={h} k={1} />
      <div style={{position: 'absolute', inset: 0, borderRadius: 46, ...glass, padding: '36px 44px'}}>
        <div style={{fontFamily: FONT, fontSize: 60, color: INK, textAlign: 'center', marginBottom: 20}}>{e.title}</div>
        {e.rows.map((r: Ev, i: number) => {
          const g = sp(t, r.t, 12, 0.6);
          return (
            <div key={i} style={{display: 'flex', alignItems: 'center', height: rowH, borderTop: '2px solid rgba(40,40,60,0.10)', gap: 26,
              opacity: Math.min(1, g * 1.5), transform: `translateX(${(1 - g) * -60}px)`}}>
              <div style={{fontSize: 80, width: 100, textAlign: 'center'}}>{r.icon}</div>
              <div style={{fontFamily: FONT, fontSize: 54, color: INK, width: 280}}>{r.label}</div>
              <div style={{fontFamily: FONT, fontSize: 42, color: ORANGE, flex: 1, textAlign: 'right'}}>{r.value}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ---------- стеклянные столбики (без цифр — только «больше / меньше») ----------
const Bars: React.FC<{e: Ev}> = ({e}) => {
  const t = useT(); const k = sp(t, e.t0, 14, 0.9) * outK(t, e, 0.3);
  const y = e.y ?? 220; const H = 820; const vmax = Math.max(...e.items.map((i: Ev) => i.value));
  return (
    <div style={{position: 'absolute', left: 90, top: y, width: 900, height: H, transform: `translateY(${(1 - k) * 80}px) scale(${0.9 + 0.1 * k})`, opacity: k}}>
      <Glow x={0} y={0} w={900} h={H} k={1} />
      <div style={{position: 'absolute', inset: 0, borderRadius: 46, ...glass}}>
        <div style={{fontFamily: FONT, fontSize: 58, color: INK, textAlign: 'center', marginTop: 40}}>{e.title}</div>
        <div style={{position: 'absolute', left: 80, right: 80, bottom: 120, height: 520, display: 'flex', alignItems: 'flex-end', justifyContent: 'space-around', borderBottom: '3px solid rgba(40,40,60,0.25)'}}>
          {e.items.map((it: Ev, i: number) => {
            const g = sp(t, (it.t ?? e.t0 + 0.3 + i * 0.35), 12, 1.1);
            const c = it.color ?? (i ? '#5f96ff' : '#ff8a5c');
            return (
              <div key={i} style={{position: 'relative', width: 220, height: 500 * (it.value / vmax) * g, borderRadius: '22px 22px 0 0',
                background: `linear-gradient(180deg, ${c}, ${c}cc 60%, ${c}99), linear-gradient(90deg, rgba(255,255,255,0.35), transparent 40%)`,
                boxShadow: `0 18px 30px ${c}55, inset 10px 0 18px rgba(255,255,255,0.35)`}}>
                <div style={{position: 'absolute', bottom: -80, left: -40, right: -40, textAlign: 'center', fontFamily: FONT, fontSize: 40, color: '#6b6d78'}}>{it.label}</div>
                {it.emoji && <div style={{position: 'absolute', top: -96, left: 0, right: 0, textAlign: 'center', fontSize: 76, opacity: g}}>{it.emoji}</div>}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

// ---------- сетка 2×2 стеклянных карточек ----------
const Grid: React.FC<{e: Ev}> = ({e}) => {
  const t = useT(); const out = outK(t, e);
  return (
    <>
      {e.items.map((it: Ev, i: number) => {
        const k = sp(t, it.t, 10, 0.7) * out;
        if (k <= 0.001) return null;
        const x = i % 2 ? 560 : 80; const y = (e.y ?? 220) + Math.floor(i / 2) * 230;
        return (
          <div key={i} style={{position: 'absolute', left: x, top: y + 6 * Math.sin(t * 2.5 + i), width: 440, height: 200, borderRadius: 40, ...glass,
            display: 'flex', alignItems: 'center', gap: 22, padding: '0 30px', transform: `scale(${k}) rotate(${(1 - k) * (i % 2 ? 12 : -12)}deg)`}}>
            <div style={{fontSize: 92}}>{it.emoji}</div>
            <div style={{fontFamily: FONT, fontSize: 46, color: INK}}>{it.title}</div>
          </div>
        );
      })}
    </>
  );
};

// ---------- «сделал один раз — продаёшь много раз»: карточка размножается веером ----------
const Fan: React.FC<{e: Ev}> = ({e}) => {
  const t = useT(); const out = outK(t, e); const k0 = sp(t, e.t0, 12, 0.8) * out;
  const n = e.copies.length;
  return (
    <div style={{position: 'absolute', left: 540, top: e.y ?? 520}}>
      {[...e.copies].reverse().map((ct: number, ri: number) => {
        const i = n - 1 - ri; const g = sp(t, ct, 11, 0.6) * out;
        const ang = (i - (n - 1) / 2) * 13 * g; const dx = (i - (n - 1) / 2) * 120 * g;
        return (
          <div key={i} style={{position: 'absolute', left: -170 + dx, top: -120 - Math.abs(dx) * -0.1, width: 340, height: 220, borderRadius: 34, ...glass,
            transform: `rotate(${ang}deg) scale(${Math.max(g, 0.001)})`, transformOrigin: '50% 140%',
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center'}}>
            <div style={{fontSize: 90}}>{e.emoji}</div>
            <div style={{fontFamily: FONT, fontSize: 38, color: INK}}>{e.title}</div>
          </div>
        );
      })}
      <div style={{position: 'absolute', left: -170, top: -120, width: 340, height: 220, borderRadius: 34, ...glass,
        transform: `scale(${k0})`, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center'}}>
        <div style={{fontSize: 90}}>{e.emoji}</div>
        <div style={{fontFamily: FONT, fontSize: 38, color: INK}}>{e.title}</div>
      </div>
    </div>
  );
};

// ---------- 3D-кнопка «деньги»: появляется, нажимается, зачёркивается ----------
const MoneyButton: React.FC<{e: Ev}> = ({e}) => {
  const t = useT(); const k = sp(t, e.t0, 10, 0.8) * outK(t, e);
  const press = interpolate(t, [e.pressT, e.pressT + 0.08, e.pressT + 0.3], [0, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const cross = sp(t, e.crossT, 12, 0.6);
  const depth = 34 * (1 - press * 0.8);
  return (
    <div style={{position: 'absolute', left: 540 - 230, top: (e.y ?? 300), width: 460, height: 360, perspective: 900, transform: `scale(${k})`}}>
      <div style={{position: 'absolute', left: 30, top: 230, width: 400, height: 90, borderRadius: '50%', background: 'radial-gradient(ellipse, rgba(60,20,20,0.35), transparent 70%)'}} />
      <div style={{position: 'absolute', left: 40, top: 70, width: 380, height: 220, transform: 'rotateX(48deg)', transformStyle: 'preserve-3d'}}>
        <div style={{position: 'absolute', inset: 0, borderRadius: '50%', background: '#7a7f8c', transform: 'translateZ(0px)', boxShadow: '0 0 0 14px #5c606b'}} />
        <div style={{position: 'absolute', inset: 20, borderRadius: '50%', background: '#a3262b', transform: `translateZ(${depth * 0.5}px)`}} />
        <div style={{position: 'absolute', inset: 20, borderRadius: '50%', transform: `translateZ(${depth}px)`,
          background: 'radial-gradient(circle at 38% 30%, #ff9a90, #e5484d 45%, #b3242a)', boxShadow: 'inset 0 -10px 20px rgba(80,0,0,0.4)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 110}}>💰</div>
      </div>
      {cross > 0.001 && (
        <svg width={460} height={360} viewBox="0 0 460 360" style={{position: 'absolute', left: 0, top: 0}}>
          <line x1="60" y1="40" x2={60 + 340 * Math.min(1, cross)} y2={40 + 280 * Math.min(1, cross)} stroke="#e5484d" strokeWidth="26" strokeLinecap="round" />
          <line x1="400" y1="40" x2={400 - 340 * Math.min(1, cross)} y2={40 + 280 * Math.min(1, cross)} stroke="#e5484d" strokeWidth="26" strokeLinecap="round" />
        </svg>
      )}
    </div>
  );
};

// ---------- 3D-монета ----------
const Coin: React.FC<{e: Ev}> = ({e}) => {
  const t = useT(); const k = sp(t, e.t0, 9, 0.7) * outK(t, e);
  if (k <= 0.001) return null;
  return (
    <div style={{position: 'absolute', left: e.x - 260, top: e.y - 260, width: 520, height: 520}}>
      <ThreeCanvas width={520} height={520} camera={{position: [0, 0, 9], fov: 35}}>
        <ambientLight intensity={0.8} />
        <directionalLight position={[4, 6, 8]} intensity={2.4} />
        <pointLight position={[-5, -3, 4]} intensity={30} color="#fff2c4" />
        <group rotation={[0.35, t * 3 + (1 - k) * 6, 0]} scale={k}>
          <mesh rotation={[Math.PI / 2, 0, 0]}>
            <cylinderGeometry args={[1.5, 1.5, 0.28, 64]} />
            <meshPhysicalMaterial color="#f5c542" metalness={0.85} roughness={0.25} clearcoat={1} />
          </mesh>
          <mesh>
            <torusGeometry args={[1.5, 0.12, 24, 64]} />
            <meshPhysicalMaterial color="#e0a92a" metalness={0.9} roughness={0.2} />
          </mesh>
          <mesh position={[0, 0, 0.15]}>
            <ringGeometry args={[0.95, 1.12, 64]} />
            <meshStandardMaterial color="#c99320" metalness={0.8} roughness={0.3} />
          </mesh>
        </group>
      </ThreeCanvas>
    </div>
  );
};

// ---------- заголовок-«крючок» с первого кадра (первый кадр = обложка в ленте) ----------
const Hook: React.FC<{e: Ev}> = ({e}) => {
  const t = useT(); const k = outK(t, e, 0.3);
  return (
    <div style={{position: 'absolute', left: 70, top: e.y ?? 190, width: 940, height: 330, opacity: k, transform: `scale(${0.9 + 0.1 * k})`}}>
      <Glow x={0} y={0} w={940} h={330} k={1} />
      <div style={{position: 'absolute', inset: 0, borderRadius: 56, ...glass, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center'}}>
        {e.lines.map((l: string, i: number) => (
          <div key={i} style={{fontFamily: FONT, fontSize: 104, lineHeight: 1.15, color: i ? ORANGE : INK}}>{l}</div>
        ))}
      </div>
      {e.emoji && <div style={{position: 'absolute', right: -20, top: -70, fontSize: 150, transform: `rotate(${12 + 6 * Math.sin(t * 4)}deg)`}}>{e.emoji}</div>}
    </div>
  );
};

// ---------- призыв в Telegram-канал (в конце каждого ролика) ----------
const TG = '#2AABEE';
export const TgCard: React.FC<{e: Ev}> = ({e}) => {
  const t = useT(); const k = sp(t, e.t0, 12, 0.9) * outK(t, e, 0.3);
  const a = t - e.t0;
  const tap = interpolate(a, [1.0, 1.15, 1.35], [0, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const finger = sp(t, e.t0 + 0.7, 14, 0.6);
  const pulse = 1 + 0.035 * Math.sin(a * 6) * (a > 1.4 ? 1 : 0);
  const y = e.y ?? 230;
  return (
    <div style={{position: 'absolute', left: 80, top: y, width: 920, height: 560, perspective: 1200,
      transform: `translateY(${(1 - k) * 300}px) scale(${0.85 + 0.15 * k})`, opacity: Math.min(1, k * 1.4)}}>
      <div style={{position: 'absolute', left: -40, top: -50, width: 480, height: 380, borderRadius: '50%', background: 'rgba(42,171,238,0.55)', filter: 'blur(70px)'}} />
      <div style={{position: 'absolute', right: -30, bottom: -50, width: 420, height: 320, borderRadius: '50%', background: 'rgba(255,150,100,0.5)', filter: 'blur(70px)'}} />
      <div style={{position: 'absolute', inset: 0, borderRadius: 56, ...glass, transform: `rotateX(${4 + 3 * Math.sin(t * 1.5)}deg)`,
        display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: 44}}>
        <div style={{position: 'relative', width: 190, height: 190}}>
          <img src={staticFile('ember_avatar.png')} style={{width: 190, height: 190, borderRadius: '50%', boxShadow: `0 0 0 7px white, 0 0 0 13px ${TG}, 0 18px 30px rgba(20,90,140,0.3)`}} />
          <div style={{position: 'absolute', right: -14, bottom: -6, width: 74, height: 74, borderRadius: '50%', background: TG, boxShadow: '0 0 0 6px white',
            display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
            <img src={staticFile('telegram.svg')} style={{width: 44, height: 44, filter: 'brightness(0) invert(1)'}} />
          </div>
        </div>
        <div style={{fontFamily: FONT, fontSize: 74, color: INK, marginTop: 26}}>{e.title ?? 'Ember'}</div>
        <div style={{fontFamily: FONT, fontSize: 40, color: '#6b6d78', marginTop: 4}}>{e.sub ?? 'Telegram-канал'} · <span style={{color: TG}}>{e.link ?? 't.me/ember_aii'}</span></div>
        <div style={{position: 'relative', marginTop: 34, padding: '24px 78px', borderRadius: 70, fontFamily: FONT, fontSize: 58, color: 'white',
          background: `linear-gradient(180deg, #45bdf5, ${TG} 60%, #1f93d1)`, boxShadow: '0 16px 30px rgba(42,171,238,0.45), inset 0 2px 0 rgba(255,255,255,0.45)',
          transform: `scale(${pulse * (1 - 0.08 * tap)})`, display: 'flex', alignItems: 'center', gap: 18}}>
          <img src={staticFile('telegram.svg')} style={{width: 52, height: 52, filter: 'brightness(0) invert(1)'}} />
          {e.button ?? 'Подписаться'}
        </div>
      </div>
      <div style={{position: 'absolute', left: 700, top: 500 - 18 * tap, fontSize: 100, opacity: finger,
        transform: `translate(${(1 - finger) * 120}px, ${(1 - finger) * 120}px) rotate(-20deg)`}}>👆</div>
    </div>
  );
};

// ---------- кнопка «Подписаться» ----------
const Button: React.FC<{e: Ev}> = ({e}) => {
  const t = useT(); const k = sp(t, e.t0, 9, 0.6) * outK(t, e);
  const press = 1 - 0.07 * Math.sin(Math.PI * Math.min(1, Math.max(0, (t - e.t0 - 0.6) / 0.25)));
  return (
    <div style={{position: 'absolute', left: 540, top: e.y ?? 340, transform: `translate(-50%, -50%) scale(${k * press})`,
      padding: '30px 70px', borderRadius: 80, fontFamily: FONT, fontSize: 70, color: 'white', whiteSpace: 'nowrap',
      background: 'linear-gradient(90deg, #ff8c46, #f04678)', boxShadow: '0 20px 40px rgba(240,70,120,0.35), inset 0 2px 0 rgba(255,255,255,0.4)'}}>{e.text}</div>
  );
};

// ---------- субтитры: подсвечивается слово, которое звучит ----------
const Captions: React.FC = () => {
  const t = useT();
  const c = (data.chunks as Ev[]).find((c) => t >= c.t0 && t < c.t1);
  if (!c || c.hide) return null;
  const pop = sp(t, c.t0, 14, 0.5);
  const side = c.pos === 'side';
  const chars = c.words.reduce((n: number, [w]: [string, number]) => n + w.length + 1, 0);   // длинная фраза — шрифт меньше, без переноса
  const top = c.pos === 'top' ? 300 : side ? 1270 : 690;
  return (
    <div style={{position: 'absolute', left: side ? 330 : 30, right: 30, top, display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 8,
      transform: `scale(${0.85 + 0.15 * pop})`, opacity: pop}}>
      {c.words.map(([w, ts]: [string, number], i: number) => {
        const nx = i + 1 < c.words.length ? c.words[i + 1][1] : c.t1;
        const active = t >= ts && t < nx; const said = t >= ts;
        return (
          <span key={i} style={{fontFamily: FONT, fontSize: Math.round((side ? 56 : 64) * (chars > 30 ? 0.8 : chars > 24 ? 0.9 : 1)), padding: '4px 16px', borderRadius: 18, whiteSpace: 'nowrap',
            color: active ? 'white' : said ? INK : 'rgba(22,22,26,0.42)', background: active ? ORANGE : 'transparent',
            boxShadow: active ? '0 8px 18px rgba(217,119,87,0.45)' : 'none', transform: `scale(${active ? 1.08 : 1})`,
            textShadow: active ? 'none' : '0 0 12px white, 0 0 4px white'}}>{w}</span>
        );
      })}
    </div>
  );
};

const COMPONENTS: Record<string, React.FC<{e: Ev}>> = {
  badge: Badge, flare: Flare, card: Card, tiles: Tiles, kinetic: Kinetic, table: Table, bars: Bars, grid: Grid,
  fan: Fan, moneybutton: MoneyButton, coin: Coin, button: Button, hook: Hook, tg: TgCard,
};

// ---------- моушн-графика: глубина и движение поверх всего ролика ----------
const rnd = (i: number) => { const x = Math.sin(i * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
const ORBS = Array.from({length: 7}, (_, i) => {
  const side = i % 2 ? 1 : -1;                       // пятна держатся у краёв, чтобы не мешать вставкам
  return {x: 540 + side * (380 + rnd(i) * 220), y: 150 + rnd(i + 9) * 1650, r: 70 + rnd(i + 3) * 120,
    c: ['255,150,100', '120,170,255', '255,205,140'][i % 3], sp: 0.15 + rnd(i + 5) * 0.25, ph: rnd(i + 7) * 6.28, depth: 0.4 + rnd(i + 11)};
});
const DUST = Array.from({length: 28}, (_, i) => ({x: rnd(i + 40) * 1080, y: rnd(i + 80) * 1920, s: 3 + rnd(i + 120) * 5,
  sp: 18 + rnd(i + 160) * 40, ph: rnd(i + 200) * 6.28}));


// плавный «пролёт»: 0 → 1 → 0 за dur секунд (для разворотов камеры)
const swoop = (dt: number, dur = 1.1) => (dt < 0 || dt > dur ? 0 : Math.sin(Math.PI * dt / dur) ** 2);
// плавный вход/выход для сцен (таблицы, графики)
const hold = (t: number, a: number, b: number, f = 0.45) =>
  Math.min(1, Math.max(0, (t - a + f) / f)) * Math.min(1, Math.max(0, (b - t) / f));

const P = 1400;                                       // «объектив»: чем меньше — тем сильнее объём
// слой на глубине z: размер компенсирован, чтобы в покое всё стояло как задумано
const Layer: React.FC<{z: number; extra?: number; children: React.ReactNode}> = ({z, extra = 1, children}) => (
  <AbsoluteFill style={{transform: `translateZ(${z}px) scale(${((P - z) / P) * extra})`, transformStyle: 'preserve-3d'}}>{children}</AbsoluteFill>
);

const Orbs: React.FC = () => {
  const t = useT();
  return (
    <>
      {ORBS.map((o, i) => {
        const x = o.x + Math.sin(t * o.sp + o.ph) * 50 * o.depth;
        const y = ((o.y - t * 14 * o.depth) % 2100 + 2100) % 2100 - 90;
        return <div key={i} style={{position: 'absolute', left: x - o.r, top: y - o.r, width: o.r * 2, height: o.r * 2, borderRadius: '50%',
          background: `radial-gradient(circle, rgba(${o.c},0.5), rgba(${o.c},0) 70%)`, opacity: 0.35 + 0.15 * Math.sin(t * 0.8 + o.ph)}} />;
      })}
    </>
  );
};

const Dust: React.FC = () => {
  const t = useT();
  return (
    <>
      {DUST.map((p, i) => {
        const y = ((p.y - t * p.sp) % 1980 + 1980) % 1980 - 30;
        const tw = 0.35 + 0.65 * Math.abs(Math.sin(t * 1.7 + p.ph));
        return <div key={i} style={{position: 'absolute', left: p.x + Math.sin(t + p.ph) * 12, top: y, width: p.s, height: p.s, borderRadius: '50%',
          background: 'white', opacity: tw * 0.85, boxShadow: `0 0 ${p.s * 2.5}px rgba(255,170,120,0.9)`}} />;
      })}
    </>
  );
};

export const Reel: React.FC = () => {
  useFonts();
  const t = useT();
  const all = data.events as Ev[];
  const evs = useMemo(() => all.filter((e) => COMPONENTS[e.type]), []);
  const beats = useMemo(() => all.filter((e) => e.type === 'flare' || e.type === 'tg').map((e) => e.t0), []);
  const scenes = useMemo(() => all.filter((e) => e.type === 'table' || e.type === 'bars'), []);

  // ---- 3D-камера ----
  let ry = 4.5 * Math.sin(t * 0.31) + 1.5 * Math.sin(t * 0.83);      // медленный облёт
  let rx = 2.2 * Math.sin(t * 0.27 + 1);
  let tz = 25 * Math.sin(t * 0.21);                                    // «дыхание» вперёд-назад
  let tx = 0;
  beats.forEach((b, i) => {                                            // на смене пункта — пролёт с разворотом
    const k = swoop(t - b + 0.1);
    const dir = i % 2 ? -1 : 1;
    ry += dir * 8 * k; rx -= 2.5 * k; tz += 120 * k; tx += dir * 25 * k;   // без вылета вставок за край
  });
  scenes.forEach((e) => {                                              // таблица/график — отъезд и наклон
    const k = hold(t, e.t0, e.t1);
    rx += 5 * k; tz -= 90 * k;
  });
  const tgEv = all.find((e) => e.type === 'tg');
  if (tgEv) tz += 60 * hold(t, tgEv.t0 + 0.4, tgEv.t1 + 1, 1.2);       // финал — медленный наезд
  const intro = Math.min(1, t / 1.4);                                  // первый кадр (обложка) — ровный
  ry *= intro; rx *= intro; tx *= intro; tz *= intro;

  const sweep = beats.map((b) => t - b - 0.05).find((dt) => dt >= 0 && dt < 0.7);
  const layered = (data as Ev).layers;
  return (
    <AbsoluteFill style={{background: '#f7f7f8', overflow: 'hidden', perspective: `${P}px`}}>
      <AbsoluteFill style={{transformStyle: 'preserve-3d',
        transform: `translateX(${tx}px) translateZ(${tz}px) rotateX(${rx}deg) rotateY(${ry}deg)`}}>
        {layered ? (
          <>
            <Layer z={-600} extra={1.22}><OffthreadVideo src={staticFile('reel_grid.mp4')} muted /></Layer>
            <Layer z={-300} extra={1.1}><Orbs /></Layer>
            <Layer z={0}><OffthreadVideo src={staticFile('reel_char.webm')} muted transparent /></Layer>
          </>
        ) : (
          <Layer z={0} extra={1.08}><OffthreadVideo src={staticFile('reel_bg.mp4')} muted /></Layer>
        )}
        <Layer z={140}>
          {evs.filter((e) => t >= e.t0 - 0.05 && t < e.t1).map((e, i) => {
            const C = COMPONENTS[e.type];
            return <C key={i} e={e} />;
          })}
        </Layer>
        <Layer z={180}><Captions /></Layer>
        <Layer z={380}><Dust /></Layer>
      </AbsoluteFill>
      {sweep !== undefined && (
        <div style={{position: 'absolute', left: -600, top: -400, width: 2400, height: 380,
          transform: `rotate(-24deg) translateY(${-200 + sweep / 0.7 * 2800}px)`, opacity: 0.5 * Math.sin(Math.PI * sweep / 0.7),
          background: 'linear-gradient(180deg, rgba(255,255,255,0), rgba(255,240,225,0.9), rgba(255,255,255,0))', mixBlendMode: 'screen'}} />
      )}
      <AbsoluteFill style={{background: 'radial-gradient(ellipse at 50% 45%, rgba(0,0,0,0) 58%, rgba(40,25,70,0.16) 100%)'}} />
    </AbsoluteFill>
  );
};

export const REEL_FRAMES = Math.ceil((data as Ev).duration * 30);
