"""Реалистичные вставки (plan.json: "style": "real"): вместо рисовки — стекло, глянец, градиенты и мягкие тени.

- графики и таблицы — на «матовом стекле» (размытый фон + цветное свечение под стеклом, светлая кромка);
  столбики с градиентом и бликом, линия с заливкой, галочки — зелёные глянцевые кружки;
- кружки-номера — объёмные оранжевые «шарики» с бликом;
- иконки — эмодзи на стеклянной плитке (имя из doodle.py или своё: "emoji": "🚀");
- надпись с "mark" — настоящая кнопка с градиентом (например, «ПОДПИСАТЬСЯ»), без mark — чистый текст с тенью;
- вспышка — мягкий свет с лучами из угла.
Используется из tools/doodle.py.
"""
import math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from inserts import inter, ease_out, paste_center, ORANGE

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMOJI_FONT = next((p for p in (os.path.join(ROOT, 'fonts', 'NotoColorEmoji.ttf'),
                               '/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf') if os.path.exists(p)), None)
EMOJI = {'coin': '💰', 'heart': '❤️', 'bulb': '💡', 'check': '✅', 'cross': '❌', 'arrow': '👉', 'star': '⭐',
         'sparkle': '✨', 'question': '❓', 'exclaim': '❗', 'clock': '⏰', 'doc': '📄', 'code': '💻', 'chat': '💬',
         'pencil': '✏️', 'bookmark': '🔖'}
INK = (22, 22, 26)
GREY = (110, 112, 120)
_cache = {}


def ease_back(x):
    x = min(max(x, 0), 1); c = 1.7
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def rmask(w, h, r, ss=2):
    key = ('mask', w, h, r)
    if key not in _cache:
        m = Image.new('L', (w * ss, h * ss), 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), r * ss, fill=255)
        _cache[key] = m.resize((w, h), Image.LANCZOS)
    return _cache[key]


def mul_alpha(img, k):
    if k >= 0.999:
        return img
    img = img.copy(); img.putalpha(img.split()[3].point(lambda v: int(v * k))); return img


def shadow(w, h, r, blur=30, strength=80):
    key = ('shadow', w, h, r, blur, strength)
    if key not in _cache:
        pad = blur * 3
        m = Image.new('L', (w + pad * 2, h + pad * 2), 0)
        m.paste(rmask(w, h, r).point(lambda v: v * strength // 255), (pad, pad))
        m = m.filter(ImageFilter.GaussianBlur(blur))
        img = Image.new('RGBA', m.size, (20, 20, 40, 0)); img.putalpha(m)
        _cache[key] = img
    return _cache[key]


def glow(w, h, colors):
    """Цветные размытые пятна под стеклом — без них «стекло» на белом фоне не читается."""
    key = ('glow', w, h, tuple(colors))
    if key not in _cache:
        spots = [(0.12, 0.15, 0.36), (0.9, 0.85, 0.4), (0.85, 0.1, 0.24)]
        rmax = max(spots, key=lambda s: s[2])[2] * min(w, h)
        pad = int(rmax + 150)                    # с запасом: размытие не должно упираться в край картинки
        img = Image.new('RGBA', (w + pad * 2, h + pad * 2), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
        for (fx, fy, fr), col in zip(spots, colors):
            r = fr * min(w, h)
            cx, cy = pad + fx * w, pad + fy * h
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=tuple(col) + (150,))
        _cache[key] = img.filter(ImageFilter.GaussianBlur(70))
    return _cache[key]


def glass(frame, cx, cy, w, h, r=46, k=1.0, colors=((255, 170, 120), (140, 180, 255), (255, 220, 120)), tint=0.5):
    """Панель матового стекла с центром (cx, cy). k — прозрачность/появление 0..1."""
    w, h = int(w), int(h); r = min(int(r), w // 2, h // 2)
    if k <= 0.02 or w < 24 or h < 24:
        return
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    sh = shadow(w, h, r)
    frame.alpha_composite(mul_alpha(sh, k * 0.9), (x0 - (sh.width - w) // 2, y0 - (sh.height - h) // 2 + 22))
    if colors:
        g = glow(w, h, colors)
        frame.alpha_composite(mul_alpha(g, k), (x0 - (g.width - w) // 2, y0 - (g.height - h) // 2))
    bx0, by0, bx1, by1 = max(0, x0), max(0, y0), min(frame.width, x0 + w), min(frame.height, y0 + h)
    if bx1 <= bx0 or by1 <= by0:
        return
    crop = frame.crop((bx0, by0, bx1, by1)).convert('RGB')
    small = crop.resize((max(1, crop.width // 4), max(1, crop.height // 4)), Image.BILINEAR).filter(ImageFilter.GaussianBlur(6))
    frost = Image.blend(small.resize(crop.size, Image.BICUBIC), Image.new('RGB', crop.size, (255, 255, 255)), tint)
    # блик: сверху стекло светлее
    hl = np.linspace(1, 0, crop.height)[:, None] ** 2 * 40
    arr = np.clip(np.asarray(frost, np.float32) + hl[..., None], 0, 255).astype(np.uint8)
    panel = Image.fromarray(arr).convert('RGBA')
    m = rmask(w, h, r).crop((bx0 - x0, by0 - y0, bx1 - x0, by1 - y0)).point(lambda v: int(v * k))
    panel.putalpha(m)
    frame.alpha_composite(panel, (bx0, by0))
    # светлая кромка
    edge = Image.new('RGBA', (w, h), (0, 0, 0, 0)); ed = ImageDraw.Draw(edge)
    ed.rounded_rectangle((1, 1, w - 2, h - 2), r, outline=(255, 255, 255, int(220 * k)), width=3)
    ed.rounded_rectangle((4, 4, w - 5, h - 5), r - 3, outline=(255, 255, 255, int(60 * k)), width=2)
    frame.alpha_composite(edge, (x0, y0))


def text(frame, s, x, y, px, color=INK, anchor='mm', k=1.0, font=None, alpha=255):
    """Текст через отдельный слой — чтобы полупрозрачность смешивалась с фоном, а не затирала его."""
    if k <= 0.02 or not s:
        return
    f = font or inter(px)
    x0, y0, x1, y1 = ImageDraw.Draw(Image.new('L', (1, 1))).textbbox((0, 0), s, font=f, anchor=anchor)
    im = Image.new('RGBA', (x1 - x0 + 6, y1 - y0 + 6), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((3 - x0, 3 - y0), s, font=f, fill=tuple(color[:3]) + (int(alpha * k),), anchor=anchor)
    frame.alpha_composite(im, (int(x + x0 - 3), int(y + y0 - 3)))


def hline(frame, x0, x1, y, alpha, width=2, color=(40, 40, 60)):
    im = Image.new('RGBA', (int(x1 - x0), width), tuple(color) + (int(alpha),))
    frame.alpha_composite(im, (int(x0), int(y - width / 2)))


def fit(s, px, maxw):
    f = inter(px); d = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    while d.textlength(s, font=f) > maxw and f.size > 18:
        f = inter(f.size - 2)
    return f


def sphere(size, color=ORANGE):
    """Глянцевый шарик: объём градиентом, блик сверху-слева, мягкая тень."""
    key = ('sphere', size, tuple(color))
    if key not in _cache:
        S = size * 2
        yy, xx = np.mgrid[0:S, 0:S] / S - 0.5
        rr = np.sqrt(xx ** 2 + yy ** 2)
        light = np.clip(1.22 - np.sqrt((xx + 0.18) ** 2 + (yy + 0.22) ** 2) * 0.9, 0.82, 1.22)
        rgb = np.clip(np.array(color, np.float32)[None, None, :] * light[..., None], 0, 255)
        a = np.clip((0.5 - rr) * S, 0, 1) * 255
        img = Image.fromarray(np.dstack([rgb, a]).astype(np.uint8), 'RGBA')
        hl = Image.new('RGBA', (S, S), (0, 0, 0, 0))
        ImageDraw.Draw(hl).ellipse((S * 0.2, S * 0.08, S * 0.62, S * 0.34), fill=(255, 255, 255, 150))
        img.alpha_composite(hl.filter(ImageFilter.GaussianBlur(S * 0.04)))
        img = img.resize((size, size), Image.LANCZOS)
        pad = size // 2
        out = Image.new('RGBA', (size + pad * 2, size + pad * 2), (0, 0, 0, 0))
        sh = Image.new('L', out.size, 0)
        ImageDraw.Draw(sh).ellipse((pad + size * 0.1, pad + size * 0.25, pad + size * 0.9, pad + size * 1.05), fill=110)
        shi = Image.new('RGBA', out.size, (90, 40, 20, 0)); shi.putalpha(sh.filter(ImageFilter.GaussianBlur(size * 0.12)))
        out.alpha_composite(shi); out.alpha_composite(img, (pad, pad))
        _cache[key] = out
    return _cache[key]


def emoji(ch, px):
    key = ('emoji', ch, px)
    if key not in _cache:
        if not EMOJI_FONT:
            return None
        f = ImageFont.truetype(EMOJI_FONT, 109)
        img = Image.new('RGBA', (160, 160), (0, 0, 0, 0))
        ImageDraw.Draw(img).text((80, 80), ch, font=f, embedded_color=True, anchor='mm')
        img = img.crop(img.getbbox() or (0, 0, 160, 160))
        sc = px / max(img.size)
        _cache[key] = img.resize((max(1, int(img.width * sc)), max(1, int(img.height * sc))), Image.LANCZOS)
    return _cache[key]


def check(frame, cx, cy, size, k, ok=True):
    """Зелёная глянцевая галочка (или красный крестик) в кружке."""
    if k <= 0.02:
        return
    s = int(size * k)
    if s < 4:
        return
    paste_center(frame, sphere(s, (60, 190, 110) if ok else (230, 80, 80)), cx, cy + s * 0.08)
    lay = Image.new('RGBA', (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(lay); w = max(2, int(s * 0.12)); c = s / 2
    if ok:
        d.line([(c - s * 0.22, c), (c - s * 0.05, c + s * 0.18), (c + s * 0.25, c - s * 0.17)], fill=(255, 255, 255, 255), width=w, joint='curve')
    else:
        for sx in (-1, 1):
            d.line([(c - s * 0.18 * sx, c - s * 0.18), (c + s * 0.18 * sx, c + s * 0.18)], fill=(255, 255, 255, 255), width=w)
    frame.alpha_composite(lay, (int(cx - c), int(cy - c)))


def vgrad_bar(w, h, color, r):
    key = ('bar', w, h, tuple(color), r)
    if key not in _cache:
        top = np.array([min(255, c * 1.18 + 25) for c in color], np.float32)
        bot = np.array([c * 0.82 for c in color], np.float32)
        g = np.linspace(0, 1, h)[:, None, None]
        rgb = top * (1 - g) + bot * g
        rgb = np.repeat(rgb, w, axis=1)
        sheen = np.clip(1 - np.abs(np.linspace(-1, 1, w) + 0.45) * 3, 0, 1)[None, :, None] * 45   # вертикальный блик
        rgb = np.clip(rgb + sheen, 0, 255).astype(np.uint8)
        img = Image.fromarray(rgb, 'RGB').convert('RGBA')
        m = Image.new('L', (w, h + r), 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h + r - 1), r, fill=255)
        img.putalpha(m.crop((0, 0, w, h)))
        _cache[key] = img
    return _cache[key]


PALETTE = [(255, 176, 60), (95, 150, 255), (255, 100, 120), (60, 190, 120), (217, 119, 87)]


def chart(frame, c, a, dur):
    k_in, k_out = ease_out(a / 0.45), ease_out((dur - a) / 0.3)
    k = min(k_in, k_out)
    if k <= 0.02:
        return
    kind, items = c['kind'], c.get('items', [])
    n = max(1, len(items))
    cy = c.get('y', 660) + 60 * (1 - k_in)
    W_, H_ = 900, {'table': 150 + 112 * (n + (1 if c.get('cols') else 0)), 'pie': 900}.get(kind, 860)
    top = cy - (430 if kind != 'table' else 360)
    pcy = top + H_ / 2
    glass(frame, 540, pcy, W_, H_, k=k)
    if c.get('title'):
        text(frame, c['title'], 540, top + 70, 0, font=fit(c['title'], 60, W_ - 120), k=k)
    col = lambda i, it: tuple(it.get('color', PALETTE[i % len(PALETTE)]))
    if kind in ('bars', 'iso'):
        base, left, width = top + H_ - 120, 540 - 360, 720
        hline(frame, left - 10, left + width + 10, base, 70 * k, 3)
        vmax = max(it['value'] for it in items) or 1
        bw = int(width / n * 0.5)
        for i, it in enumerate(items):
            g = ease_out((a - 0.25 - i * 0.3) / 0.8)
            h = int(it['value'] / vmax * 520 * g)
            x0 = left + width / n * (i + 0.5) - bw / 2
            if h > 3:
                sh = shadow(bw, h, 18, blur=16, strength=60)
                frame.alpha_composite(mul_alpha(sh, k), (int(x0 - (sh.width - bw) / 2 + 8), int(base - h - (sh.height - h) / 2 + 6)))
                frame.alpha_composite(mul_alpha(vgrad_bar(bw, h, col(i, it), 18), k), (int(x0), int(base - h)))
            text(frame, it['label'], x0 + bw / 2, base + 45, 40, color=GREY, k=k)
            if g > 0.9 and it.get('text'):
                text(frame, it['text'], x0 + bw / 2, base - h - 42, 50, k=k * min(1, (g - 0.9) * 10))
    elif kind == 'line':
        left, width, base = 540 - 360, 720, top + H_ - 120
        vmax = max(it['value'] for it in items) or 1
        pts = [(left + 30 + (width - 60) * i / max(1, n - 1), base - it['value'] / vmax * 480) for i, it in enumerate(items)]
        f = ease_out((a - 0.3) / 1.6) * (n - 1); kk = int(f); part = pts[:kk + 1]
        if kk < n - 1:
            (x1, y1), (x2, y2) = pts[kk], pts[kk + 1]; r = f - kk
            part = part + [(x1 + (x2 - x1) * r, y1 + (y2 - y1) * r)]
        lay = Image.new('RGBA', frame.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        if len(part) > 1:
            d.polygon(part + [(part[-1][0], base), (part[0][0], base)], fill=ORANGE + (int(55 * k),))
            d.line(part, fill=ORANGE + (int(255 * k),), width=9, joint='curve')
        d.line((left, base, left + width, base), fill=(40, 40, 50, int(60 * k)), width=3)
        frame.alpha_composite(lay)
        for i, (x, y) in enumerate(pts[:kk + 1]):
            paste_center(frame, sphere(34, ORANGE), x, y + 8, alpha=k)
            text(frame, items[i]['label'], x, base + 42, 38, color=GREY, k=k)
    elif kind == 'pie':
        tot = sum(it['value'] for it in items) or 1
        sweep = 360 * ease_out((a - 0.25) / 1.2); ang = -90.0
        lay = Image.new('RGBA', frame.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
        R, cxp, cyp = 280, 540, pcy + 30
        for i, it in enumerate(items):
            span = 360 * it['value'] / tot; vis = max(0.0, min(span, sweep - (ang + 90)))
            if vis > 0.5:
                d.pieslice((cxp - R, cyp - R, cxp + R, cyp + R), ang, ang + vis, fill=col(i, it) + (int(255 * k),))
            ang += span
        d.ellipse((cxp - R * 0.55, cyp - R * 0.55, cxp + R * 0.55, cyp + R * 0.55), fill=(0, 0, 0, 0))
        hole = Image.new('L', frame.size, 255)
        ImageDraw.Draw(hole).ellipse((cxp - R * 0.55, cyp - R * 0.55, cxp + R * 0.55, cyp + R * 0.55), fill=0)
        lay.putalpha(Image.fromarray(np.minimum(np.asarray(lay.split()[3]), np.asarray(hole))))
        frame.alpha_composite(lay)
        ang = -90.0
        for i, it in enumerate(items):
            span = 360 * it['value'] / tot
            if sweep - (ang + 90) >= span - 1:
                mid = math.radians(ang + span / 2)
                text(frame, it['label'], cxp + R * 0.78 * math.cos(mid), cyp + R * 0.78 * math.sin(mid), 40, color=(255, 255, 255), k=k)
            ang += span
    elif kind == 'table':
        cols, widths = c.get('cols', []), c.get('widths', [0.72, 0.28])
        rh, tw = 112, W_ - 80
        y = top + 140; left = 540 - tw / 2
        xs = [left]
        for wd in widths[:-1]:
            xs.append(xs[-1] + tw * wd)
        if cols:
            for j, h_ in enumerate(cols):
                text(frame, h_.upper(), xs[j] + tw * widths[j] / 2, y + rh / 2, 34, color=GREY, k=k)
            y += rh
        for i, row in enumerate(items):
            g = ease_out((a - row.get('dt', 0.3 + i * 0.5)) / 0.3)
            hline(frame, left + 10, left + tw - 10, y, 30 * k, 2)
            if g > 0.03:
                ty = y + rh / 2 + 16 * (1 - g)
                text(frame, row['label'], left + 30, ty, 0, anchor='lm', font=fit(row['label'], 48, tw * widths[0] - 40), k=k * g)
                v = row.get('value')
                if v is True or v is False:
                    check(frame, xs[1] + tw * widths[1] / 2, y + rh / 2, 66, k * ease_back((a - row.get('dt', 0.3 + i * 0.5)) / 0.35), ok=v)
                elif v is not None:
                    text(frame, str(v), xs[1] + tw * widths[1] / 2, ty, 48, color=ORANGE, k=k * g)
            y += rh


def pop_k(e, a):
    dur = e['t1'] - e['t0']
    return ease_back(a / 0.35) * ease_out((dur - a) / 0.25) * e.get('size', 1.0)


def badge(frame, e, a):
    k = pop_k(e, a)
    if k <= 0.03:
        return
    s = int(124 * k)
    cx, cy = e['x'], e['y'] + 6 * math.sin(a * 3)
    paste_center(frame, sphere(s, tuple(e.get('color', ORANGE))), cx, cy + s * 0.1)
    text(frame, e['text'], cx + 2, cy + 3, int(70 * k), color=(120, 50, 30), alpha=110)
    text(frame, e['text'], cx, cy, int(70 * k), color=(255, 255, 255))


def icon(frame, e, a):
    k = pop_k(e, a)
    if k <= 0.03:
        return
    ch = e.get('emoji') or EMOJI.get(e.get('icon'), '✨')
    cx, cy = e['x'], e['y'] + 8 * math.sin(a * 3)
    s = int(170 * k)
    glass(frame, cx, cy, s, s, r=int(s * 0.28), k=min(1, k), colors=((255, 190, 140), (150, 190, 255), (255, 230, 150)), tint=0.45)
    em = emoji(ch, int(s * 0.62))
    if em is not None:
        paste_center(frame, em, cx, cy)


def button(frame, e, a):
    """Кнопка с градиентом (оранжевый → розовый), белый текст, тень, «нажатие» в середине показа."""
    k = pop_k(e, a)
    if k <= 0.03:
        return
    label = e['text']; px = int(e.get('btn_px', 64))
    f = inter(px); d0 = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    w, h = int(d0.textlength(label, font=f) + px * 1.6), int(px * 1.9)
    key = ('btn', label, px)
    if key not in _cache:
        g = np.linspace(0, 1, w)[None, :, None]
        c1, c2 = np.array([255, 140, 70], np.float32), np.array([240, 70, 120], np.float32)
        rgb = np.repeat(c1 * (1 - g) + c2 * g, h, axis=0)
        rgb[: h // 2] += 18
        img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), 'RGB').convert('RGBA')
        img.putalpha(rmask(w, h, h // 2))
        ImageDraw.Draw(img).text((w / 2, h / 2), label, font=f, fill=(255, 255, 255, 255), anchor='mm')
        pad = 40
        out = Image.new('RGBA', (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
        sh = shadow(w, h, h // 2, blur=18, strength=90)
        out.alpha_composite(sh.resize(out.size), (0, 14)); out.alpha_composite(img, (pad, pad))
        _cache[key] = out
    dur = e['t1'] - e['t0']
    press = 1 - 0.07 * math.sin(math.pi * min(max((a - dur * 0.5) / 0.25, 0), 1))
    paste_center(frame, _cache[key], e['x'], e['y'] + 4 * math.sin(a * 3), scale=k * press)


def plain_text(frame, e, a):
    k = pop_k(e, a)
    if k <= 0.03:
        return
    px = int(e.get('px', 92) * 0.72 * k)
    text(frame, e['text'], e['x'] + 3, e['y'] + 5, px, color=(0, 0, 0), alpha=60)
    text(frame, e['text'], e['x'], e['y'], px, color=tuple(e.get('color', INK)))


def burst(frame, e, a):
    """Мягкая световая вспышка из угла: тёплое свечение + размытые лучи."""
    dur = e['t1'] - e['t0']
    g = math.sin(math.pi * min(max(a / dur, 0), 1))
    if g <= 0.02:
        return
    corner = e.get('corner', 'tr')
    cx = 1080 if corner in ('tr', 'br') else 0; cy = 0 if corner in ('tr', 'tl') else 1920
    sc = 4
    lay = Image.new('RGBA', (1080 // sc, 1920 // sc), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    R = 520 * g / sc
    for i in range(10, 0, -1):
        r = R * i / 10
        d.ellipse((cx / sc - r, cy / sc - r, cx / sc + r, cy / sc + r), fill=ORANGE + (int(26 * g),))
    rot = a * 40
    for kk in range(12):
        ang = math.radians(rot + kk * 30); r1 = (300 + 60 * (kk % 3)) * g / sc
        d.line((cx / sc, cy / sc, cx / sc + r1 * math.cos(ang), cy / sc + r1 * math.sin(ang)),
               fill=(255, 190, 150, int(170 * g)), width=max(1, int(9 * g)))
    lay = lay.filter(ImageFilter.GaussianBlur(3)).resize((1080, 1920), Image.BICUBIC)
    frame.alpha_composite(lay)
