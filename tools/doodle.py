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
"corner_logo": {"logo": "claude-color", "x": 965, "y": 250, "size": 120, "speed": 18} — маленький логотип
  в углу, медленно крутится весь ролик (speed — градусов в секунду).
"music": "work/<имя>/music.wav" — тихая фоновая мелодия (tools/music.py), "music_volume": 1.0 — множитель громкости.
"style": "real" — реалистичные вставки вместо рисовки (стекло, глянец, кнопки; см. tools/real.py).
"sfx": true — тихие звуки на появление элементов (tools/sfx.py), "sfx_volume": 1.0; у события "sfx": "pop"/false.
"type": "pose", "pose": shrug | arms_up | point_up | point_left | point_right | explain — жест руками на время dur.
"type": "cam", "cam": [x, y, масштаб], "snap": true — свой ракурс камеры (snap — резкий «наезд»);
"type": "punch" — короткий резкий наезд на лицо на ключевом слове (dur ~0.6).
"bg_only": true — только персонаж и фон (без субтитров и вставок): подложка для Remotion.
"layers": true (вместе с bg_only) — два файла: <out>_grid.mp4 (клетка) и <out>_char.webm (Эмбер с тенью, прозрачный фон)
  для 3D-камеры в Remotion; в <out> пишется метка.
"tail": 0.8 — сколько секунд тишины добавить в конце, чтобы последняя надпись успела доиграть.
Субтитры рвутся на точках/запятых сценария, если рядом с words.json лежит script.txt.
Линии «дрожат» (эффект рисованной анимации), фон медленно плывёт волнами.
"""
import json, math, os, random, subprocess, sys, wave
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import inserts, real, sfx

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
SHIRT = (226, 62, 62, 255)     # красная футболка Эмбер
SHORTS = (58, 110, 210, 255)   # синие шорты
WATCH = (240, 196, 72, 255)    # золотистые часы на руке, None — без часов
CHEST_LOGO = None              # белый знак на футболке (assets/logos/<имя>.svg), None — без логотипа


def character(d, ox, oy, s, st, seed):
    """ox, oy — центр головы (в пикселях SS); st — состояние (рот, глаза, руки, поворот turn: −1 влево … +1 вправо)."""
    tr = max(-1.0, min(1.0, st.get('turn', 0.0)))
    kx = 1 - 0.17 * abs(tr)                           # вполоборота корпус кажется уже
    B = lambda pts: [(x * kx + tr * 14, y) for x, y in pts]
    L = lambda pts, **k: line(d, P(B(pts) if k.get('body', True) else pts, ox, oy, s), seed + len(pts), w=k.get('w', 7) * s,
                             closed=k.get('closed', False), color=k.get('color', INK))
    F = lambda pts, fill=(255, 255, 255, 255), body=True: shape(d, P(B(pts) if body else pts, ox, oy, s), seed + len(pts) * 3,
                                                               fill=fill, w=7 * s)
    # тень на «полу» под ногами — герой стоит, а не висит в воздухе
    d.ellipse([*P([(-175, 668)], ox, oy, s)[0], *P([(185, 712)], ox, oy, s)[0]], fill=(40, 30, 60, 46))
    # ноги и стопы
    L([(-62, 560), (-66, 640)]); L([(62, 560), (70, 640)])
    F(ell(-88, 655, 52, 28)); F(ell(96, 655, 52, 28))
    # шорты
    F([(-128, 420), (128, 420), (138, 565), (18, 565), (2, 480), (-14, 565), (-138, 565)], fill=SHORTS)
    # руки (за футболкой — плечо, к кисти)
    la, ra = st['arm_l'], st['arm_r']
    lh = (-170 + 150 * math.cos(math.radians(la)), 245 + 150 * math.sin(math.radians(la)))
    rh = (170 + 150 * math.cos(math.radians(ra)), 245 + 150 * math.sin(math.radians(ra)))
    L([(-160, 250), lh]); L([(160, 250), rh])
    F(ell(lh[0], lh[1], 46, 44)); F(ell(rh[0], rh[1], 46, 44))
    # футболка
    F([(-36, 118), (36, 118), (108, 140), (190, 215), (160, 285), (124, 262), (130, 430), (-130, 430), (-124, 262),
       (-160, 285), (-190, 215), (-108, 140)], fill=SHIRT)
    if CHEST_LOGO:                                   # маленький логотип на груди (слева у героя = справа на экране)
        px = max(4, int(74 * s * SS))
        lg = inserts.logo_img(CHEST_LOGO, px, '#FFFFFF')
        d._image.alpha_composite(lg, (int(ox + (62 * kx + tr * 14) * s * SS - px / 2), int(oy + 205 * s * SS - px / 2)))
    if WATCH:                                        # часы на запястье (рука справа на экране), крутятся вместе с рукой
        sx, sy = 160, 250
        dx, dy = rh[0] - sx, rh[1] - sy; ln = math.hypot(dx, dy) or 1; ux, uy = dx / ln, dy / ln
        wx, wy = rh[0] - ux * 62, rh[1] - uy * 62    # чуть выше ладони
        nx, ny = -uy, ux
        F([(wx + nx * k1 + ux * k2, wy + ny * k1 + uy * k2) for k1, k2 in ((-26, -11), (26, -11), (26, 11), (-26, 11))],
          fill=(38, 38, 44, 255))                     # ремешок
        F(ell(wx, wy, 23, 23), fill=WATCH)                                                          # корпус
        shape(d, P(B(ell(wx, wy, 14, 14)), ox, oy, s), seed + 91, fill=(255, 255, 255, 255), w=2.5 * s, amp=0.6)   # циферблат
        line(d, P(B([(wx, wy), (wx + 8 * ux, wy + 8 * uy)]), ox, oy, s), seed + 92, w=2.5 * s, amp=0.3)
        line(d, P(B([(wx, wy), (wx + 10 * nx, wy + 10 * ny)]), ox, oy, s), seed + 93, w=2.5 * s, amp=0.3)
    L([(-36 + tr * 18, 120), (tr * 22, 150), (36 + tr * 18, 120)], w=5)     # ворот смещается к повороту
    # голова: сама чуть сдвигается, лицо и причёска — сильнее (вполоборота)
    hx = st['head_dx'] + tr * 8
    fx = hx + tr * 36
    F(ell(hx, 0, 124, 120), body=False)
    F([(x * (1 - 0.06 * abs(tr)) + hx + tr * 12, y) for x, y in HAIR], body=False)
    # глаза: дальний глаз чуть уже
    for ex in (-40, 40):
        far = (ex > 0) != (tr > 0)
        ew = 9 * (1 - 0.35 * abs(tr)) if far else 9
        exx = fx + ex * (1 - 0.18 * abs(tr))
        if st['blink']:
            L([(exx - 12, 34), (exx + 12, 34)], w=6, body=False)
        else:
            lk = st['look'] * 4 + tr * 5
            d.ellipse([*P([(exx - ew + lk, 24)], ox, oy, s)[0], *P([(exx + ew + lk, 44)], ox, oy, s)[0]], fill=INK)
    # рот
    m = st['mouth']
    if m == 0:
        L([(fx - 26, 74), (fx - 6, 77), (fx + 12, 73), (fx + 26, 75)], w=6, body=False)
    else:
        rw, rh_ = [0, 16, 22, 26, 20][m], [0, 7, 13, 19, 24][m]
        shape(d, P(ell(fx, 76, rw * (1 - 0.15 * abs(tr)), rh_, 28), ox, oy, s), seed + 77, fill=INK, w=5 * s, amp=1.2)


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


def txt(d, text, cx, cy, px, color=INK, mark=None, seed=0, maxw=None):
    if px < 4:
        return
    if maxw:
        wid = d.textlength(text, font=font(round(px * SS)))
        if wid > maxw * SS:
            px = px * maxw * SS / wid
    f = font(round(px * SS))
    x0, y0, x1, y1 = d.textbbox((cx, cy), text, font=f, anchor='mm')
    if mark:
        pad = 14 * SS
        shape(d, [(x0 - pad, y0 + 4 * SS), (x1 + pad, y0 - 2 * SS), (x1 + pad * 0.6, y1 + pad * 0.7), (x0 - pad * 0.7, y1 + pad * 0.5)],
              seed, fill=tuple(mark) + (255,), w=0.01, color=tuple(mark) + (255,), amp=1.5)
    d.text((cx, cy), text, font=f, fill=color, anchor='mm')


def ease_back(x):
    x = min(max(x, 0), 1); c = 1.7
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


# ---------- графики и таблицы («сцены») ----------
PALETTE = [(255, 206, 70), (120, 170, 255), (255, 120, 140), (110, 200, 140), (217, 119, 87)]


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def chart(d, c, a, seed):
    """c — описание из plan.json (kind: bars | iso | line | pie | table), a — сколько секунд сцена на экране."""
    cx, cy = 540 * SS, c.get('y', 660) * SS
    if c.get('title'):
        txt(d, c['title'], cx, cy - 430 * SS, 96 * min(1, ease(a / 0.4) * 1.0), mark=(255, 226, 90), seed=seed,
            maxw=c.get('title_w', 660))   # место справа под логотип в углу
    items, kind = c.get('items', []), c['kind']
    n = max(1, len(items))
    col = lambda i, it: tuple(it.get('color', PALETTE[i % len(PALETTE)])) + (255,)
    if kind in ('bars', 'iso'):
        base, left, width = cy + 290 * SS, cx - 400 * SS, 800 * SS
        line(d, [(left - 20 * SS, base), (left + width + 20 * SS, base)], seed, w=7)
        vmax = max(it['value'] for it in items) or 1
        bw = width / n * 0.55
        for i, it in enumerate(items):
            g = ease((a - 0.25 - i * 0.3) / 0.8)
            h = it['value'] / vmax * 520 * SS * g
            x0 = left + width / n * (i + 0.5) - bw / 2
            if h > 2:
                if kind == 'iso':
                    dx, dy = bw * 0.35, -bw * 0.25
                    top = tuple(min(255, int(v * 1.15 + 20)) for v in col(i, it)[:3]) + (255,)
                    side = tuple(int(v * 0.72) for v in col(i, it)[:3]) + (255,)
                    shape(d, [(x0 + bw, base), (x0 + bw + dx, base + dy), (x0 + bw + dx, base - h + dy), (x0 + bw, base - h)], seed + i, fill=side, w=6)
                    shape(d, [(x0, base - h), (x0 + bw, base - h), (x0 + bw + dx, base - h + dy), (x0 + dx, base - h + dy)], seed + i + 9, fill=top, w=6)
                shape(d, [(x0, base), (x0 + bw, base), (x0 + bw, base - h), (x0, base - h)], seed + i + 3, fill=col(i, it), w=6)
            txt(d, it['label'], x0 + bw / 2, base + 55 * SS, 58)
            if g > 0.95 and it.get('text'):
                txt(d, it['text'], x0 + bw / 2 + (bw * 0.17 if kind == 'iso' else 0), base - h - (bw * 0.25 if kind == 'iso' else 0) - 60 * SS, 64)
    elif kind == 'line':
        left, width, base = cx - 400 * SS, 800 * SS, cy + 290 * SS
        line(d, [(left, base - 560 * SS), (left, base), (left + width, base)], seed, w=6)
        vmax = max(it['value'] for it in items) or 1
        pts = [(left + 40 * SS + (width - 80 * SS) * i / max(1, n - 1), base - it['value'] / vmax * 500 * SS) for i, it in enumerate(items)]
        f = ease((a - 0.3) / 1.6) * (n - 1)
        k = int(f); part = pts[:k + 1]
        if k < n - 1:
            (x1, y1), (x2, y2) = pts[k], pts[k + 1]; r = f - k
            part = part + [(x1 + (x2 - x1) * r, y1 + (y2 - y1) * r)]
        if len(part) > 1:
            line(d, part, seed, w=11, color=(217, 119, 87, 255))
        for i, (x, y) in enumerate(pts[:k + 1]):
            d.ellipse((x - 14 * SS, y - 14 * SS, x + 14 * SS, y + 14 * SS), fill=INK)
            txt(d, items[i]['label'], x, base + 50 * SS, 54)
    elif kind == 'pie':
        tot = sum(it['value'] for it in items) or 1
        sweep = 360 * ease((a - 0.25) / 1.2); ang = -90.0
        for i, it in enumerate(items):
            span = 360 * it['value'] / tot
            vis = max(0.0, min(span, sweep - (ang + 90)))
            if vis > 1:
                pts = [(0, 0)] + ell(0, 0, 330, 330, 40, ang, ang + vis) + [(330 * math.cos(math.radians(ang + vis)), 330 * math.sin(math.radians(ang + vis)))]
                shape(d, P(pts, cx, cy, 1), seed + i, fill=col(i, it), w=7)
            if vis >= span - 1:
                mid = math.radians(ang + span / 2)
                txt(d, it['label'], cx + 200 * SS * math.cos(mid), cy + 200 * SS * math.sin(mid), 60)
            ang += span
    elif kind == 'table':
        rows, cols = items, c.get('cols', [])
        rh, tw = 120 * SS, 860 * SS
        top = cy - 300 * SS; left = cx - tw / 2
        widths = c.get('widths', [0.7, 0.3])
        nr = len(rows) + (1 if cols else 0)
        shape(d, [(left, top), (left + tw, top), (left + tw, top + rh * nr), (left, top + rh * nr)], seed, fill=(255, 255, 255, 255), w=7)
        for r in range(1, nr):
            line(d, [(left, top + rh * r), (left + tw, top + rh * r)], seed + r, w=5)
        xs = [left]
        for wdt in widths[:-1]:
            xs.append(xs[-1] + tw * wdt)
            line(d, [(xs[-1], top), (xs[-1], top + rh * nr)], seed + 40, w=5)
        y = top
        if cols:
            for j, h_ in enumerate(cols):
                txt(d, h_, xs[j] + tw * widths[j] / 2, y + rh / 2, 64, color=(217, 119, 87, 255))
            y += rh
        for i, row in enumerate(rows):
            g = ease((a - row.get('dt', 0.3 + i * 0.5)) / 0.3)
            if g > 0.05:
                txt(d, row['label'], xs[0] + tw * widths[0] / 2, y + rh / 2, 62 * g)
                v = row.get('value')
                if v is True or v is False:
                    icon(d, 'check' if v else 'cross', xs[1] + tw * widths[1] / 2, y + rh / 2, 0.55 * g, seed + i, a)
                elif v is not None:
                    txt(d, str(v), xs[1] + tw * widths[1] / 2, y + rh / 2, 62 * g)
            y += rh


CAM_DEFAULT = (540, 1050, 1.1)
CAM_SIDE = (180, 1470, 0.55)    # персонаж отходит в левый нижний угол, экран занимает график
CAM_ZOOM = (540, 1060, 2.1)     # крупный план лица


CAM_PUNCH = (540, 1110, 1.55)   # резкий наезд на лицо
POSES = {'shrug': (195, -15), 'arms_up': (238, -58), 'point_up': (128, -86), 'point_left': (182, -22),
         'point_right': (128, 2), 'explain': (158, 18)}


def cam_target(t, evs):
    """Куда смотрит камера и насколько резко туда «прыгает»."""
    for e in evs:
        if e['type'] == 'punch' and e['t0'] <= t < e['t1']:
            return CAM_PUNCH, 0.45
        if e['type'] == 'cam' and e['t0'] <= t < e['t1']:
            return tuple(e['cam']), (0.45 if e.get('snap') else 0.16)
    return cam_base(t, evs), 0.16


def cam_base(t, evs):
    for e in evs:
        if e['type'] == 'chart' and e['t0'] - 0.15 <= t < e['t1'] - 0.2:
            return e.get('cam', CAM_SIDE)
        if e['type'] == 'zoom' and e['t0'] - 0.1 <= t < e['t1'] - 0.15:
            return CAM_ZOOM
    return CAM_DEFAULT


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
        if 'x' not in e and e['type'] in ('icon', 'text', 'badge'):
            e['x'], e['y'] = SLOTS[k % len(SLOTS)]
        if e['type'] == 'kinetic':                       # время каждого слова фразы
            j = next((i for i, (w, t) in enumerate(words) if t >= t0 - 0.01), len(words))
            wt = []
            for tok in e['text'].split():
                k2 = next((i for i in range(j, min(j + 6, len(words))) if norm(words[i][0]) == norm(tok)), None)
                if k2 is not None:
                    wt.append(words[k2][1] - e['t0']); j = k2 + 1
                else:
                    wt.append((wt[-1] + 0.15) if wt else 0.0)
            e['wt'] = wt
        for it in e.get('chart', {}).get('items', []):
            if isinstance(it.get('at'), str):
                hits = [t for w, t in words if norm(w) == norm(it['at'])]
                if hits:
                    it['dt'] = hits[min(it.get('word_n', 1), len(hits)) - 1] - e['t0']
        evs.append(e)
    return evs


def punctuation(words_path, words):
    """Знаки препинания после каждого слова — из script.txt рядом с words.json (в words.json их нет)."""
    import re
    path = os.path.join(os.path.dirname(os.path.abspath(words_path)), 'script.txt')
    if not os.path.exists(path):
        return [''] * len(words)
    toks = [w for w in re.findall(r"[\w\-]+[.,!?…:;]*", open(path).read()) if any(ch.isalnum() for ch in w)]
    if len(toks) != len(words):
        return [''] * len(words)
    return [re.sub(r'^[\w\-]+', '', w) for w in toks]


def captions(words, dur, punct=None):
    """Фразы по 2–4 слова, смена на паузах и знаках препинания."""
    punct = punct or [''] * len(words)
    chunks, cur = [], []
    for i, (w, t) in enumerate(words):
        cur.append((w, t))
        nxt = words[i + 1][1] if i + 1 < len(words) else dur
        p = punct[i]
        end = any(ch in p for ch in '.!?…:') or (',' in p and len(cur) >= 2)
        if end or len(cur) >= 4 or nxt - t > 0.55 or (len(cur) >= 2 and len(w) > 9):
            chunks.append((cur[0][1], nxt, ' '.join(x for x, _ in cur))); cur = []
    if cur:
        chunks.append((cur[0][1], dur, ' '.join(x for x, _ in cur)))
    return chunks


def main(wav, words_path, plan_path, out):
    words = json.load(open(words_path)); plan = json.load(open(plan_path))
    rms, dur = loudness(wav)
    tail = plan.get('tail', 0.8)
    rms = np.concatenate([rms, np.zeros(int(tail * FPS))]); dur += tail
    evs = resolve(plan, words)
    caps = captions(words, dur, punctuation(words_path, words)) if plan.get('captions', True) else []
    grid = Grid()
    rnd = random.Random(9)
    blinks, t = set(), 1.1
    while t < dur:
        blinks.update(range(int(t * FPS), int(t * FPS) + 4)); t += rnd.uniform(2.0, 4.2)
    waves = [(e['t0'], e['t0'] + 1.4) for e in evs if e.get('wave')]
    inputs, graph, mixin = [], ['[1:a]apad[v0]'], ['[v0]']
    if plan.get('music'):                               # тихая музыка; под речью приглушается ещё сильнее
        inputs += ['-stream_loop', '-1', '-i', plan['music']]
        graph = ['[1:a]apad,asplit[v0][vs]', f"[2:a]volume={plan.get('music_volume', 1.0)}[m]",
                 '[m][vs]sidechaincompress=threshold=0.04:ratio=3:attack=40:release=600[md]']
        mixin.append('[md]')
    fx_path = None
    if plan.get('sfx'):                                 # звуки на появление элементов
        fx_path = out + '.sfx.wav'
        sfx.render(sfx.cues(evs), dur, fx_path, plan.get('sfx_volume', 1.0))
        inputs += ['-i', fx_path]
        graph.append(f'[{1 + len(mixin)}:a]anull[fx]'); mixin.append('[fx]')
    graph.append(''.join(mixin) + f'amix=inputs={len(mixin)}:duration=first:normalize=0[a]')
    audio = [*inputs, '-filter_complex', ';'.join(graph), '-map', '0:v', '-map', '[a]']
    layers = plan.get('bg_only') and plan.get('layers')   # слои для 3D-камеры: фон отдельно, Эмбер на прозрачном
    raw_in = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-']
    if layers:
        base = out.rsplit('.', 1)[0]
        ff = subprocess.Popen(raw_in + ['-t', f'{dur:.3f}', '-c:v', 'libvpx-vp9', '-pix_fmt', 'yuva420p', '-b:v', '0', '-crf', '18',
                               '-deadline', 'good', '-cpu-used', '5', '-row-mt', '1', '-auto-alt-ref', '0', '-an', base + '_char.webm'],
                              stdin=subprocess.PIPE)
        ff_grid = subprocess.Popen(raw_in + ['-t', f'{dur:.3f}', '-c:v', 'libx264', '-preset', 'slow', '-crf', '12', '-pix_fmt', 'yuv420p',
                                    '-movflags', '+faststart', base + '_grid.mp4'], stdin=subprocess.PIPE)
    else:
        ff = subprocess.Popen(raw_in + ['-i', wav, *audio, '-t', f'{dur:.3f}', '-c:v', 'libx264', '-preset', 'slow',
                               '-crf', '10' if plan.get('bg_only') else '15', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '256k', '-ar', '48000',
                               '-movflags', '+faststart', out], stdin=subprocess.PIPE)
    is_real = plan.get('style') == 'real'
    jumps = [e['t0'] for e in evs if e.get('jump')]
    cuts = [x for e in evs if e['type'] in ('chart', 'zoom') for x in (e['t0'], e['t1'] - 0.1) if x > 0.3]   # первый кадр — чёткий (это обложка)
    arms = [125.0, -25.0]
    bg_only = plan.get('bg_only')
    cam = list(cam_target(0, evs)[0])                       # с первого кадра — сразу нужный ракурс
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
        if plan.get('turn'):                                # поворот вслед за 3D-камерой (считает tools/reel.py)
            st['turn'] = plan['turn'][min(i, len(plan['turn']) - 1)]
        pose = next((e for e in evs if e['type'] == 'pose' and e['t0'] <= t < e['t1']), None)
        goal = [st['arm_l'], st['arm_r']]
        if pose:                                             # жест: руки плавно, но бодро идут в позу
            pl, pr = POSES[pose['pose']]
            goal = [pl + 4 * math.sin(t * 5), pr + 4 * math.sin(t * 5 + 1)]
        arms = [a + (g - a) * 0.28 for a, g in zip(arms, goal)]
        st['arm_l'], st['arm_r'] = arms
        layer = Image.new('RGBA', (W * SS, H * SS), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
        bob = 6 * math.sin(t * 2 * math.pi / 2.6) + (4 * min(v, 1) if talk else 0)
        for j0 in jumps:                                     # подпрыгивание
            if 0 <= t - j0 < 0.45:
                bob -= 70 * math.sin(math.pi * (t - j0) / 0.45)
        tgt, speed = cam_target(t, evs)
        cam = [c + (g - c) * speed for c, g in zip(cam, tgt)]  # плавный (или резкий) «отъезд» и «наезд»
        in_scene = tgt == CAM_SIDE or any(e['type'] == 'chart' and e['t0'] <= t < e['t1'] for e in evs)
        for e in evs:
            if e['type'] == 'chart' and e['t0'] <= t < e['t1'] and not is_real and not bg_only:
                a = t - e['t0']
                chart(d, e['chart'], a, 500 + boil * 13)
        character(d, cam[0] * SS, (cam[1] + bob * cam[2]) * SS, cam[2], st, 100 + boil * 7)
        for e in evs:
            if not (e['t0'] <= t < e['t1']) or e['type'] in ('chart', 'zoom', 'logo', 'card', 'kinetic', 'burst', 'pose', 'cam', 'punch') or is_real or bg_only:
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
        kinetic = any(e['type'] == 'kinetic' and e['t0'] <= t < e['t1'] for e in evs)   # не дублировать текст
        for c0, c1, text in caps:
            if c0 <= t < c1 and not kinetic and not bg_only:
                cap_y = 1250 if in_scene else (360 if tgt[2] > 1.6 else 760)
                txt(d, text, 640 * SS if in_scene else 540 * SS, cap_y * SS, 104, mark=(255, 255, 255), seed=boil, maxw=760 if in_scene else 960)
                break
        grid_frame = grid.draw(t)
        frame = Image.new('RGBA', (W, H), (0, 0, 0, 0)) if layers else grid_frame
        small = layer.reduce(SS)
        if plan.get('depth', True):                         # мягкая тень от фигуры — объём вместо «наклейки»
            a = small.split()[3].resize((W // 4, H // 4), Image.BILINEAR).filter(ImageFilter.GaussianBlur(5))
            a = a.resize((W, H), Image.BILINEAR).point(lambda v: v * 34 // 255)
            sh = Image.new('RGBA', (W, H), (40, 30, 70, 0)); sh.putalpha(a)
            frame.alpha_composite(sh, (16, 26))
        frame.alpha_composite(small)
        if is_real and not bg_only:                          # реалистичные вставки: сначала графики, потом остальное
            for e in sorted((e for e in evs if e['t0'] <= t < e['t1']), key=lambda e: e['type'] != 'chart'):
                a = t - e['t0']
                if e['type'] == 'chart':
                    real.chart(frame, e['chart'], a, e['t1'] - e['t0'])
                elif e['type'] == 'badge':
                    real.badge(frame, e, a)
                elif e['type'] == 'icon':
                    real.icon(frame, e, a)
                elif e['type'] == 'text':
                    (real.button if e.get('mark') else real.plain_text)(frame, e, a)
        for e in evs:                                        # «чистые» вставки поверх
            if e['t0'] <= t < e['t1'] and not bg_only:
                a = t - e['t0']
                if e['type'] == 'logo':
                    inserts.draw_logo(frame, e, a)
                elif e['type'] == 'card':
                    inserts.draw_card(frame, e, a)
                elif e['type'] == 'kinetic':
                    inserts.draw_kinetic(frame, e, a, e['wt'])
                elif e['type'] == 'burst':
                    (real.burst if is_real else inserts.draw_burst)(frame, e, a)
        if plan.get('corner_logo') and not bg_only:
            inserts.draw_spin_logo(frame, plan['corner_logo'], t)
        bl = max([0.0] + [1 - abs(t - ts) / 0.16 for ts in cuts])   # размытие на смене сцены
        if bl > 0.05:
            frame = frame.filter(ImageFilter.GaussianBlur(14 * bl))
            if layers:
                grid_frame = grid_frame.filter(ImageFilter.GaussianBlur(14 * bl))
        ff.stdin.write(frame.tobytes())
        if layers:
            ff_grid.stdin.write(grid_frame.tobytes())
    ff.stdin.close(); ff.wait()
    if layers:
        ff_grid.stdin.close(); ff_grid.wait()
        open(out, 'w').write('layers')                    # метка: подложка собрана слоями
    if fx_path:
        os.remove(fx_path)
    print('Готово:', out)


if __name__ == '__main__':
    main(*sys.argv[1:5])
