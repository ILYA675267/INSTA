"""Бесплатная русская озвучка Silero v5 (офлайн, лицензия MIT — можно для монетизации).

python3 tools/voice.py script.txt out.wav [голос] [скорость] [высота]
python3 tools/voice.py --list                      — показать русские голоса

скорость: 1.0 — норма; высота: полутонов вверх (+1.5 — голос моложе), 0 — как есть.
Модель (92 МБ) скачивается с Hugging Face в models/ при первом запуске.
"""
import os, re, subprocess, sys, tempfile, urllib.request, wave
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(ROOT, 'models', 'v5_cis_base_nostress.pt')
URL = 'https://huggingface.co/adeshkin/silero-models-v5-cis-base-nostress/resolve/main/v5_cis_base_nostress.pt'
SR = 48000


def model():
    import torch
    if not os.path.exists(MODEL):
        os.makedirs(os.path.dirname(MODEL), exist_ok=True)
        urllib.request.urlretrieve(URL, MODEL)
    torch.set_num_threads(os.cpu_count() or 4)
    return torch.package.PackageImporter(MODEL).load_pickle('tts_models', 'model')


def speak(m, text, speaker):
    """Синтез по предложениям (модель не любит длинные куски) с паузами между ними."""
    parts = [p.strip() for p in re.split(r'(?<=[.!?…])\s+', text.strip()) if p.strip()]
    out = []
    for p in parts:
        a = m.apply_tts(text=p, speaker=speaker, sample_rate=SR).numpy()
        out += [a, np.zeros(int(SR * 0.18), np.float32)]
    return np.concatenate(out)


def save(a, path):
    pad = np.zeros(int(SR * 0.2), np.float32)
    pcm = (np.clip(np.concatenate([pad, a, pad]), -1, 1) * 32767).astype(np.int16)
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())


def post(src, dst, speed=1.0, pitch=0.0):
    """Скорость, высота и «мягкость»: убираем резкие верха, чуть теплее низ, громкость −14 LUFS."""
    k = 2 ** (pitch / 12)
    f = [f'asetrate={int(SR * k)}', f'aresample={SR}', f'atempo={speed / k:.4f}',
         'highpass=f=70', 'equalizer=f=4500:t=q:w=1.2:g=-3', 'equalizer=f=200:t=q:w=1:g=1.5',
         'lowpass=f=12000', 'loudnorm=I=-14:TP=-1.5:LRA=11', f'aresample={SR}']
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-af', ','.join(f), '-ac', '1', dst], check=True)


def main(script, out, speaker='ru_eduard', speed=1.0, pitch=0.0):
    m = model()
    text = open(script).read() if os.path.exists(script) else script
    tmp = tempfile.mktemp(suffix='.wav')
    save(speak(m, text, speaker), tmp)
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    post(tmp, out, float(speed), float(pitch))
    os.remove(tmp)
    print('Готово:', out)


if __name__ == '__main__':
    if sys.argv[1] == '--list':
        print([s for s in model().speakers if s.startswith('ru_') or '_' not in s])
    else:
        main(*sys.argv[1:6])
