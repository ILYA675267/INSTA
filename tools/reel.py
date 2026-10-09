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
import json, os, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doodle, music, sfx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REM = os.path.join(ROOT, 'remotion')
BROWSER = '/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell'
BG_TYPES = ('zoom', 'punch', 'cam', 'pose')
SIDE_MODE_TYPES = ('table', 'bars')
SFX = {'badge': 'pop', 'flare': 'ding', 'card': 'whoosh', 'table': 'whoosh', 'bars': 'whoosh', 'coin': 'whoosh',
       'moneybutton': 'whoosh', 'button': 'pop', 'punch': None}


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
    bg_plan = {'captions': False, 'bg_only': True, 'tail': plan.get('tail', 0.9), 'events': bg_events}
    json.dump(bg_plan, open(f'{folder}/plan_bg.json', 'w'), ensure_ascii=False, indent=1)
    bg = f'{folder}/bg.mp4'
    doodle.main(f'{folder}/voice.wav', f'{folder}/words.json', f'{folder}/plan_bg.json', bg)

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
        hide = any(e['type'] == 'kinetic' for e in active)
        chunks.append({'t0': c0, 't1': c1, 'pos': pos, 'hide': hide, 'words': ws})
    json.dump({'duration': dur, 'chunks': chunks, 'events': [e for e in evs if e['type'] not in BG_TYPES]},
              open(f'{REM}/src/reel.json', 'w'), ensure_ascii=False)
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
    if not os.path.exists(f'{folder}/music.wav'):
        music.main(f'{folder}/music.wav', dur + 1)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', silent, '-i', f'{folder}/voice.wav', '-i', f'{folder}/music.wav', '-i', f'{folder}/sfx.wav',
                    '-filter_complex', '[1:a]apad,asplit[v][vs];[2:a]volume=1[m];[m][vs]sidechaincompress=threshold=0.04:ratio=3:attack=40:release=600[md];'
                    '[v][md][3:a]amix=inputs=3:duration=first:normalize=0[a]',
                    '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k', '-t', f'{dur:.3f}',
                    '-movflags', '+faststart', out], check=True)
    print('Готово:', out)


if __name__ == '__main__':
    main(*sys.argv[1:3])
