"""Мультяшный говорящий персонаж-подросток (бесплатно, рисуется кодом).

python3 tools/teen.py voice.wav out.mp4 characters/имя.json   — ролик: рот по голосу, моргание, «дыхание»
python3 tools/teen.py --preview characters/имя.json out.png    — картинка персонажа (рот закрыт / открыт)

Внешность задаётся в characters/*.json: кожа, волосы и причёска, глаза, одежда, аксессуары, комната.
"""
import json, math, os, random, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H, FPS = 1080, 1920, 30
SS = 2  # рисуем крупнее и уменьшаем — гладкие края

DEFAULT = {
    'skin': [250, 220, 196], 'skin_shade': [236, 192, 164], 'blush': [244, 160, 150],
    'hair': [70, 50, 40], 'hair_light': [104, 78, 62], 'hair_style': 'fringe',
    'iris': [92, 64, 44], 'brows': None,
    'top': [120, 170, 160], 'top_shade': [96, 146, 136], 'top_style': 'hoodie', 'accent': [255, 255, 255],
    'headphones': False, 'glasses': False, 'cap': None,
    'wall': [232, 226, 240], 'wall_dark': [214, 206, 226], 'desk': [52, 46, 60], 'plant': True,
}


def rgb(c, a=255):
    return tuple(int(v) for v in c) + (a,)


def S(*v):
    return [x * SS for x in v]


def layer(w, h):
    return Image.new('RGBA', (w * SS, h * SS), (0, 0, 0, 0))


def done(img):
    return img.resize((img.width // SS, img.height // SS), Image.LANCZOS)


def mix(a, b, t):
    return [a[i] * (1 - t) + b[i] * t for i in range(3)]


# ---------- комната ----------
def room(c):
    img = Image.new('RGB', (W, H), tuple(c['wall']))
    px = np.zeros((H, W, 3), np.float32)
    top, bot = np.array(c['wall'], np.float32), np.array(c['wall_dark'], np.float32)
    k = np.linspace(0, 1, H)[:, None, None]
    px[:] = top * (1 - k) + bot * k
    img = Image.fromarray(px.astype(np.uint8)).convert('RGBA')
    d = ImageDraw.Draw(img)
    # окно со светом слева
    d.rounded_rectangle((70, 260, 400, 820), 24, fill=rgb(mix(c['wall'], [255, 255, 255], 0.65)))
    d.rounded_rectangle((70, 260, 400, 820), 24, outline=rgb(mix(c['wall_dark'], [0, 0, 0], 0.15)), width=14)
    d.line((235, 260, 235, 820), fill=rgb(mix(c['wall_dark'], [0, 0, 0], 0.15)), width=12)
    d.line((70, 540, 400, 540), fill=rgb(mix(c['wall_dark'], [0, 0, 0], 0.15)), width=12)
    # полка справа
    d.rectangle((700, 560, 1040, 580), fill=rgb(mix(c['wall_dark'], [0, 0, 0], 0.25)))
    for i, (bw, bh, col) in enumerate([(40, 150, [240, 180, 90]), (34, 130, [110, 150, 210]), (46, 165, [230, 120, 110]), (30, 120, [140, 190, 150])]):
        x = 730 + sum(b[0] + 6 for b in [(40,), (34,), (46,), (30,)][:i])
        d.rounded_rectangle((x, 560 - bh, x + bw, 560), 6, fill=rgb(col))
    if c.get('plant'):
        d.polygon([(930, 560), (1000, 560), (990, 480), (940, 480)], fill=rgb([200, 120, 90]))
        for a in range(-60, 61, 30):
            r = math.radians(a - 90)
            d.ellipse((965 + 75 * math.cos(r) - 28, 470 + 75 * math.sin(r) - 16, 965 + 75 * math.cos(r) + 28, 470 + 75 * math.sin(r) + 16), fill=rgb([90, 160, 110]))
    # гирлянда-огоньки
    for i in range(12):
        x = 90 + i * 85; y = 150 + 30 * math.sin(i / 11 * math.pi)
        d.ellipse((x - 9, y - 9, x + 9, y + 9), fill=(255, 220, 140, 255))
    img = img.filter(ImageFilter.GaussianBlur(6))  # фон чуть размыт — персонаж «в фокусе»
    glow = Image.new('L', (W, H), 0)
    ImageDraw.Draw(glow).ellipse((W / 2 - 520, 380, W / 2 + 520, 1500), fill=110)
    img = Image.composite(Image.new('RGBA', (W, H), (255, 255, 255, 255)), img, glow.filter(ImageFilter.GaussianBlur(120)))
    return img


# ---------- туловище ----------
def body(c):
    w, h = 1000, 820
    img = layer(w, h); d = ImageDraw.Draw(img)
    top, sh = rgb(c['top']), rgb(c['top_shade'])
    if c.get('headphones'):
        d.arc(S(320, 120, 680, 420), 160, 380, fill=rgb([40, 40, 48]), width=26 * SS)   # дужка за шеей
    d.rounded_rectangle(S(110, 230, 890, 1000), 300 * SS, fill=top)                 # плечи
    if c['top_style'] == 'hoodie':
        d.ellipse(S(330, 190, 670, 350), fill=sh)                                   # капюшон за шеей
        d.ellipse(S(400, 205, 600, 315), fill=rgb(mix(c['top_shade'], [0, 0, 0], 0.35)))  # ворот изнутри
    d.rounded_rectangle(S(430, 0, 570, 290), 70 * SS, fill=rgb(c['skin_shade']))            # шея
    if c['top_style'] == 'hoodie':
        d.polygon(S(380, 290, 500, 380, 620, 290, 620, 320, 500, 410, 380, 320), fill=sh)
        a = rgb(c['accent'], 235)
        d.line(S(440, 360, 430, 520), fill=a, width=9 * SS); d.line(S(560, 360, 570, 520), fill=a, width=9 * SS)
        d.ellipse(S(418, 512, 444, 538), fill=a); d.ellipse(S(556, 512, 582, 538), fill=a)
        d.rounded_rectangle(S(300, 620, 700, 780), 60 * SS, outline=sh, width=10 * SS)  # карман
    else:  # футболка + рубашка нараспашку
        d.polygon(S(420, 250, 500, 360, 580, 250), fill=rgb(c['skin_shade']))
        d.polygon(S(110, 400, 400, 250, 470, 820, 110, 820), fill=sh)
        d.polygon(S(890, 400, 600, 250, 530, 820, 890, 820), fill=sh)
        d.line(S(400, 250, 470, 820), fill=rgb(c['accent']), width=8 * SS)
        d.line(S(600, 250, 530, 820), fill=rgb(c['accent']), width=8 * SS)
    if c.get('headphones'):
        hp = rgb([40, 40, 48])
        d.rounded_rectangle(S(300, 270, 380, 380), 30 * SS, fill=hp); d.rounded_rectangle(S(620, 270, 700, 380), 30 * SS, fill=hp)
        d.rounded_rectangle(S(316, 290, 364, 360), 20 * SS, fill=rgb(c['accent']))
        d.rounded_rectangle(S(636, 290, 684, 360), 20 * SS, fill=rgb(c['accent']))
    return done(img)


# ---------- голова ----------
def hair_back(d, c):
    hair = rgb(c['hair'])
    st = c['hair_style']
    if st == 'long':
        d.rounded_rectangle(S(85, 180, 515, 560), 180 * SS, fill=hair)


def hair_front(d, c):
    hair, hl = rgb(c['hair']), rgb(c['hair_light'])
    st = c['hair_style']
    d.pieslice(S(88, 70, 512, 470), 180, 360, fill=hair)                            # шапка волос
    d.ellipse(S(90, 220, 150, 370), fill=hair); d.ellipse(S(450, 220, 510, 370), fill=hair)    # виски
    if st == 'fringe':      # мягкая чёлка набок
        d.polygon(S(95, 280, 150, 150, 300, 110, 470, 160, 505, 300, 440, 250, 360, 300, 330, 230, 250, 310, 210, 250, 140, 330), fill=hair)
        d.arc(S(180, 120, 420, 260), 200, 300, fill=hl, width=10 * SS)
    elif st == 'quiff':     # зачёс вверх-набок, «перья»
        d.polygon(S(92, 300, 110, 170, 170, 90, 150, 40, 250, 70, 280, 10, 350, 60, 420, 20, 430, 90, 520, 80, 495, 180, 510, 300,
                    450, 220, 380, 250, 330, 200, 260, 245, 190, 210, 130, 290), fill=hair)
        d.line(S(200, 110, 270, 70, 340, 90), fill=hl, width=9 * SS, joint='curve')
        d.line(S(360, 110, 420, 80), fill=hl, width=9 * SS)
    elif st == 'curly':
        for x, y, r in [(140, 170, 66), (210, 110, 72), (300, 88, 76), (390, 110, 72), (460, 170, 64), (120, 260, 52), (480, 260, 50),
                        (200, 220, 58), (300, 205, 60), (400, 220, 58)]:
            d.ellipse(S(x - r, y - r, x + r, y + r), fill=hair)
    elif st == 'long':
        d.polygon(S(95, 300, 160, 140, 440, 140, 505, 300, 420, 240, 300, 270, 180, 240), fill=hair)
    if c.get('cap'):
        cap = rgb(c['cap'])
        d.chord(S(84, 60, 516, 430), 180, 360, fill=cap)
        d.rounded_rectangle(S(84, 225, 516, 262), 18 * SS, fill=rgb(mix(c['cap'], [0, 0, 0], 0.2)))
        d.ellipse(S(285, 52, 315, 82), fill=rgb(mix(c['cap'], [0, 0, 0], 0.2)))


def face_shape():
    pts = []
    for k in range(120):
        a = 2 * math.pi * k / 120
        sn = math.sin(a)
        rx = 200 * (1 - 0.22 * max(0.0, sn) ** 2.2)
        ry = 225 if sn < 0 else 268
        pts += [(300 + rx * math.cos(a)) * SS, (350 + ry * sn) * SS]
    return pts


def head(c, blink=0.0, mouth=0, look=0.0, brow=0.0):
    """blink 0..1 (1 — глаза закрыты); mouth 0..4; look −1..1 — взгляд; brow — подъём бровей."""
    w, h = 600, 700
    img = layer(w, h); d = ImageDraw.Draw(img)
    skin, shade = rgb(c['skin']), rgb(c['skin_shade'])
    hair_back(d, c)
    d.ellipse(S(62, 330, 142, 450), fill=shade); d.ellipse(S(458, 330, 538, 450), fill=shade)   # уши
    d.ellipse(S(84, 330, 124, 420), fill=rgb(c['blush'], 120)); d.ellipse(S(476, 330, 516, 420), fill=rgb(c['blush'], 120))
    d.polygon(face_shape(), fill=skin)                                              # лицо «яйцом»
    hair_front(d, c)
    # брови
    bc = rgb(c['brows'] or mix(c['hair'], [0, 0, 0], 0.25))
    by = 318 - brow * 10
    d.line(S(178, by + 6, 210, by - 6, 262, by - 2), fill=bc, width=14 * SS, joint='curve')
    d.line(S(338, by - 2, 390, by - 6, 422, by + 6), fill=bc, width=14 * SS, joint='curve')
    # глаза
    ex = 12 * look
    for x in (222, 378):
        top_y, bot_y = 350, 440
        if blink < 0.85:
            open_top = top_y + (bot_y - top_y) * blink * 0.9
            m = Image.new('L', (w * SS, h * SS), 0)
            ImageDraw.Draw(m).ellipse(S(x - 44, open_top, x + 44, bot_y), fill=255)
            eye = layer(w, h); e = ImageDraw.Draw(eye)
            e.ellipse(S(x - 44, top_y, x + 44, bot_y), fill=(255, 255, 255, 255))
            e.ellipse(S(x - 30 + ex, 362, x + 30 + ex, 434), fill=rgb(c['iris']))
            e.ellipse(S(x - 30 + ex, 362, x + 30 + ex, 434), outline=rgb(mix(c['iris'], [0, 0, 0], 0.4)), width=4 * SS)
            e.ellipse(S(x - 15 + ex, 382, x + 15 + ex, 416), fill=(24, 20, 26, 255))
            e.ellipse(S(x - 18 + ex, 368, x - 2 + ex, 386), fill=(255, 255, 255, 255))
            e.ellipse(S(x + 8 + ex, 406, x + 16 + ex, 414), fill=(255, 255, 255, 220))
            img.paste(eye, (0, 0), Image.fromarray(np.minimum(np.array(m), np.array(eye.split()[3]))))
            d.arc(S(x - 46, open_top - 2, x + 46, bot_y + 60 * (1 - blink)), 195, 345, fill=(40, 30, 34, 255), width=8 * SS)
        else:
            d.arc(S(x - 42, 370, x + 42, 430), 20, 160, fill=(40, 30, 34, 255), width=8 * SS)
    if c.get('glasses'):
        g = (36, 36, 44, 255)
        for x in (222, 378):
            d.rounded_rectangle(S(x - 66, 334, x + 66, 456), 44 * SS, outline=g, width=8 * SS)
        d.arc(S(282, 360, 318, 400), 200, 340, fill=g, width=8 * SS)
    # нос, щёки
    d.arc(S(282, 430, 322, 480), 220, 330, fill=shade, width=7 * SS)
    d.ellipse(S(140, 452, 210, 492), fill=rgb(c['blush'], 110)); d.ellipse(S(390, 452, 460, 492), fill=rgb(c['blush'], 110))
    # рот
    cx, my = 300, 532
    lip = (120, 54, 60, 255)
    if mouth == 0:
        d.arc(S(cx - 48, my - 36, cx + 48, my + 14), 25, 155, fill=lip, width=8 * SS)
    else:
        mw = [0, 36, 44, 50, 44][mouth]; mh = [0, 26, 40, 54, 64][mouth]
        top_y = my - 14
        d.ellipse(S(cx - mw, top_y - mh * 0.12, cx + mw, top_y + mh), fill=(96, 32, 42, 255))
        d.chord(S(cx - mw + 4, top_y - mh * 0.12, cx + mw - 4, top_y + mh * 0.45), 180, 360, fill=(255, 255, 255, 255))
        d.chord(S(cx - mw - 2, top_y - mh * 0.5, cx + mw + 2, top_y + mh * 0.25), 180, 360, fill=skin)
        if mh > 30:
            d.chord(S(cx - mw * 0.6, top_y + mh * 0.5, cx + mw * 0.6, top_y + mh * 1.1), 180, 360, fill=(232, 112, 118, 255))
            d.ellipse(S(cx - mw, top_y - mh * 0.12, cx + mw, top_y + mh), outline=(96, 32, 42, 255), width=3 * SS)
    return done(img)


# ---------- стол с микрофоном ----------
def desk(c):
    img = layer(W, 520); d = ImageDraw.Draw(img)
    d.rounded_rectangle(S(-40, 120, W + 40, 600), 30 * SS, fill=rgb(c['desk']))
    d.rectangle(S(0, 120, W, 140), fill=rgb(mix(c['desk'], [255, 255, 255], 0.15)))
    return done(img)


def mic(c):
    img = layer(360, 700); d = ImageDraw.Draw(img)
    arm = (44, 44, 52, 255)
    d.line(S(300, 690, 250, 300, 170, 170), fill=arm, width=16 * SS, joint='curve')
    d.rounded_rectangle(S(110, 20, 230, 230), 60 * SS, fill=(58, 58, 68, 255))
    for y in range(50, 200, 22):
        d.line(S(126, y, 214, y), fill=(84, 84, 96, 255), width=5 * SS)
    d.rounded_rectangle(S(100, 210, 240, 250), 16 * SS, fill=rgb(c['top']))
    return done(img)


def arms(c):
    img = layer(W, 360); d = ImageDraw.Draw(img)
    for x in (230, 850):
        d.rounded_rectangle(S(x - 120, 30, x + 120, 230), 90 * SS, fill=rgb(c['top']))
        d.rounded_rectangle(S(x - 120, 30, x + 120, 230), 90 * SS, outline=rgb(c['top_shade']), width=6 * SS)
        d.ellipse(S(x - 78, 140, x + 78, 262), fill=rgb(c['skin']))
        d.ellipse(S(x - 78, 140, x + 78, 262), outline=rgb(c['skin_shade']), width=5 * SS)
    return done(img)


class Rig:
    def __init__(self, c):
        self.c = c
        K = 1.18
        big = lambda im: im.resize((int(im.width * K), int(im.height * K)), Image.LANCZOS)
        self.bg, self.bd, self.dk, self.mc, self.ar = room(c), big(body(c)), desk(c), mic(c), arms(c)
        self.big = big
        self.cache = {}

    def head(self, blink, mouth, look, brow):
        key = (round(blink, 1), mouth, look, round(brow, 1))
        if key not in self.cache:
            self.cache[key] = self.big(head(self.c, *key))
        return self.cache[key]

    def frame(self, blink=0.0, mouth=0, look=0.0, brow=0.0, breath=0.0, nod=0.0, tilt=0.0):
        f = self.bg.copy()
        f.alpha_composite(self.bd, (W // 2 - self.bd.width // 2, int(905 + breath)))
        hd = self.head(blink, mouth, look, brow).rotate(tilt, resample=Image.BICUBIC)
        f.alpha_composite(hd, (W // 2 - hd.width // 2, int(395 + breath * 0.8 + nod)))
        f.alpha_composite(self.dk, (0, 1400))
        f.alpha_composite(self.ar, (0, int(1300 + breath * 0.3)))
        f.alpha_composite(self.mc, (W - 430, 880))
        return f


def loudness(wav_path):
    w = wave.open(wav_path)
    sr, n = w.getframerate(), w.getnframes()
    a = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768
    if w.getnchannels() > 1:
        a = a.reshape(-1, w.getnchannels()).mean(1)
    hop = sr // FPS; frames = int(math.ceil(len(a) / hop))
    rms = np.array([np.sqrt(np.mean(a[i * hop:(i + 1) * hop] ** 2) + 1e-9) for i in range(frames)])
    rms = (rms / (np.percentile(rms, 92) + 1e-9)) ** 0.8
    return np.convolve(rms, [0.25, 0.5, 0.25], mode='same'), len(a) / sr


def load(cfg_path):
    c = dict(DEFAULT)
    c.update(json.load(open(cfg_path)))
    return c


def preview(cfg_path, out):
    r = Rig(load(cfg_path))
    a = r.frame(mouth=0).convert('RGB'); b = r.frame(mouth=3, brow=0.6).convert('RGB')
    img = Image.new('RGB', (W * 2 + 20, H), (20, 20, 24))
    img.paste(a, (0, 0)); img.paste(b, (W + 20, 0))
    img.resize((img.width // 2, img.height // 2), Image.LANCZOS).save(out)
    print('Готово:', out)


def main(wav, out, cfg_path):
    r = Rig(load(cfg_path))
    rms, dur = loudness(wav)
    n = len(rms)
    random.seed(11)
    blinks, t = {}, 1.0
    while t < dur:
        f = int(t * FPS)
        for k, v in enumerate((0.5, 1.0, 1.0, 0.5)):
            blinks[f + k] = v
        t += random.uniform(2.0, 4.0)
    looks = {int(x * FPS): random.choice((-1.0, 0.0, 0.0, 1.0)) for x in np.arange(0.5, dur, 2.4)}
    ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', f'{W}x{H}',
                           '-r', str(FPS), '-i', '-', '-i', wav, '-map', '0:v', '-map', '1:a', '-shortest',
                           '-c:v', 'libx264', '-preset', 'medium', '-crf', '16', '-pix_fmt', 'yuv420p',
                           '-c:a', 'aac', '-b:a', '256k', '-ar', '48000', '-movflags', '+faststart', out], stdin=subprocess.PIPE)
    look, prev, brow = 0.0, 0, 0.0
    for i in range(n):
        t = i / FPS; v = rms[i]
        m = 0 if v < 0.10 else 1 if v < 0.25 else 2 if v < 0.45 else 3 if v < 0.75 else 4
        if abs(m - prev) > 1:
            m = prev + (1 if m > prev else -1)
        prev = m
        look = looks.get(i, look)
        brow += ((0.8 if v > 0.9 else 0.0) - brow) * 0.15
        talk = v > 0.10
        frame = r.frame(blink=blinks.get(i, 0.0), mouth=m, look=look, brow=brow,
                        breath=math.sin(t * 2 * math.pi / 3.4) * 6,
                        nod=min(v, 1.2) * 9 + math.sin(t * 2 * math.pi / 1.6) * 2.5 * talk,
                        tilt=math.sin(t * 2 * math.pi / 4.8) * 2.0 + (v - 0.4) * 1.4 * talk)
        ff.stdin.write(frame.tobytes())
    ff.stdin.close(); ff.wait()
    print('Готово:', out)


if __name__ == '__main__':
    if sys.argv[1] == '--preview':
        preview(sys.argv[2], sys.argv[3])
    else:
        main(*sys.argv[1:4])
