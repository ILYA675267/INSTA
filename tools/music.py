"""Тихая спокойная фоновая мелодия, сгенерированная с нуля (своя — без авторских прав).

python3 tools/music.py out.wav 32 [seed]

Мягкий «пэд» из аккордов (Cmaj7 → Am7 → Fmaj7 → G6) + редкие нежные ноты, как у электропиано, + эхо.
Громкость −30 LUFS: под голосом (−14) почти не слышно, но паузы не звучат пусто.
В ролик подключается в plan.json: "music": "work/<имя>/music.wav" (tools/doodle.py сам приглушает её под речью).
"""
import subprocess, sys, wave
import numpy as np

SR = 48000
CHORDS = [[48, 55, 59, 64], [45, 52, 55, 60], [41, 48, 52, 57], [43, 50, 52, 59]]   # MIDI-ноты
SCALE = [60, 62, 64, 67, 69, 72, 74, 76]                                            # пентатоника до мажор


def hz(m):
    return 440 * 2 ** ((m - 69) / 12)


def lowpass(x, cut):
    a = np.exp(-2 * np.pi * cut / SR)
    y = np.empty_like(x); acc = 0.0
    for i, v in enumerate(x):                       # однополюсный фильтр — убирает «звон»
        acc = (1 - a) * v + a * acc; y[i] = acc
    return y


def main(out, dur, seed=7, target=-30.0):
    dur, rng = float(dur), np.random.default_rng(int(seed))
    n = int(dur * SR); t = np.arange(n) / SR
    mix = np.zeros(n)
    bar = 3.4                                        # один аккорд ≈ 3,4 с — очень неторопливо
    for k in range(int(dur / bar) + 2):
        t0 = k * bar; i0 = int(t0 * SR)
        L = int((bar + 1.6) * SR); seg = np.arange(L) / SR
        env = np.minimum(1, seg / 1.2) * np.clip((bar + 1.6 - seg) / 1.6, 0, 1)      # медленный вход и выход
        tone = np.zeros(L)
        for m in CHORDS[k % 4]:
            for det in (-0.05, 0.05):               # две чуть расстроенные копии — «тёплый» пэд
                f = hz(m + det)
                tone += np.sin(2 * np.pi * f * seg + rng.uniform(0, 6.28)) + 0.18 * np.sin(4 * np.pi * f * seg)
        j = min(n, i0 + L) - i0
        if j > 0:
            mix[i0:i0 + j] += 0.05 * (tone * env)[:j]
        for b in range(8):                           # редкие ноты «электропиано» по восьмым
            if rng.random() < 0.45:
                m = rng.choice([x for x in SCALE if (x % 12) in [c % 12 for c in CHORDS[k % 4]]] or SCALE)
                s0 = int((t0 + b * bar / 8) * SR); Ln = int(2.2 * SR); sg = np.arange(Ln) / SR
                f = hz(m)
                note = (np.sin(2 * np.pi * f * sg) + 0.3 * np.sin(4 * np.pi * f * sg) * np.exp(-sg * 6)) \
                    * np.exp(-sg * 2.2) * np.minimum(1, sg / 0.01)
                j = min(n, s0 + Ln) - s0
                if j > 0:
                    mix[s0:s0 + j] += 0.09 * note[:j]
    mix = lowpass(mix, 2600)
    ir_t = np.arange(int(1.8 * SR)) / SR                                           # простое «эхо зала»
    ir = rng.normal(0, 1, len(ir_t)) * np.exp(-ir_t * 3.2); ir[0] = 0
    wet = np.fft.irfft(np.fft.rfft(mix, 2 * n + len(ir)) * np.fft.rfft(ir, 2 * n + len(ir)))[:n]
    mix = mix + 0.02 * wet
    fade = np.minimum(1, t / 1.5) * np.minimum(1, (dur - t) / 2.0)
    mix = mix * fade / (np.abs(mix).max() + 1e-9) * 0.8
    tmp = out + '.raw.wav'
    w = wave.open(tmp, 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((mix * 32767).astype(np.int16).tobytes()); w.close()
    # меряем громкость и ровно сдвигаем к цели (без «качания», как бывает у loudnorm на тихой музыке)
    log = subprocess.run(['ffmpeg', '-hide_banner', '-i', tmp, '-af', 'ebur128', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    lufs = float(log.rsplit('I:', 1)[1].split('LUFS')[0])
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', tmp, '-af', f'volume={target - lufs:.2f}dB',
                    '-ac', '1', '-ar', '48000', '-sample_fmt', 's16', out], check=True)
    subprocess.run(['rm', tmp])
    print('Готово:', out)


if __name__ == '__main__':
    main(*sys.argv[1:4])
