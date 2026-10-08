"""Озвучка через Zvukogram (платно, по токенам). Голос по умолчанию — «Борислав».

python3 tools/voice_zvuk.py script.txt out.wav [голос] [скорость]
python3 tools/voice_zvuk.py --voices          — русские голоса и цены

Нужны переменные среды ZVUKOGRAM_TOKEN и ZVUKOGRAM_EMAIL (настройки среды) и домен zvukogram.com в разрешённых.
"""
import json, os, subprocess, sys, tempfile, time, urllib.error, urllib.parse, urllib.request

API = 'https://zvukogram.com/index.php?r=api/'


def call(method, **params):
    data = urllib.parse.urlencode(params).encode() if params else None
    with urllib.request.urlopen(urllib.request.Request(API + method, data=data), timeout=120) as r:
        return json.load(r)


def main(script, out, voice='Борислав', speed='1.0'):
    token, email = os.environ.get('ZVUKOGRAM_TOKEN'), os.environ.get('ZVUKOGRAM_EMAIL')
    if not token or not email:
        raise SystemExit('Нет ZVUKOGRAM_TOKEN / ZVUKOGRAM_EMAIL в переменных среды')
    text = open(script).read().strip() if os.path.exists(script) else script
    for attempt in range(3):                          # сервис иногда отвечает 504 — пробуем ещё раз
        try:
            r = call('text', token=token, email=email, voice=voice, text=text, format='wav', speed=speed)
            break
        except urllib.error.HTTPError as e:
            if e.code < 500 or attempt == 2:
                raise
            time.sleep(5)
    while r.get('status') == 0:                       # длинный текст озвучивается не сразу
        time.sleep(2)
        r = call('result', token=token, email=email, id=r['id'])
    if r.get('status') != 1:
        raise SystemExit(f"Zvukogram: {r.get('error') or r}")
    tmp = tempfile.mktemp(suffix='.wav')
    urllib.request.urlretrieve(r['file'], tmp)
    # 48 кГц моно, громкость −14 LUFS, короткая тишина в начале и в конце
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', tmp, '-af',
                    'adelay=200,apad=pad_dur=0.2,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000',
                    '-ac', '1', '-ar', '48000', '-sample_fmt', 's16', out], check=True)
    os.remove(tmp)
    print(f"Готово: {out} (осталось на балансе: {r.get('balans')})")


if __name__ == '__main__':
    if sys.argv[1] == '--voices':
        for v in call('voices')['Русский']:
            print(v['voice'], v['sex'], v['type'], 'цена', v['price'])
    else:
        main(*sys.argv[1:5])
