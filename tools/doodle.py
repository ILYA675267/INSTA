"""Дудл-ролик: нарисованный от руки персонаж на «плывущем» клетчатом фоне + мини-анимации под текст.

python3 tools/doodle.py voice.wav words.json plan.json out.mp4

words.json — [[слово, время_с], ...] (tools/align.py).
plan.json  — {"captions": true, "events": [ {...}, ... ]}. Событие:
  "at": "слово" или номер слова (время начала), "word_n": какое по счёту вхождение слова (1 — первое),
  "dur": сколько секунд держать (по умолчанию 2.2),
  "type": "text" | "icon" | "badge",
  "text": для text/badge, "icon": coin heart bulb check cross arrow star question exclaim clock doc code chat
          sparkle pencil bookmark,
  "x", "y": центр (по умолчанию — свободное место сверху), "size": масштаб (1.0), "color": [r,g,b],
  "mark": true — жёлтый маркер под текстом, "wave": true — персонаж машет рукой.
Линии «дрожат» (эффект рисованной анимации), фон медленно плывёт волнами.
"""
import json, math, random, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS, SS = 1080, 1920, 30, 2
INK = (24, 24, 28, 255)
ROOT = __file__.rsplit('/tools/', 1)[0]
FONT = f'{ROOT}/fonts/Caveat.ttf'
_fonts = {}


def font(px):
    if px not in _fonts:
        f = ImageFont.truetype(FONT, int(px)); f.set_variation_by_name('Bold'); _fonts[px] = f
    return _fonts[px]


# ---------- рисованная линия ----------
def resample(pts, step, closed):
    pts = [np.array(p, float) for p in pts]
    if closed:
        pts = pts + [pts[0]]
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(np.linalg.norm(b - a) / step))
        out += [a + (b - a) * k / n for k in range(1, n + 1)]
    return np.array(out)


def wobble(pts, seed, amp=2.0, step=16, closed=False):
    p = resample(pts, step * SS, closed)
    rng = np.random.default_rng(seed)
    n = rng.normal(0, amp * SS, p.shape)
    k = np.array([0.25, 0.5, 0.25])
    for _ in range(2 if len(p) >= 3 else 0):
        n = np.stack([np.convolve(n[:, i], k, mode='same') for i in range(2)], 1)
    return [tuple(x) for x in (p + n)]


def line(d, pts, seed, w=7, color=INK, closed=False, amp=2.0):
    q = wobble(pts, seed, amp, closed=closed)
    d.line(q, fill=color, width=int(w * SS), joint='curve')
    r = w * SS / 2
    for x, y in (q[0], q[-1]):
        d.ellipse((x - r, y - r, x + r, y + r), fill=color)


def shape(d, pts, seed, fill=(255, 255, 255, 255), w=7, color=INK, amp=2.0):
    q = wobble(pts, seed, amp, closed=True)
    d.polygon(q, fill=fill)
    d.line(q + [q[0]], fill=color, width=int(w * SS), joint='curve')


def ell(cx, cy, rx, ry, n=48, a0=0, a1=360):
    return [(cx + rx * math.cos(math.radians(a)), cy + ry * math.sin(math.radians(a)))
            for a in np.linspace(a0, a1, n, endpoint=(a1 - a0 < 360))]


def P(pts, ox, oy, s):
    return [(ox + x * s * SS, oy + y * s * SS) for x, y in pts]


# ---------- фон ----------
class Grid:
    def __init__(self, step=120):
        rnd = random.Random(3)
        self.v = [(x, rnd.uniform(0, 6.28), rnd.uniform(0.6, 1.4)) for x in range(-step // 2, W + step, step)]
        self.h = [(y, rnd.uniform(0, 6.28), rnd.uniform(0.6, 1.4)) for y in range(-step // 2, H + step, step)]

    def draw(self, t):
        img = Image.new('RGB', (W, H), (255, 255, 255)); d = ImageDraw.Draw(img)
        col, A = (168, 168, 172), 14
        ys = np.linspace(-40, H + 40, 70); xs = np.linspace(-40, W + 40, 44)
        for x0, ph, f in self.v:
            x = x0 + A * np.sin(ys / 260 * f + ph + t * 0.9) + 5 * np.sin(ys / 90 + ph * 2 + t * 0.5)
            d.line(list(zip(x, ys)), fill=col, width=3, joint='curve')
        for y0, ph, f in self.h:
            y = y0 + A * np.sin(xs / 240 * f + ph + t * 0.8) + 5 * np.sin(xs / 80 + ph * 2 - t * 0.6)
            d.line(list(zip(xs, y)), fill=col, width=3, joint='curve')
        return img.convert('RGBA')


# ---------- персонаж ----------
def spikes():
    rnd = random.Random(5)
    pts = [(-122, 25)]
    angs = np.linspace(170, 370, 17)
    for i, a in enumerate(angs[1:-1]):
        r0, r1 = (126, 118) if i % 2 else (124, 124 + rnd.uniform(45, 85))
        rr = r1 if i % 2 == 0 else r0
        jitter = rnd.uniform(-6, 6)
        pts.append((rr * math.cos(math.radians(a + jitter)), -8 + rr * 0.95 * math.sin(math.radians(a + jitter))))
    pts.append((122, 25))
    bangs = [(100, -25), (84, 20), (58, -30), (36, 14), (10, -32), (-14, 10), (-40, -34), (-66, 16), (-92, -24)]
    return pts + bangs


HAIR = spikes()


def character(d, ox, oy, s, st, seed):
    """ox, oy — центр головы (в пикселях SS); st — состояние (рот, глаза, руки)."""
    L = lambda pts, **k: line(d, P(pts, ox, oy, s), seed + len(pts), w=k.get('w', 7) * s, closed=k.get('closed', False),
                             color=k.get('color', INK))
    F = lambda pts, fill=(255, 255, 255, 255): shape(d, P(pts, ox, oy, s), seed + len(pts) * 3, fill=fill, w=7 * s)
    # ноги и стопы
    L([(-62, 560), (-66, 640)]); L([(62, 560), (70, 640)])
    F(ell(-88, 655, 52, 28)); F(ell(96, 655, 52, 28))
    # шорты
    F([(-128, 420), (128, 420), (138, 565), (18, 565), (2, 480), (-14, 565), (-138, 565)])
    # руки (за футболкой — плечо, к кисти)
    la, ra = st['arm_l'], st['arm_r']
    lh = (-170 + 150 * math.cos(math.radians(la)), 245 + 150 * math.sin(math.radians(la)))
    rh = (170 + 150 * math.cos(math.radians(ra)), 245 + 150 * math.sin(math.radians(ra)))
    L([(-160, 250), lh]); L([(160, 250), rh])
    F(ell(lh[0], lh[1], 46, 44)); F(ell(rh[0], rh[1], 46, 44))
    # футболка
    F([(-36, 118), (36, 118), (108, 140), (190, 215), (160, 285), (124, 262), (130, 430), (-130, 430), (-124, 262),
       (-160, 285), (-190, 215), (-108, 140)])
    L([(-36, 120), (0, 150), (36, 120)], w=5)
    # голова
    hx = st['head_dx']
    F(ell(hx, 0, 124, 120))
    F([(x + hx, y) for x, y in HAIR])
    # глаза
    for ex in (-40, 40):
        if st['blink']:
            L([(hx + ex - 12, 34), (hx + ex + 12, 34)], w=6)
        else:
            d.ellipse([*P([(hx + ex - 9 + st['look'] * 4, 24)], ox, oy, s)[0], *P([(hx + ex + 9 + st['look'] * 4, 44)], ox, oy, s)[0]], fill=INK)
    # рот
    m = st['mouth']
    if m == 0:
        L([(hx - 26, 74), (hx - 6, 77), (hx + 12, 73), (hx + 26, 75)], w=6)
    else:
        rw, rh_ = [0, 16, 22, 26, 20][m], [0, 7, 13, 19, 24][m]
        shape(d, P(ell(hx, 76, rw, rh_, 28), ox, oy, s), seed + 77, fill=INK, w=5 * s, amp=1.2)


# ---------- мини-анимации ----------
def icon(d, name, cx, cy, s, seed, t, color=None):
    S_ = lambda pts: P(pts, cx, cy, s)
    Ln = lambda pts, w=7, col=INK, closed=False: line(d, S_(pts), seed + len(pts), w=w * s, color=col, closed=closed)
    Fl = lambda pts, fill: shape(d, S_(pts), seed + len(pts) * 5, fill=fill, w=7 * s)
    if name == 'coin':
        Fl(ell(0, 0, 70, 70), (255, 206, 70, 255)); Ln(ell(0, 0, 50, 50), w=4, closed=True)
        txt(d, '₽', cx, cy, 80 * s)
    elif name == 'heart':
        pts = [(16 * math.sin(a) ** 3 * 4.4, -(13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a)) * 4.4)
               for a in np.linspace(0, 2 * math.pi, 60, endpoint=False)]
        Fl(pts, (255, 110, 130, 255))
    elif name == 'bulb':
        Fl(ell(0, -20, 58, 60, a0=140, a1=400) + [(22, 50), (-22, 50)], (255, 236, 120, 255))
        Ln([(-22, 62), (22, 62)], w=6); Ln([(-16, 78), (16, 78)], w=6)
        for a in (-150, -110, -70, -30):
            r = math.radians(a); Ln([(80 * math.cos(r), -20 + 80 * math.sin(r)), (108 * math.cos(r), -20 + 108 * math.sin(r))], w=5)
    elif name == 'check':
        Ln([(-60, 0), (-18, 44), (66, -56)], w=14, col=(40, 170, 90, 255))
    elif name == 'cross':
        Ln([(-50, -50), (50, 50)], w=14, col=(225, 50, 50, 255)); Ln([(50, -50), (-50, 50)], w=14, col=(225, 50, 50, 255))
    elif name == 'arrow':
        Ln([(-80, 30), (-20, -20), (40, -30), (80, -10)], w=8); Ln([(52, -40), (82, -10), (48, 16)], w=8)
    elif name in ('star', 'sparkle'):
        n, r1, r2 = (5, 70, 30) if name == 'star' else (4, 72, 20)
        pts = [((r1 if k % 2 == 0 else r2) * math.cos(-math.pi / 2 + k * math.pi / n), (r1 if k % 2 == 0 else r2) * math.sin(-math.pi / 2 + k * math.pi / n))
               for k in range(2 * n)]
        Fl(pts, tuple(color or (255, 206, 70)) + (255,))
    elif name in ('question', 'exclaim'):
        txt(d, '?' if name == 'question' else '!', cx, cy, 190 * s, color=tuple(color or INK[:3]) + (255,))
    elif name == 'clock':
        Fl(ell(0, 0, 70, 70), (255, 255, 255, 255))
        a = t * 4
        Ln([(0, 0), (34 * math.sin(a / 12), -34 * math.cos(a / 12))], w=7); Ln([(0, 0), (52 * math.sin(a), -52 * math.cos(a))], w=5)
    elif name == 'doc':
        Fl([(-50, -66), (26, -66), (54, -38), (54, 66), (-50, 66)], (255, 255, 255, 255))
        for y in (-30, -6, 18, 42):
            Ln([(-30, y), (34, y)], w=5)
    elif name == 'code':
        Ln([(-36, -46), (-76, 0), (-36, 46)], w=10); Ln([(36, -46), (76, 0), (36, 46)], w=10); Ln([(12, -56), (-12, 56)], w=10)
    elif name == 'chat':
        Fl(ell(0, -6, 82, 60, 40, 0, 300) + [(30, 70), (40, 54)][::-1][:1] + [(-10, 82)], (255, 255, 255, 255))
        for x in (-30, 0, 30):
            d.ellipse(S_([(x - 7, -13)])[0] + S_([(x + 7, 1)])[0], fill=INK)
    elif name == 'pencil':
        Fl([(-70, 40), (40, -70), (70, -40), (-40, 70), (-80, 80)], (255, 206, 70, 255)); Ln([(-70, 40), (-40, 70)], w=6)
    elif name == 'bookmark':
        Fl([(-44, -66), (44, -66), (44, 70), (0, 36), (-44, 70)], (120, 170, 255, 255))


def txt(d, text, cx, cy, px, color=INK, mark=None, seed=0):
    f = font(px * SS)
    x0, y0, x1, y1 = d.textbbox((cx, cy), text, font=f, anchor='mm')
    if mark:
        pad = 14 * SS
        shape(d, [(x0 - pad, y0 + 4 * SS), (x1 + pad, y0 - 2 * SS), (x1 + pad * 0.6, y1 + pad * 0.7), (x0 - pad * 0.7, y1 + pad * 0.5)],
              seed, fill=tuple(mark) + (255,), w=0.01, color=tuple(mark) + (255,), amp=1.5)
    d.text((cx, cy), text, font=f, fill=color, anchor='mm')


def ease_back(x):
    x = min(max(x, 0), 1); c = 1.7
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


# ---------- звук ----------
def loudness(path):
    w = wave.open(path); sr = w.getframerate()
    a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    hop = sr // FPS; n = int(math.ceil(len(a) / hop))
    r = np.array([np.sqrt(np.mean(a[i * hop:(i + 1) * hop] ** 2) + 1e-9) for i in range(n)])
    r = (r / (np.percentile(r, 92) + 1e-9)) ** 0.8
    return np.convolve(r, [0.25, 0.5, 0.25], mode='same'), len(a) / sr


SLOTS = [(300, 430), (780, 470), (540, 330), (290, 650), (790, 660)]


def resolve(plan, words):
    norm = lambda w: w.lower().replace('ё', 'е').strip('.,!?…:;—-«»')
    evs = []
    for k, e in enumerate(plan['events']):
        at = e['at']
        if isinstance(at, str):
            hits = [t for w, t in words if norm(w) == norm(at)]
            if not hits:
                raise SystemExit(f'Слово «{at}» не найдено в words.json')
            t0 = hits[min(e.get('word_n', 1), len(hits)) - 1]
        else:
            t0 = words[at][1]
        e = dict(e, t0=t0 + e.get('delay', 0), t1=t0 + e.get('delay', 0) + e.get('dur', 2.2))
        if 'x' not in e:
            e['x'], e['y'] = SLOTS[k % len(SLOTS)]
        evs.append(e)
    return evs


def captions(words, dur):
    """Фразы по 2–4 слова, смена на паузах и знаках препинания."""
    chunks, cur = [], []
    for i, (w, t) in enumerate(words):
        cur.append((w, t))
        nxt = words[i + 1][1] if i + 1 < len(words) else dur
        if len(cur) >= 4 or nxt - t > 0.55 or (len(cur) >= 2 and len(w) > 9):
            chunks.append((cur[0][1], nxt, ' '.join(x for x, _ in cur))); cur = []
    if cur:
        chunks.append((cur[0][1], dur, ' '.join(x for x, _ in cur)))
    return chunks


def main(wav, words_path, plan_path, out):
    words = json.load(open(words_path)); plan = json.load(open(plan_path))
    rms, dur = loudness(wav)
    evs = resolve(plan, words)
    caps = captions(words, dur) if plan.get('captions', True) else []
    grid = Grid()
    rnd = random.Random(9)
    blinks, t = set(), 1.1
    while t < dur:
        blinks.update(range(int(t * FPS), int(t * FPS) + 4)); t += rnd.uniform(2.0, 4.2)
    waves = [(e['t0'], e['t0'] + 1.4) for e in evs if e.get('wave')]
    ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', f'{W}x{H}', '-r', str(FPS),
                           '-i', '-', '-i', wav, '-map', '0:v', '-map', '1:a', '-shortest', '-c:v', 'libx264', '-preset', 'medium',
                           '-crf', '17', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '256k', '-ar', '48000',
                           '-movflags', '+faststart', out], stdin=subprocess.PIPE)
    prev, n = 0, len(rms)
    for i in range(n):
        t = i / FPS; v = rms[i]
        boil = (i // 4) % 3                                  # линии «дрожат» 7–8 раз в секунду
        m = 0 if v < 0.10 else 1 if v < 0.25 else 2 if v < 0.45 else 3 if v < 0.75 else 4
        if abs(m - prev) > 1:
            m = prev + (1 if m > prev else -1)
        prev = m
        talk = v > 0.1
        waving = any(a <= t < b for a, b in waves)
        st = {'mouth': m, 'blink': i in blinks, 'look': math.sin(t * 0.7),
              'head_dx': 4 * math.sin(t * 1.3) + (3 * math.sin(t * 7) if talk else 0),
              'arm_l': 125 + 8 * math.sin(t * 2.1) + (10 * min(v, 1) if talk else 0),
              'arm_r': (-60 + 25 * math.sin(t * 14)) if waving else (-25 + 10 * math.sin(t * 1.7) - (14 * min(v, 1) if talk else 0))}
        layer = Image.new('RGBA', (W * SS, H * SS), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
        bob = 6 * math.sin(t * 2 * math.pi / 2.6) + (4 * min(v, 1) if talk else 0)
        character(d, 540 * SS, (1050 + bob) * SS, 1.1, st, 100 + boil * 7)
        for e in evs:
            if not (e['t0'] <= t < e['t1']):
                continue
            a = t - e['t0']; out_k = min(1.0, (e['t1'] - t) / 0.25)
            k = ease_back(a / 0.35) * out_k * e.get('size', 1.0)
            if k <= 0.02:
                continue
            cx, cy = e['x'] * SS, (e['y'] + 8 * math.sin(a * 3)) * SS
            sd = 300 + boil * 11 + hash(e.get('text', e.get('icon', ''))) % 50
            if e['type'] == 'icon':
                icon(d, e['icon'], cx, cy, k * 1.35, sd, a, e.get('color'))
            elif e['type'] == 'badge':
                shape(d, P(ell(0, 0, 62, 62), cx, cy, k), sd, fill=tuple(e.get('color', (217, 119, 87))) + (255,), w=7 * k)
                txt(d, e['text'], cx, cy - 6 * SS * k, 100 * k, color=(255, 255, 255, 255))
            else:
                txt(d, e['text'], cx, cy, e.get('px', 92) * k, color=tuple(e.get('color', INK[:3])) + (255,),
                    mark=(255, 226, 90) if e.get('mark') else None, seed=sd)
        for c0, c1, text in caps:
            if c0 <= t < c1:
                txt(d, text, 540 * SS, 760 * SS, 104, mark=(255, 255, 255), seed=boil)
                break
        frame = grid.draw(t)
        frame.alpha_composite(layer.reduce(SS))
        ff.stdin.write(frame.tobytes())
    ff.stdin.close(); ff.wait()
    print('Готово:', out)


if __name__ == '__main__':
    main(*sys.argv[1:5])
