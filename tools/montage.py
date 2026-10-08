"""Монтаж короткого вертикального ролика в фирменном стиле (см. CLAUDE.md).

python3 tools/montage.py input/video.mp4 work/video/words.json plan.json output/video.mp4

plan.json:
{
  "fixes": {"клод": "Claude"},          # исправления распознанных слов
  "end": 14.6,                           # где обрезать конец (необязательно)
  "elements": [
    {"type": "title", "start": 0, "end": 4, "label": "день 1", "title": "Изучаю\\nнейросеть Claude"},
    {"type": "list", "start": 4, "end": 11.8, "label": "что умеет",
     "items": [[4.0, "Систематизирует бизнес"], [6.0, "Облегчает жизнь"]]},
    {"type": "bar", "start": 8, "end": 11, "label": "уровень", "name": "ИИ", "from": 0, "to": 99},
    {"type": "slide", "start": 11.8, "end": 14.4, "label": "главное", "title": "Заработок\\nбольших денег",
     "accent": "денег"}
  ]
}
Для title/list/bar можно указать "pos": "top" (по умолчанию) или "mid".
"""
import json, os, re, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, 'fonts')
W, H, FPS = 1080, 1920, 30

# ---- фирменный стиль: светлый ----
CREAM = (246, 244, 240)      # фон плашек и слайдов (светлый, тёплый белый)
INK = (20, 20, 22)           # основной текст
MUTED = (120, 116, 110)      # второстепенный текст
ACCENT = (217, 119, 87)      # акцент (коралловый, как у Claude)
GRID = (0, 0, 0, 14)         # еле заметная сетка на слайдах
F_TITLE = os.path.join(FONTS, 'Oswald-Bold.ttf')
F_LABEL = os.path.join(FONTS, 'JetBrainsMono-Bold.ttf')
F_SUB = os.path.join(FONTS, 'Inter-ExtraBold.ttf')
SUB_FONT_NAME = 'Inter ExtraBold'
FADE_IN, FADE_OUT, SLIDE = 0.35, 0.30, 50   # секунды / пиксели сдвига
MARGIN_X, TOP_Y, MID_Y, LOW_Y = 64, 110, 760, 1000


def font(path, size):
    return ImageFont.truetype(path, size)


def draw_label(d, xy, text, size=30, fill=ACCENT):
    f = font(F_LABEL, size); x, y = xy
    for ch in text.upper():
        d.text((x, y), ch, font=f, fill=fill)
        x += d.textlength(ch, font=f) + 3
    return x


def label_width(d, text, size=30):
    f = font(F_LABEL, size)
    return sum(d.textlength(c, font=f) + 3 for c in text.upper())


def card(w, h, alpha=242):
    img = Image.new('RGBA', (w + 24, h + 24), (0, 0, 0, 0))
    sh = Image.new('RGBA', img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((12, 18, w + 12, h + 18), 30, fill=(0, 0, 0, 70))
    from PIL import ImageFilter
    img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(10)))
    ImageDraw.Draw(img).rounded_rectangle((12, 12, w + 12, h + 12), 30, fill=CREAM + (alpha,))
    return img


def png_title(el, path):
    lines = el['title'].upper().split('\n'); ft = font(F_TITLE, 76)
    tmp = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    tw = max(max(tmp.textlength(l, font=ft) for l in lines), label_width(tmp, el.get('label', '')))
    w, h = int(tw) + 88, 80 + 88 * len(lines) + 24
    img = card(w, h); d = ImageDraw.Draw(img)
    draw_label(d, (56, 46), el.get('label', ''))
    for i, l in enumerate(lines):
        d.text((56, 84 + 88 * i), l, font=ft, fill=INK)
    img.save(path); return img.size


def png_list_item(el, i, path, width):
    n, text = i + 1, el['items'][i][1].upper()
    fn, ft = font(F_TITLE, 72), font(F_TITLE, 50)
    img = Image.new('RGBA', (width, 92), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    num = str(el.get('numbers', [n] * 99)[i])
    d.text((56, 2), num, font=fn, fill=ACCENT if num == '0' else INK)
    d.text((56 + 64, 18), text, font=ft, fill=INK)
    img.save(path)


def list_geometry(el):
    tmp = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    ft = font(F_TITLE, 50)
    tw = max([tmp.textlength(t.upper(), font=ft) + 64 for _, t in el['items']] + [label_width(tmp, el.get('label', ''))])
    return int(tw) + 112, 86 + 92 * len(el['items']) + 20


def png_list_bg(el, path):
    w, h = list_geometry(el)
    img = card(w, h); draw_label(ImageDraw.Draw(img), (56, 46), el.get('label', ''))
    img.save(path); return img.size


def png_bar(el, path, value):
    w, h = 520, 190
    img = card(w, h); d = ImageDraw.Draw(img)
    draw_label(d, (56, 46), el.get('label', ''))
    f = font(F_TITLE, 52)
    d.text((56, 84), el['name'].upper(), font=f, fill=INK)
    v = f'{int(round(value))}%'
    d.text((w - 32 - d.textlength(v, font=f), 84), v, font=f, fill=ACCENT if value == 0 else INK)
    d.rounded_rectangle((56, 160, w - 32, 172), 6, fill=(215, 208, 196))
    if value > 0:
        d.rounded_rectangle((56, 160, 56 + (w - 88) * value / 100, 172), 6, fill=INK)
    img.save(path)


def slide_layout(el):
    """Раскладка заголовка слайда по словам: [(слово, x, y, шрифт, плашка?)]."""
    tmp = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    lines = el['title'].upper().split('\n'); pill = el.get('pill', '').upper(); size = 160
    while max(tmp.textlength(l, font=font(F_TITLE, size)) for l in lines) > W - 2 * MARGIN_X - 40 and size > 60:
        size -= 4
    ft = font(F_TITLE, size); lh = int(size * 1.22); y0 = H // 2 - 140 - lh * len(lines) // 2
    sp = tmp.textlength(' ', font=ft); out = []
    for i, l in enumerate(lines):
        x = MARGIN_X; in_pill = bool(pill) and l.strip() == pill
        for w in l.split():
            out.append((w, x, y0 + lh * i, ft, in_pill))
            x += tmp.textlength(w, font=ft) + sp
    return out, y0, size


def png_slide_bg(el, path):
    img = Image.new('RGB', (W, H), CREAM); d = ImageDraw.Draw(img)
    line = tuple(int(v * (1 - GRID[3] / 255)) for v in CREAM)  # сетка: чуть темнее фона, без прозрачности
    for gx in range(0, W, 90):
        d.line((gx, 0, gx, H), fill=line, width=2)
    for gy in range(0, H, 90):
        d.line((0, gy, W, gy), fill=line, width=2)
    _, y0, _ = slide_layout(el)
    draw_label(d, (MARGIN_X + 6, y0 - 70), el.get('label', ''), size=34)
    img.save(path)


def png_word(word, ft, pill, accent, path):
    tmp = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    bb = tmp.textbbox((0, 0), word, font=ft); pad = 22 if pill else 0
    w, h = int(bb[2]) + 2 * pad + 4, int(ft.size * 1.35) + 2 * pad
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    if pill:
        d.rounded_rectangle((0, pad // 2, w - 1, h - pad // 2), 18, fill=INK)
    d.text((pad, pad), word, font=ft, fill=(255, 255, 255) if pill else (ACCENT if accent else INK))
    img.save(path); return pad


def word_times(el, words):
    """Каждому слову заголовка — момент, когда оно звучит (или равномерно, если не нашлось)."""
    norm = lambda w: ''.join(c for c in w.lower() if c.isalnum())
    lay, _, _ = slide_layout(el); a, b = el['start'], el['end']
    pool = [(norm(w), t) for w, t in words if a - 0.6 <= t < b]
    times, j, prev = [], 0, a
    for w, *_ in lay:
        hit = next((k for k in range(j, len(pool)) if pool[k][0] == norm(w)), None)
        if hit is not None:
            prev = max(prev, pool[hit][1]); j = hit + 1
        else:
            prev = prev + 0.18
        times.append(min(max(prev, a + 0.15), b - 0.3))
    return times


def ass_time(x):
    return f'{int(x // 3600)}:{int(x % 3600 // 60):02d}:{x % 60:05.2f}'


def build_subs(words, end, path, light=()):
    """Одно слово за раз, как в референсе: белое, жирное, по центру внизу."""
    head = ['[Script Info]', 'ScriptType: v4.00+', f'PlayResX: {W}', f'PlayResY: {H}', 'WrapStyle: 2', '',
            '[V4+ Styles]',
            'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, '
            'Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, '
            'MarginR, MarginV, Encoding',
            f'Style: Dark,{SUB_FONT_NAME},84,&H00161414,&H00161414,&H00161414,&H00000000,0,0,0,0,100,100,0,0,1,0,0,2,80,80,430,1',
            f'Style: Sub,{SUB_FONT_NAME},84,&H00FFFFFF,&H00FFFFFF,&H50000000,&H78000000,0,0,0,0,100,100,0,0,1,2.5,4,2,80,80,430,1',
            '', '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    ev = []
    for i, (w, s) in enumerate(words):
        if re.fullmatch(r'[А-Яа-яЁё\-]+', w):
            w = w.lower()  # субтитры строчными; латиницу (Claude) не трогаем
        e = words[i + 1][1] if i + 1 < len(words) else end
        e = min(e, s + 1.2)
        # лёгкий «поп»: слово появляется с 92% и за 0.12 с вырастает до 100%
        if any(a <= s + 0.05 < b for a, b in light):
            continue  # на слайде слова появляются в заголовке — субтитры не дублируем
        st = 'Sub'
        ev.append(f'Dialogue: 0,{ass_time(s)},{ass_time(e)},{st},,0,0,0,,'
                  r'{\blur0.6\fscx92\fscy92\t(0,120,\fscx100\fscy100)}' + w)
    open(path, 'w').write('\n'.join(head + ev) + '\n')


def main(src, words_path, plan_path, out):
    plan = json.load(open(plan_path))
    work = os.path.join(os.path.dirname(os.path.abspath(words_path)), 'gfx'); os.makedirs(work, exist_ok=True)
    dur = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', src]))
    end = min(plan.get('end', dur), dur)
    fixes = plan.get('fixes', {})
    words = [[fixes.get(w, w), s] for w, s in json.load(open(words_path)) if s < end]
    subs = os.path.join(work, 'subs.ass')
    light = [(e['start'] + 0.2, e['end']) for e in plan.get('elements', []) if e['type'] == 'slide' and e.get('reveal', True)]
    build_subs(words, end - 0.1, subs, light)

    inputs, layers = [], []

    def add(png, a, b, x, y, anim, fin=True, fout=True):
        layers.append(dict(png=png, a=a, b=b, x=x, y=y, anim=anim, fin=fin, fout=fout and b < end - 0.05))

    for k, el in enumerate(plan.get('elements', [])):
        a, b, t = el['start'], min(el['end'], end), el['type']
        y = {'mid': MID_Y, 'low': LOW_Y}.get(el.get('pos'), TOP_Y)
        if t == 'title':
            p = f'{work}/e{k}.png'; png_title(el, p); add(p, a, b, MARGIN_X - 12, y, 'up')
        elif t == 'list':
            p = f'{work}/e{k}.png'; png_list_bg(el, p); w, _ = list_geometry(el)
            add(p, a, b, MARGIN_X - 12, y, 'up')
            for i, (ts, _) in enumerate(el['items']):
                q = f'{work}/e{k}_{i}.png'; png_list_item(el, i, q, w)
                add(q, max(a, ts), b, MARGIN_X - 12, y + 12 + 84 + 92 * i, 'left')
        elif t == 'bar':
            steps = 12; frm, to = el.get('from', 0), el['to']; ramp = min(1.0, (b - a) / 2)
            cuts = [a] + [a + 0.3 + ramp * i / steps for i in range(1, steps + 1)] + [b]
            for i in range(steps + 1):
                q = f'{work}/e{k}_{i}.png'; png_bar(el, q, frm + (to - frm) * i / steps)
                add(q, cuts[i], cuts[i + 1], W - 520 - MARGIN_X - 12, y, 'up' if i == 0 else 'none',
                    fin=(i == 0), fout=(i == steps))
        elif t == 'slide':
            p = f'{work}/e{k}.png'; png_slide_bg(el, p); add(p, a, b, 0, 0, 'slide')
            acc = set(el.get('accent', '').upper().split())
            for i, ((w, x, yy, ft, pill), ts) in enumerate(zip(slide_layout(el)[0], word_times(el, words))):
                q = f'{work}/e{k}_{i}.png'; pad = png_word(w, ft, pill, w in acc, q)
                add(q, ts if el.get('reveal', True) else a, b, x - pad, yy - pad, 'up')

    graph = [f'[0:v]scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,crop={W}:{H},setsar=1,'
             f'fps={FPS},format=yuv420p[base]']
    last = 'base'
    for i, L in enumerate(layers):
        a, b = L['a'], L['b']; d = max(0.05, b - a)
        inputs += ['-loop', '1', '-framerate', str(FPS), '-t', f'{d:.3f}', '-i', L['png']]
        fi = 0.45 if L['anim'] == 'slide' else FADE_IN
        fx = ['format=rgba']
        if L['fin']: fx.append(f'fade=in:st=0:d={fi}:alpha=1')
        if L['fout']: fx.append(f'fade=out:st={max(0, d - FADE_OUT):.3f}:d={FADE_OUT}:alpha=1')
        graph.append(f'[{i + 1}:v]{",".join(fx)},setpts=PTS+{a:.3f}/TB[l{i}]')
        ease = f'pow(max(0\\,1-(t-{a:.3f})/{FADE_IN})\\,3)'
        xe = f"{L['x']}-{SLIDE}*{ease}" if L['anim'] == 'left' else str(L['x'])
        ye = f"{L['y']}+{SLIDE}*{ease}" if L['anim'] == 'up' else str(L['y'])
        graph.append(f"[{last}][l{i}]overlay=x='{xe}':y='{ye}':eof_action=pass:enable='between(t,{a:.3f},{b:.3f})'[v{i}]")
        last = f'v{i}'
    graph.append(f"[{last}]ass='{subs}':fontsdir='{FONTS}',fade=in:st=0:d=0.3,"
                 f"fade=out:st={end - 0.4:.3f}:d=0.4,format=yuv420p[vout]")
    graph.append(f'[0:a]atrim=0:{end:.3f},afade=in:st=0:d=0.15,afade=out:st={end - 0.4:.3f}:d=0.4,'
                 'loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[aout]')
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    cmd = ['ffmpeg', '-v', 'error', '-y', '-i', src, *inputs, '-filter_complex', ';'.join(graph),
           '-map', '[vout]', '-map', '[aout]', '-t', f'{end:.3f}',
           '-c:v', 'libx264', '-profile:v', 'high', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p',
           '-c:a', 'aac', '-b:a', '320k', '-ar', '48000', '-movflags', '+faststart', out]
    subprocess.run(cmd, check=True)
    print('Готово:', out)


if __name__ == '__main__':
    main(*sys.argv[1:5])
