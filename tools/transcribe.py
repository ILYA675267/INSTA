"""Распознаёт русскую речь в видео и сохраняет тайминги слов.

python3 tools/transcribe.py input/video.mp4 work/video/words.json

Модель (sherpa-onnx zipformer-ru) скачивается с GitHub при первом запуске в models/.
"""
import json, os, subprocess, sys, tarfile, urllib.request, wave
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = 'sherpa-onnx-zipformer-ru-2024-09-18'
URL = f'https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/{MODEL}.tar.bz2'


def ensure_model():
    d = os.path.join(ROOT, 'models', MODEL)
    if not os.path.isdir(d):
        os.makedirs(os.path.dirname(d), exist_ok=True)
        tmp = d + '.tar.bz2'
        print('Скачиваю модель распознавания речи...')
        urllib.request.urlretrieve(URL, tmp)
        with tarfile.open(tmp) as t:
            t.extractall(os.path.dirname(d))
        os.remove(tmp)
    return d


def main(src, out):
    import sherpa_onnx as so
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    wav = out + '.wav'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-ac', '1', '-ar', '16000', wav], check=True)
    w = wave.open(wav)
    audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    os.remove(wav)
    m = ensure_model() + '/'
    rec = so.OfflineRecognizer.from_transducer(
        encoder=m + 'encoder.int8.onnx', decoder=m + 'decoder.onnx', joiner=m + 'joiner.int8.onnx',
        tokens=m + 'tokens.txt', num_threads=4)
    words = []
    # длинные записи режем на куски ~15 с по самым тихим местам (модель не любит длинный звук)
    sr, start = 16000, 0
    while start < len(audio):
        end = len(audio) if len(audio) - start <= 18 * sr else start + 12 * sr
        if end < len(audio):
            win = audio[end:end + 4 * sr]
            e = np.convolve(np.abs(win), np.ones(800) / 800, mode='same')
            end += int(np.argmin(e))
        s = rec.create_stream()
        s.accept_waveform(sr, audio[start:end])
        rec.decode_stream(s)
        first = True
        for tok, ts in zip(s.result.tokens, s.result.timestamps):
            if tok.startswith(' ') or first:
                words.append([tok.strip(), round(ts + start / sr, 2)]); first = False
            else:
                words[-1][0] += tok
        start = end
    json.dump(words, open(out, 'w'), ensure_ascii=False)
    print(' '.join(f'{w}@{t:.2f}' for w, t in words))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
