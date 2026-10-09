"""Тихие звуковые эффекты на появление элементов (синтезируются с нуля — свои, без авторских прав).

pop    — «пузырёк»: кружки-номера, иконки, галочки в таблице
whoosh — мягкий «вжух»: логотипы, карточки, графики, смена сцены
tick   — короткий щелчок: точки на графике, слова кинетического текста с плашкой
ding   — «дзынь» с хвостом: оранжевая вспышка на смене пункта
rise   — растущий тон: пока поднимается столбик графика
Используется из tools/doodle.py (в plan.json: "sfx": true, "sfx_volume": 1.0;
у отдельного события — "sfx": "pop" | ... | false, чтобы заменить или выключить звук).
"""
import wave
import numpy as np

SR = 48000
_rng = np.random.default_rng(11)


def _env(n, attack, decay):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(attack, 1e-4)) * np.exp(-t / decay)


def _smooth(x, k):
    """Простое сглаживание (грубый фильтр низких частот) окном k отсчётов."""
    return np.convolve(x, np.ones(k) / k, mode='same')


def pop(pitch=1.0):
    n = int(0.16 * SR); t = np.arange(n) / SR
    f = (300 + 900 * np.exp(-t * 38)) * pitch                    # высота быстро «падает» — как пузырь
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = np.sin(ph) * _env(n, 0.002, 0.045)
    s += 0.25 * _smooth(_rng.normal(0, 1, n), 6) * _env(n, 0.0005, 0.006)   # лёгкий «чпок» в начале
    return 0.55 * s


def whoosh(length=0.42):
    n = int(length * SR); t = np.arange(n) / SR
    noise = _rng.normal(0, 1, n)
    lo, hi = _smooth(noise, 24), _smooth(noise, 6)
    mixk = np.clip(t / length, 0, 1)                              # от глухого к яркому — «пролёт»
    s = (lo * (1 - mixk) + (hi - _smooth(hi, 40)) * mixk * 0.8)
    env = np.sin(np.pi * np.clip(t / length, 0, 1)) ** 1.6
    return 0.5 * s * env / (np.abs(s).max() + 1e-9)


def tick(pitch=1.0):
    n = int(0.05 * SR); t = np.arange(n) / SR
    s = np.sin(2 * np.pi * 2100 * pitch * t) * _env(n, 0.0005, 0.008) + 0.4 * np.sin(2 * np.pi * 3300 * pitch * t) * _env(n, 0.0005, 0.004)
    return 0.35 * s


def ding(pitch=1.0):
    n = int(1.1 * SR); t = np.arange(n) / SR
    f0 = 1318 * pitch                                              # ми второй октавы — светлый «колокольчик»
    s = sum(a * np.sin(2 * np.pi * f0 * r * t) * np.exp(-t * d) for r, a, d in
            [(1, 1, 4.0), (2.76, 0.35, 7), (5.4, 0.15, 12), (0.5, 0.2, 5)])
    return 0.28 * s * np.minimum(1, t / 0.003)


def rise(length=0.8):
    n = int(length * SR); t = np.arange(n) / SR
    f = 330 * 2 ** (t / length * 1.0)                              # ровно на октаву вверх
    ph = 2 * np.pi * np.cumsum(f) / SR
    s = (np.sin(ph) + 0.3 * np.sin(2 * ph)) * np.sin(np.pi * np.clip(t / length, 0, 1)) ** 1.2
    return 0.16 * s


MASTER = 0.33          # общая громкость эффектов: заметно тише голоса, «на фоне»
SOUNDS = {'pop': pop, 'whoosh': whoosh, 'tick': tick, 'ding': ding, 'rise': rise}
DEFAULT = {'badge': 'pop', 'icon': 'pop', 'logo': 'whoosh', 'card': 'whoosh', 'chart': 'whoosh',
           'burst': 'ding', 'text': 'pop', 'kinetic': 'tick', 'zoom': None}


def cues(evs):
    """События ролика → список (время, звук, параметр)."""
    out = []
    for e in evs:
        kind = e.get('sfx', DEFAULT.get(e['type']))
        if not kind:
            continue
        t0 = e['t0']
        if e['type'] == 'kinetic':                 # щелчок на слове в плашке
            toks = e['text'].split()
            for tok, wt in zip(toks, e.get('wt', [])):
                if e.get('pill') and tok.strip('.,!?') == e['pill']:
                    out.append((t0 + wt, 'pop', 1.25))
            continue
        out.append((t0, kind, 1.0 if e['type'] != 'icon' else 1.15))
        c = e.get('chart')
        if e['type'] == 'chart' and c:
            items = c.get('items', [])
            if c['kind'] in ('bars', 'iso'):
                for i in range(len(items)):
                    out.append((t0 + 0.25 + i * 0.3, 'rise', 0.8))
            elif c['kind'] == 'line':
                n = max(1, len(items) - 1)
                for i in range(len(items)):
                    out.append((t0 + 0.3 + 1.6 * i / n, 'tick', 1 + 0.08 * i))
            elif c['kind'] == 'table':
                for i, it in enumerate(items):
                    out.append((t0 + it.get('dt', 0.3 + i * 0.5) + 0.08, 'pop', 1.1 + 0.05 * i))
    return out


def render(cue_list, dur, path, volume=1.0):
    mix = np.zeros(int((dur + 1.5) * SR))
    for t, kind, p in cue_list:
        s = SOUNDS[kind](p) if kind in ('pop', 'tick', 'ding') else SOUNDS[kind]()
        i = int(max(0, t) * SR); j = min(len(mix), i + len(s))
        if j > i:
            mix[i:j] += s[:j - i]
    mix = np.clip(mix * volume * MASTER, -1, 1)[:int(dur * SR)]
    w = wave.open(path, 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((mix * 32767).astype(np.int16).tobytes()); w.close()
