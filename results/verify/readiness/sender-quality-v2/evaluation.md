# Ретроспектива timing UDP sender v2

Все исходные every-slot решения были failed. Столбец v2 относится только к генератору, не ко всему сбору. Raw inventory до/после совпал; доступные captured.json проверены. Null seal не заменяется положительной оценкой.

| Collection | Late % | Lag max ms | Gap max ms | Peak/10ms | Groups | v2 | Причина |
|---|---:|---:|---:|---:|---:|---|---|
| calibration.ZQRTHB2H/baseline-after | 0.3000 | 28.639335 | 37.517167 | 4 | 25 | passed | все три ограничения соблюдены |
| calibration.ZQRTHB2H/baseline-before | 0.7700 | 58.287995 | 61.686333 | 7 | 56 | failed | maximum lag 58.288 ms > 50 ms; burst 7 packets/10 ms > 4 |
| calibration.ZQRTHB2H/r20p0-after | 0.3400 | 28.152593 | 36.763333 | 4 | 28 | passed | все три ограничения соблюдены |
| calibration.ZQRTHB2H/r20p0-before | 0.2000 | 29.462531 | 38.227208 | 4 | 17 | passed | все три ограничения соблюдены |
| calibration.ZQRTHB2H/r20p0-latency | 0.2800 | 59.020711 | 68.172333 | 7 | 22 | failed | maximum lag 59.0207 ms > 50 ms; burst 7 packets/10 ms > 4 |
| calibration.ZQRTHB2H/r20p1-after | 0.3200 | 32.603612 | 40.083375 | 5 | 27 | failed | burst 5 packets/10 ms > 4 |
| calibration.ZQRTHB2H/r20p1-before | 0.8300 | 44.887614 | 54.383875 | 6 | 58 | failed | burst 6 packets/10 ms > 4 |
| calibration.ZQRTHB2H/r20p1-latency | 1.0400 | 135.269694 | 145.154292 | 14 | 55 | failed | late slots 1.04% > 1%; maximum lag 135.27 ms > 50 ms; burst 14 packets/10 ms > 4 |
| calibration.ZQRTHB2H/r80p0-after | 0.3400 | 28.994638 | 38.019292 | 4 | 28 | passed | все три ограничения соблюдены |
| calibration.ZQRTHB2H/r80p0-before | 0.3000 | 68.604912 | 76.196875 | 7 | 24 | failed | maximum lag 68.6049 ms > 50 ms; burst 7 packets/10 ms > 4 |
| calibration.ZQRTHB2H/r80p0-latency | 1.5000 | 121.302133 | 129.417958 | 13 | 89 | failed | late slots 1.5% > 1%; maximum lag 121.302 ms > 50 ms; burst 13 packets/10 ms > 4 |
| calibration.ZQRTHB2H/r80p1-after | 0.2400 | 30.802573 | 39.610542 | 4 | 20 | passed | все три ограничения соблюдены |
| calibration.ZQRTHB2H/r80p1-before | 0.5100 | 52.282357 | 56.602542 | 7 | 40 | failed | maximum lag 52.2824 ms > 50 ms; burst 7 packets/10 ms > 4 |
| calibration.ZQRTHB2H/r80p1-latency | 0.5900 | 62.645235 | 72.253249 | 8 | 45 | failed | maximum lag 62.6452 ms > 50 ms; burst 8 packets/10 ms > 4 |
| sender-diagnostic.9XCZ6Zqd/baseline-before | 0.6000 | 23.460460 | 33.242792 | 4 | 8 | passed | все три ограничения соблюдены |
| sender-diagnostic.9XCZ6Zqd/baseline-repeat | 1.0000 | 26.247964 | 33.671834 | 4 | 14 | passed | все три ограничения соблюдены |
| sender-diagnostic.9XCZ6Zqd/r80p0-response | 1.8667 | 32.535084 | 40.619625 | 5 | 22 | failed | late slots 1.86667% > 1%; burst 5 packets/10 ms > 4 |
| sender-diagnostic.Lno9XZ1D/baseline-control | 0.6000 | 28.645420 | 38.101958 | 4 | 7 | passed | все три ограничения соблюдены |
| sender-diagnostic.T6NngDpB/baseline-control | 0.2667 | 40.942417 | 50.600709 | 6 | 1 | failed | burst 6 packets/10 ms > 4 |
| sender-diagnostic.lEn9VhiY/baseline-control | 2.1333 | 138.511919 | 146.192251 | 15 | 9 | failed | late slots 2.13333% > 1%; maximum lag 138.512 ms > 50 ms; burst 15 packets/10 ms > 4 |
| sender-diagnostic.yB7Jzpyh/baseline-control | 0.7333 | 39.963338 | 37.784917 | 5 | 7 | failed | burst 5 packets/10 ms > 4 |
| sender-scheduling.LGEmSpOH/baseline-scheduling | 0.7333 | 29.820501 | 38.789083 | 4 | 9 | passed | все три ограничения соблюдены |

Полные распределения, быстрые группы и сценарии чувствительности находятся в evaluation.json. Воспроизведение: `python3 -B results/verify/readiness/sender-quality-v2/recompute.py`. Обоснование: [решение](../../../../docs/readiness/sender-quality-v2.md).
