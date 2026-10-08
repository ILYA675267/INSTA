"""«Чистые» вставки в стиле референса (IMG_8284): логотипы в кружках со «шлейфом», 3D-карточки
с наклоном и тенью, кинетический текст по словам, оранжевая «вспышка» Claude в углу, размытие на переходах.

Используется из tools/doodle.py. Логотипы — assets/logos/*.svg (список и фирменные цвета в index.json).
"""
import io, json, math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGOS = os.path.join(ROOT, 'assets', 'logos')
INTER = os.path.join(ROOT, 'fonts', 'Inter-ExtraBold.ttf')
ORANGE = (217, 119, 87)
_cache, _fonts = {}, {}
_index = json.load(open(os.path.join(LOGOS, 'index.json'))) if os.path.exists(os.path.join(LOGOS, 'index.json')) else {}


def inter(px):
    px = max(4, int(px))
    if px not in _fonts:
        _fonts[px] = ImageFont.truetype(INTER, px)
    return _fonts[px]


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def logo_img(name, px, color=None):
    """SVG-логотип → картинка px×px. color — цвет заливки (для одноцветных логотипов)."""
    import cairosvg
    key = ('logo', name, px, color)
    if key not in _cache:
        svg = open(os.path.join(LOGOS, name + '.svg')).read()
        col = color or (_index.get(name, {}).get('color')) or '#111111'
        svg = svg.replace('currentColor', col)
        if 'fill=' not in svg.split('>', 1)[0]:
            svg = svg.replace('<svg ', f'<svg fill="{col}" ', 1)
        png = cairosvg.svg2png(bytestring=svg.encode(), output_width=px, output_height=px)
        _cache[key] = Image.open(io.BytesIO(png)).convert('RGBA')
    return _cache[key]


def with_shadow(img, blur=26, dy=22, alpha=95):
    """Мягкая тень под объектом — главный источник ощущения «объёма»."""
    pad = blur * 3
    out = Image.new('RGBA', (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
    a = img.split()[3].point(lambda v: v * alpha // 255)
    sh = Image.new('RGBA', img.size, (0, 0, 0, 0)); sh.putalpha(a)
    out.alpha_composite(sh, (pad, pad + dy))
    out = out.filter(ImageFilter.GaussianBlur(blur))
    out.alpha_composite(img, (pad, pad))
    return out


def badge(name, size, dark=None):
    """Кружок с логотипом. dark=True — чёрный кружок и белый знак (как ChatGPT в референсе)."""
    key = ('badge', name, size, dark)
    if key not in _cache:
        if dark is None:
            dark = name == 'openai'
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
        d.ellipse((0, 0, size - 1, size - 1), fill=(24, 24, 26, 255) if dark else (255, 255, 255, 255))
        lg = logo_img(name, int(size * 0.58), '#FFFFFF' if dark else None)
        img.alpha_composite(lg, ((size - lg.width) // 2, (size - lg.height) // 2))
        _cache[key] = with_shadow(img)
    return _cache[key]


def card(spec, w=760, h=300):
    """Белая карточка: логотип слева, заголовок и подпись."""
    key = ('card', json.dumps(spec, sort_keys=True, ensure_ascii=False), w, h)
    if key not in _cache:
        img = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
        d.rounded_rectangle((0, 0, w - 1, h - 1), 44, fill=(255, 255, 255, 255))
        x = 48
        if spec.get('logo'):
            lg = logo_img(spec['logo'], int(h * 0.46))
            img.alpha_composite(lg, (x, (h - lg.height) // 2)); x += lg.width + 40
        title, sub = spec.get('title', ''), spec.get('sub', '')
        tf = inter(64)
        while d.textlength(title, font=tf) > w - x - 40 and tf.size > 30:
            tf = inter(tf.size - 4)
        d.text((x, h / 2 - (28 if sub else 0)), title, font=tf, fill=(20, 20, 22), anchor='lm')
        if sub:
            d.text((x, h / 2 + 46), sub, font=inter(40), fill=(130, 130, 136), anchor='lm')
        if spec.get('accent', True):
            d.rounded_rectangle((0, h - 14, w - 1, h - 1), 7, fill=ORANGE + (255,))
        _cache[key] = img
    return _cache[key]


def perspective(img, yaw):
    """Поворот плоской картинки вокруг вертикальной оси (yaw в градусах) — псевдо-3D."""
    w, h = img.size
    k = math.sin(math.radians(yaw)) * 0.22
    cw = w * math.cos(math.radians(yaw))
    near, far = h * (1 + abs(k)) / 2, h * (1 - abs(k)) / 2
    lh, rh = (far, near) if yaw > 0 else (near, far)
    W2, H2 = int(cw) + 2, int(h * (1 + abs(k))) + 2
    cy = H2 / 2
    dst = [(0, cy - lh), (cw, cy - rh), (cw, cy + rh), (0, cy + lh)]
    src = [(0, 0), (w, 0), (w, h), (0, h)]
    A, B = [], []
    for (x, y), (X, Y) in zip(dst, src):
        A += [[x, y, 1, 0, 0, 0, -X * x, -X * y], [0, 0, 0, x, y, 1, -Y * x, -Y * y]]; B += [X, Y]
    c = np.linalg.solve(np.array(A, float), np.array(B, float))
    return img.transform((W2, H2), Image.PERSPECTIVE, tuple(c), Image.BICUBIC)


def paste_center(frame, img, cx, cy, scale=1.0, alpha=1.0, blur=0):
    if scale <= 0.02 or alpha <= 0.02:
        return
    if abs(scale - 1) > 0.01:
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.BICUBIC)
    if blur > 0.5:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    if alpha < 0.99:
        img = img.copy(); img.putalpha(img.split()[3].point(lambda v: int(v * alpha)))
    frame.alpha_composite(img, (int(cx - img.width / 2), int(cy - img.height / 2)))


def draw_logo(frame, e, a):
    """Логотип выезжает слева со «шлейфом» (серая плашка), чуть покачивается, в конце уменьшается."""
    size = int(e.get('size', 230))
    cx, cy = e.get('x', 600), e.get('y', 420)
    dur = e['t1'] - e['t0']
    k_in = ease_out(a / 0.5)
    k_out = ease_out((dur - a) / 0.3)
    x = -size + (cx + size) * k_in
    if e.get('trail', True) and x > -50:
        d = ImageDraw.Draw(frame)
        th = size * 0.62
        d.rounded_rectangle((-60, cy - th / 2, x, cy + th / 2), int(th / 2), fill=(206, 206, 210, int(235 * k_out)))
    blur = (1 - k_in) * 10 + (1 - k_out) * 6
    paste_center(frame, badge(e['logo'], size, e.get('dark')), x, cy + 6 * math.sin(a * 2.4),
                 scale=0.6 + 0.4 * k_out, alpha=k_out, blur=blur)


def draw_card(frame, e, a):
    """3D-карточка: влетает снизу с поворотом, «дышит» наклоном, тень."""
    dur = e['t1'] - e['t0']
    k_in, k_out = ease_out(a / 0.55), ease_out((dur - a) / 0.3)
    yaw = (38 * (1 - k_in) + 10) * e.get('dir', 1) + 3 * math.sin(a * 1.6)
    img = with_shadow(perspective(card(e['card'], e.get('w', 760), e.get('h', 300)), yaw), blur=24, dy=26, alpha=80)
    paste_center(frame, img, e.get('x', 540), e.get('y', 470) + 140 * (1 - k_in) + 6 * math.sin(a * 2),
                 scale=0.85 + 0.15 * k_in, alpha=min(k_in * 1.4, 1) * k_out, blur=(1 - k_in) * 8 + (1 - k_out) * 8)


def draw_kinetic(frame, e, a, words_t):
    """Текст по словам: слово появляется серым и мелким, затем становится чёрным и жирным.
    pill — слово в чёрной плашке, которая «вытирается» слева направо."""
    d = ImageDraw.Draw(frame)
    toks = e['text'].split()
    px = e.get('px', 84); maxw = e.get('maxw', 900)
    lines, cur = [], []
    for tk in toks:
        trial = ' '.join(cur + [tk])
        if cur and d.textlength(trial, font=inter(px)) > maxw:
            lines.append(cur); cur = [tk]
        else:
            cur.append(tk)
    lines.append(cur)
    dur = e['t1'] - e['t0']; k_out = ease_out((dur - a) / 0.25)
    y = e.get('y', 420) - (len(lines) - 1) * px * 0.62
    idx = 0
    for ln in lines:
        widths = [d.textlength(w + ' ', font=inter(px)) for w in ln]
        x = e.get('x', 540) - sum(widths) / 2
        for w, wd in zip(ln, widths):
            ta = words_t[idx] if idx < len(words_t) else idx * 0.18
            g = ease_out((a - ta) / 0.28)
            idx += 1
            if g <= 0.01:
                x += wd; continue
            shade = int(175 * (1 - g) + 18 * g)
            col = (shade, shade, shade + 2, int(255 * min(1, g * 2) * k_out))
            yy = y + 18 * (1 - g)
            if e.get('pill') and w.strip('.,!?') == e['pill']:
                bw = d.textlength(w, font=inter(px))
                d.rounded_rectangle((x - 18, yy - px * 0.62, x - 18 + (bw + 36) * g, yy + px * 0.62), 16,
                                    fill=(20, 20, 22, int(255 * k_out)))
                d.text((x, yy), w, font=inter(px), fill=(255, 255, 255, int(255 * g * k_out)), anchor='lm')
            else:
                d.text((x, yy), w, font=inter(px * (0.86 + 0.14 * g)), fill=col, anchor='lm')
            x += wd
        y += px * 1.24


def draw_burst(frame, e, a):
    """Оранжевая «вспышка» Claude из угла кадра — переход между частями ролика."""
    dur = e['t1'] - e['t0']
    g = math.sin(math.pi * min(max(a / dur, 0), 1))
    if g <= 0.01:
        return
    corner = e.get('corner', 'tr')
    cx = {'tr': 1080, 'tl': 0, 'br': 1080, 'bl': 0}[corner]; cy = {'tr': 0, 'tl': 0, 'br': 1920, 'bl': 1920}[corner]
    d = ImageDraw.Draw(frame)
    rot = a * 50
    for k in range(12):
        ang = math.radians(rot + k * 30)
        r0, r1 = 40 * g, (260 + 50 * (k % 3)) * g
        w = int(46 * g) + 1
        x0, y0 = cx + r0 * math.cos(ang), cy + r0 * math.sin(ang)
        x1, y1 = cx + r1 * math.cos(ang), cy + r1 * math.sin(ang)
        d.line((x0, y0, x1, y1), fill=ORANGE + (255,), width=w)
        d.ellipse((x1 - w / 2, y1 - w / 2, x1 + w / 2, y1 + w / 2), fill=ORANGE + (255,))
