"""Привязывает слова сценария к таймингам распознанной речи (чтобы в субтитрах был точный текст сценария).

python3 tools/align.py script.txt work/X/asr_words.json work/X/words.json
"""
import difflib, json, re, sys


def norm(w):
    return ''.join(ch for ch in w.lower().replace('ё', 'е') if ch.isalnum())


def main(script, asr_path, out):
    text = open(script).read()
    sw = [w for w in re.findall(r"[\w\-]+[.,!?…:;]*", text) if norm(w)]
    asr = json.load(open(asr_path))
    sm = difflib.SequenceMatcher(a=[norm(w) for w in sw], b=[norm(w) for w, _ in asr], autojunk=False)
    times = [None] * len(sw)
    for op, a0, a1, b0, b1 in sm.get_opcodes():
        if op == 'equal' or (op == 'replace' and a1 - a0 == b1 - b0):  # совпало или распознано с ошибкой 1:1
            for k in range(a1 - a0):
                times[a0 + k] = asr[b0 + k][1]
        elif op == 'replace':  # разное число слов — растягиваем по участку
            for k in range(a1 - a0):
                times[a0 + k] = asr[b0 + min(b1 - b0 - 1, k * (b1 - b0) // (a1 - a0))][1]
    # слова без пары — равномерно между соседями
    known = [i for i, t in enumerate(times) if t is not None]
    for i in range(len(sw)):
        if times[i] is None:
            prev = max([k for k in known if k < i], default=None)
            nxt = min([k for k in known if k > i], default=None)
            t0 = times[prev] if prev is not None else 0.0
            t1 = times[nxt] if nxt is not None else t0 + 0.35 * (i - (prev or 0) + 1)
            span = (nxt if nxt is not None else i + 1) - (prev if prev is not None else -1)
            times[i] = t0 + (t1 - t0) * (i - (prev if prev is not None else -1)) / span
    words = [[re.sub(r'[.,!?…:;]+$', '', w), round(t, 2)] for w, t in zip(sw, times)]
    json.dump(words, open(out, 'w'), ensure_ascii=False)
    print(' '.join(f'{w}@{t:.2f}' for w, t in words))


if __name__ == '__main__':
    main(*sys.argv[1:4])
