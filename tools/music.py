"""Тихая спокойная фоновая мелодия, сгенерированная с нуля (своя — без авторских прав).

python3 tools/music.py out.wav 32 [seed] [energy|calm]

energy (по умолчанию) — тихо, но бодро: 104 удара в минуту, мягкий бит, бас, переливы нот, «дышащий» пэд.
calm — мягкий «пэд» из аккордов (Cmaj7 → Am7 → Fmaj7 → G6) + редкие нежные ноты, как у электропиано, + эхо.
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


def _place(mix, snd, t, gain=1.0):
    i = int(t * SR); j = min(len(mix), i + len(snd))
    if j > i:
        mix[i:j] += gain * snd[:j - i]


def energy(dur, rng):
    """Бодрый, но тихий фон: Am → F → C → G, бит, бас, арпеджио восьмыми, пэд «качается» под бочку."""
    n = int(dur * SR); t = np.arange(n) / SR
    beat = 60 / 104; bar = 4 * beat
    chords = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]
    pad, keys, bass, drums = (np.zeros(n) for _ in range(4))
    # готовые «сэмплы»
    kt = np.arange(int(0.3 * SR)) / SR
    kick = np.sin(2 * np.pi * np.cumsum(45 + 80 * np.exp(-kt * 30)) / SR) * np.exp(-kt * 11)
    noise = rng.normal(0, 1, int(0.2 * SR))
    hat = (noise - lowpass(noise, 6000))[:int(0.04 * SR)] * np.exp(-np.arange(int(0.04 * SR)) / SR * 90)
    snare = lowpass(noise - lowpass(noise, 900), 5000) * np.exp(-np.arange(len(noise)) / SR * 22)
    nbars = int(dur / bar) + 1
    for k in range(nbars):
        t0 = k * bar; ch = chords[k % 4]
        L = int((bar + 0.8) * SR); seg = np.arange(L) / SR
        env = np.minimum(1, seg / 0.25) * np.clip((bar + 0.8 - seg) / 0.8, 0, 1)
        tone = sum(np.sin(2 * np.pi * hz(m + d) * seg + rng.uniform(0, 6.28)) for m in ch for d in (-0.04, 0.04))
        _place(pad, tone * env, t0, 0.035)
        root = hz(ch[0] - 24)
        for bt, ln in ((0, 1.4), (2.5, 1.2)):                                     # бас с «оттяжкой»
            bs = np.arange(int(ln * beat * SR)) / SR
            b = np.tanh(1.6 * np.sin(2 * np.pi * root * bs)) * np.minimum(1, bs / 0.01) * np.exp(-bs * 2.5)
            _place(bass, b, t0 + bt * beat, 0.16)
        arp = [0, 1, 2, 1, 2, 0, 2, 1]
        for e8 in range(8):                                                       # переливы восьмыми
            m = ch[arp[e8]] + 12; ns = np.arange(int(0.6 * SR)) / SR; f = hz(m)
            note = (np.sin(2 * np.pi * f * ns) + 0.35 * np.sin(4 * np.pi * f * ns) * np.exp(-ns * 9)) \
                * np.exp(-ns * 6) * np.minimum(1, ns / 0.004)
            _place(keys, note, t0 + e8 * beat / 2, (0.07 if e8 % 2 == 0 else 0.05) * rng.uniform(0.85, 1.1))
        if k == 0:
            continue                                                              # первый такт — без бита
        for b4 in range(4):
            _place(drums, kick, t0 + b4 * beat, 0.5)
            _place(drums, hat, t0 + (b4 + 0.5) * beat, 0.05)
            if b4 in (1, 3):
                _place(drums, snare, t0 + b4 * beat, 0.07)
    # пэд «приседает» на каждую долю — ощущение движения
    since = (t % beat); pump = 1 - 0.45 * np.exp(-since * 9)
    mix = pad * pump + keys + bass + drums
    return lowpass(mix, 7000)


def main(out, dur, seed=7, style='energy', target=None):
    dur, rng = float(dur), np.random.default_rng(int(seed))
    if style == 'energy':
        target = -28.0 if target is None else target
        n = int(dur * SR); t = np.arange(n) / SR
        mix = energy(dur, rng)
        return finish(out, mix, t, dur, rng, target)
    target = -30.0 if target is None else target
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
    return finish(out, mix, t, dur, rng, target, reverb=False)


def finish(out, mix, t, dur, rng, target, reverb=True):
    n = len(mix)
    if reverb:
        ir_t = np.arange(int(1.2 * SR)) / SR
        ir = rng.normal(0, 1, len(ir_t)) * np.exp(-ir_t * 4.5); ir[0] = 0
        wet = np.fft.irfft(np.fft.rfft(mix, 2 * n + len(ir)) * np.fft.rfft(ir, 2 * n + len(ir)))[:n]
        mix = mix + 0.012 * wet
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
    main(*sys.argv[1:5])
