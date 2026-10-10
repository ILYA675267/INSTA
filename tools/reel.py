"""Ролик на Remotion: персонаж и фон — tools/doodle.py, вставки и субтитры — remotion/src/Reel.tsx.

python3 tools/reel.py work/<имя>/ output/<имя>.mp4

В папке: voice.wav, words.json, script.txt, plan.json. План — список событий, как у doodle.py ("at" — слово,
"word_n" — какое вхождение, "dur" — сколько держать). Типы:
  для камеры и персонажа (рисует doodle.py): zoom, punch, cam, pose; "jump": true — подпрыгнуть; "side": true — персонаж
    отходит в угол на время события (таблицы, графики);
  вставки (рисует Remotion): badge, flare, card, tiles, kinetic, table, bars, grid, fan, moneybutton, coin, button.
  Вложенные элементы (tiles.items, table.rows, grid.items, bars.items) тоже берут "at"/"word_n"; у плиток
  "mark": "check"|"cross" и "mark_at" — когда поставить галочку/зачеркнуть; у fan — "copies_at": [слова].
Звуки, музыка (тихая бодрая), микс — автоматически.
"""
import json, math, os, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doodle, music, sfx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REM = os.path.join(ROOT, 'remotion')
BROWSER = '/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell'
BG_TYPES = ('zoom', 'punch', 'cam', 'pose', 'orbit')
SIDE_MODE_TYPES = ('table', 'bars', 'phone')
SFX = {'globe': 'whoosh', 'book': 'whoosh', 'tg': 'whoosh', 'badge': 'pop', 'flare': 'ding', 'card': 'whoosh', 'table': 'whoosh', 'bars': 'whoosh', 'coin': 'whoosh',
       'moneybutton': 'whoosh', 'button': 'pop', 'punch': None}


def camera_track(evs, dur, fps=30):
    """3D-камера по кадрам: [наклон rx, поворот ry, наезд tz, сдвиг tx]. Её же «видит» Эмбер — и поворачивается за ней.
    ry > 0 — камера уходит влево от героя, ry < 0 — вправо. Событие "orbit": "dir": 1 (вправо) / -1 (влево)."""
    swoop = lambda dt, d=1.1: 0.0 if dt < 0 or dt > d else math.sin(math.pi * dt / d) ** 2
    hold = lambda t, a, b, f=0.45: min(1, max(0, (t - a + f) / f)) * min(1, max(0, (b - t) / f))
    beats = [e['t0'] for e in evs if e['type'] in ('flare', 'tg')]
    scenes = [e for e in evs if e['type'] in ('table', 'bars')]
    orbits = [e for e in evs if e['type'] == 'orbit']
    tg = next((e for e in evs if e['type'] == 'tg'), None)
    out = []
    for i in range(int(math.ceil(dur * fps)) + 1):
        t = i / fps
        ry = 4.5 * math.sin(t * 0.31) + 1.5 * math.sin(t * 0.83)
        rx = 2.2 * math.sin(t * 0.27 + 1); tz = 25 * math.sin(t * 0.21); tx = 0.0
        for j, b in enumerate(beats):                      # смена пункта — пролёт с разворотом (по очереди в разные стороны)
            k = swoop(t - b + 0.1); dr = -1 if j % 2 else 1
            ry += dr * 8 * k; rx -= 2.5 * k; tz += 120 * k; tx += dr * 25 * k
        for e in scenes:                                   # таблица/график — отъезд и наклон
            k = hold(t, e['t0'], e['t1']); rx += 5 * k; tz -= 90 * k
        for e in orbits:                                   # заданный облёт: камера уходит вправо/влево
            k = hold(t, e['t0'], e['t1'], 0.6); dr = e.get('dir', 1)
            ry -= dr * 14 * k; tx -= dr * 30 * k
        if tg:
            tz += 60 * hold(t, tg['t0'] + 0.4, tg['t1'] + 1, 1.2)
        intro = min(1, t / 1.4)                            # первый кадр (обложка) — ровный
        out.append([round(rx * intro, 3), round(ry * intro, 3), round(tz * intro, 2), round(tx * intro, 2)])
    return out


def turn_track(cam):
    """Эмбер поворачивается к камере с небольшой задержкой — как живой."""
    res, v = [], 0.0
    for rx, ry, tz, tx in cam:
        v += (max(-1.0, min(1.0, -ry / 9)) - v) * 0.18
        res.append(round(v, 3))
    return res


def word_time(words, at, n=1):
    norm = lambda w: w.lower().replace('ё', 'е').strip('.,!?…:;—-«»')
    hits = [t for w, t in words if norm(w) == norm(at)]
    if not hits:
        raise SystemExit(f'Слово «{at}» не найдено')
    return hits[min(n, len(hits)) - 1]


def main(folder, out):
    folder = folder.rstrip('/')
    words = json.load(open(f'{folder}/words.json')); plan = json.load(open(f'{folder}/plan.json'))
    dur = doodle.loudness(f'{folder}/voice.wav')[1] + plan.get('tail', 0.9)
    T = lambda at, n=1: word_time(words, at, n) if isinstance(at, str) else float(at)

    # 1) времена всех событий и вложенных элементов
    evs = []
    for e in plan['events']:
        e = dict(e); e['t0'] = T(e['at'], e.get('word_n', 1)) + e.get('delay', 0); e['t1'] = e['t0'] + e.get('dur', 2.2)
        for key in ('items', 'rows'):
            for it in e.get(key, []):
                it['t'] = T(it['at'], it.get('word_n', 1)) if 'at' in it else e['t0']
                if 'mark_at' in it:
                    it['markT'] = T(it['mark_at'], it.get('mark_n', 1))
        if 'copies_at' in e:
            e['copies'] = [T(a) for a in e['copies_at']]
        for k in ('sub_at', 'press_at', 'cross_at'):
            if k in e:
                e[{'sub_at': 'subT', 'press_at': 'pressT', 'cross_at': 'crossT'}[k]] = T(e[k])
        if e['type'] == 'kinetic':
            j = next(i for i, (w, t) in enumerate(words) if t >= e['t0'] - 0.01)
            wt = []
            for tok in e['text'].split():
                k2 = next((i for i in range(j, min(j + 6, len(words))) if words[i][0].lower().strip('.,!?') == tok.lower().strip('.,!?')), None)
                if k2 is not None:
                    wt.append(words[k2][1] - e['t0']); j = k2 + 1
                else:
                    wt.append((wt[-1] + 0.15) if wt else 0.0)
            e['wt'] = wt
        evs.append(e)

    # 2) подложка: персонаж, камера, жесты
    bg_events = []
    for e in evs:
        if e['type'] in BG_TYPES:
            bg_events.append({k: v for k, v in e.items() if k not in ('t0', 't1')})
        if e.get('side') or e['type'] in SIDE_MODE_TYPES:
            bg_events.append({'at': e['at'], 'word_n': e.get('word_n', 1), 'delay': e.get('delay', 0), 'dur': e.get('dur', 2.2),
                              'type': 'chart', 'chart': {'kind': 'none'}})
        if e.get('jump'):
            bg_events.append({'at': e['at'], 'word_n': e.get('word_n', 1), 'type': 'badge', 'text': '', 'x': -999, 'y': -999,
                              'dur': 0.5, 'jump': True})
    layers = plan.get('layers', True)                # 3D-камера: фон и Эмбер отдельными слоями
    cam = camera_track(evs, dur)
    bg_plan = {'captions': False, 'bg_only': True, 'layers': layers, 'tail': plan.get('tail', 0.9), 'events': bg_events,
               'turn': turn_track(cam) if plan.get('follow_camera', False) else None}   # поворот за камерой выключен (решение пользователя)
    bg = f'{folder}/bg.mp4'
    old = open(f'{folder}/plan_bg.json').read() if os.path.exists(f'{folder}/plan_bg.json') else None
    new = json.dumps(bg_plan, ensure_ascii=False, indent=1)
    if old != new or not os.path.exists(bg) or os.path.getmtime(f'{ROOT}/tools/doodle.py') > os.path.getmtime(bg):
        open(f'{folder}/plan_bg.json', 'w').write(new)
        doodle.main(f'{folder}/voice.wav', f'{folder}/words.json', f'{folder}/plan_bg.json', bg)
    else:
        print('Подложка не менялась — беру готовую')

    # 3) субтитры фразами: где стоят и когда спрятать (пока кинетический текст повторяет слова)
    punct = doodle.punctuation(f'{folder}/words.json', words)
    chunks = []
    wi = 0
    for c0, c1, text in doodle.captions(words, dur, punct):
        n = len(text.split()); ws = words[wi:wi + n]; wi += n
        mid = (c0 + min(c1, c0 + 1.0)) / 2
        active = [e for e in evs if e['t0'] <= mid < e['t1']]
        pos = 'top' if any(e['type'] == 'zoom' for e in active) else \
              'side' if any(e.get('side') or e['type'] in SIDE_MODE_TYPES for e in active) else 'mid'
        hide = any(e['type'] in ('kinetic', 'hook', 'tg') for e in active)
        chunks.append({'t0': c0, 't1': c1, 'pos': pos, 'hide': hide, 'words': ws})
    json.dump({'duration': dur, 'layers': layers, 'cam': cam, 'chunks': chunks, 'events': [e for e in evs if e['type'] not in BG_TYPES]},
              open(f'{REM}/src/reel.json', 'w'), ensure_ascii=False)
    if layers:
        shutil.copy(f'{folder}/bg_grid.mp4', f'{REM}/public/reel_grid.mp4')
        shutil.copy(f'{folder}/bg_char.webm', f'{REM}/public/reel_char.webm')
    else:
        shutil.copy(bg, f'{REM}/public/reel_bg.mp4')

    # 4) Remotion
    silent = f'{folder}/video_silent.mp4'
    subprocess.run(['npx', 'remotion', 'render', 'src/index.ts', 'Reel', os.path.abspath(silent),
                    f'--browser-executable={BROWSER}', '--log=error'], cwd=REM, check=True)

    # 5) звуки, музыка, микс
    cues = []
    for e in evs:
        kind = e.get('sfx', SFX.get(e['type']))
        if e['type'] == 'tiles':
            for it in e['items']:
                cues.append((it['t'], 'pop', 1.1))
                if 'markT' in it:
                    cues.append((it['markT'], 'tick' if it.get('mark') == 'cross' else 'pop', 1.3))
        elif e['type'] in ('table',):
            cues.append((e['t0'], 'whoosh', 1))
            cues += [(r['t'], 'pop', 1.1) for r in e['rows']]
        elif e['type'] == 'phone':
            cues.append((e['t0'], 'whoosh', 1)); cues += [(it['t'], 'pop', 1.2 if it.get('from') == 'ai' else 1.0) for it in e['items']]
        elif e['type'] == 'grid':
            cues += [(it['t'], 'pop', 1.05) for it in e['items']]
        elif e['type'] == 'bars':
            cues.append((e['t0'], 'whoosh', 1)); cues.append((e['t0'] + 0.3, 'rise', 1))
        elif e['type'] == 'fan':
            cues.append((e['t0'], 'pop', 1)); cues += [(c, 'pop', 1 + 0.08 * i) for i, c in enumerate(e['copies'])]
        elif e['type'] == 'moneybutton':
            cues.append((e['t0'], 'whoosh', 1)); cues.append((e['pressT'], 'tick', 0.8)); cues.append((e['crossT'], 'pop', 0.8))
        elif e['type'] == 'kinetic':
            cues += [(e['t0'] + w, 'pop', 1.25) for tok, w in zip(e['text'].split(), e['wt']) if tok.strip('.,!?') == e.get('pill')]
        elif kind:
            cues.append((e['t0'], kind, 1))
    sfx.render(cues, dur, f'{folder}/sfx.wav')
    if not os.path.exists(f'{folder}/music.wav'):          # лёгкая бодрая музыка: слышна, но голос не перекрывает
        music.main(f'{folder}/music.wav', dur + 1, target=plan.get('music_lufs', -21.0))
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', silent, '-i', f'{folder}/voice.wav', '-i', f'{folder}/music.wav', '-i', f'{folder}/sfx.wav',
                    '-filter_complex', '[1:a]apad,asplit[v][vs];[2:a]volume=1[m];[m][vs]sidechaincompress=threshold=0.08:ratio=2:attack=60:release=700[md];'
                    '[v][md][3:a]amix=inputs=3:duration=first:normalize=0[a]',
                    '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k', '-t', f'{dur:.3f}',
                    '-movflags', '+faststart', out], check=True)
    print('Готово:', out)


if __name__ == '__main__':
    main(*sys.argv[1:3])
