# Четыре полные калибровки: независимая сверка

14 ноября 2026. Внутренний method_review: только чтение существующих документов, JSON и raw. Новая сеть, диагностики, изменения production и допусков не выполнялись. Пользователь планирует начать замеры 15 ноября; начало подготовительных измерений и допуск к main — разные цели.

## Исторические результаты

Каждый сбор содержит 14 echo × 10000 плановых ID и 4 saturation, shell exit0, 146 sealed files. Сейчас повторно проверены SHA256 всех 584 ссылок captured.json. Каждый сбор занял около 29 минут; четыре вместе — примерно 1 ч 58 мин, без разработки и дополнительных диагностик.

| Сбор и source | Sender по тогдашним правилам | Process и итог | Что численно прошло |
|---|---|---|---|
| lShojabe, 494e1a99, 13 ноября | 12/14 passed. r20p0-after maxlag129.224986ms и r20p1-after53.692504ms при max50; late/burst проходят | Formal process2/6 suspect: baseline-before, r20p0-latency. Итог failed старого sender-v2; дополнительно process inconclusive | Целостность, ID/pcap/counters, 16 formal directional loss, 4 capacity9.99949–10.00128Mbit/s; browser fraction.00838004 |
| gIdWLx7o, d4cf0f82, после poll0, 14 ноября | 14/14 passed, maxlag35.468481ms | Formal process3/6 suspect: r20p0/r80p0/r80p1-latency. Итог inconclusive старого process контракта. Был реальный длительный RTT режим около +3ms | Целостность, 16 formal loss, 4 capacity9.99932–10.00112; применимое BW сопоставление <10% |
| ew2u0ceD, d665590, после poll0+pin, 14 ноября | 13/14 passed. r20p1-before maxlag69.794312ms>50; late.17%/burst4 проходят | Formal process1/6 suspect: r80p1-latency. Итог failed старого sender-v2 плюс process inconclusive из-за малого сдвига около −.134ms | Целостность, 16 formal loss, 4 capacity9.99932–10.00128; BW<10%; прежние многомиллисекундные forward режимы исчезли |
| sFWOAzbo, acce594, новая практическая методика, 14 ноября | 13/14 passed. r80p1-after242late/10000=2.42%>1%; lagproxy maxima27/28/26/27/26 при budget12, все4005 окна fail | Failed уже по новому практическому критерию. Это существенная наблюдаемая деформация нагрузки, не отказ старого stationarity теста | Целостность, все120 median окон / 8 envelopes, 16 formal empirical loss, 4 capacity9.99916–10.00080; новый BW fraction.008380319<.1 |

Loss относится к 16 проверкам 8 выделенных before/after коллекций, process — к 6 latency/baseline коллекциям. Дополнительные диагностические flags/drops других коллекций сохранены, но не подменяют заданные families. Полный stationary bootstrap первых трёх сборов не выполнялся: установленные ранее failed/inconclusive уже останавливали приёмку.

## Реальный +3ms режим и малый .134ms ACF сдвиг

Новая observed-profile-check-v1 снимает требование обосновывать стационарный CI самой среды. ACF, drift и maxlag остаются видимыми; диапазоны median окон проверяют фактическое воспроизведение target±2ms без обещания будущего покрытия.

В gIdWLx7o r80p1-latency поздние оконные medians83.882–84.034792ms против ранних80.544–80.700ms; forward span около43.03–43.18ms против40.30ms. Это продолжительный физически наблюдаемый режим, а не одна чувствительная ACF метка.

В ew2u0ceD median80.68848→80.55579ms, forward span40.298→40.299ms: малый остаточный сдвиг около −.133ms, ACF.05668/.03800. Старый контракт отвергал его как препятствие stationary inference; новый сам по себе не отвергает такую малую наблюдаемую амплитуду.

Выполненный ранее exploratory пересчёт старых raw даёт:

| Исторический raw | Новый sender proxy, ретроспективно | Новые 8 median envelopes, ретроспективно |
|---|---|---|
| lShojabe | 14/14 passed | 8/8 passed |
| gIdWLx7o | 14/14 passed | 6/8 passed; оба r80p1 контраста fail: верх83.430292/83.426125ms>82 |
| ew2u0ceD | 14/14 passed | 8/8 passed |

Это не переприсвоение passed старым reports и не нетронутая валидация новой политики. Эти данные участвовали в её разработке и собраны на прежнем source. Единственный новый prospective полный сбор новой методики — sFWOAzbo — failed. Выбирать вместо него исторический удачный raw либо повторять неизменённо до успеха нельзя.

## Что можно и нельзя заключить из чисел

Все 56 echo коллекций суммарно: 560000 плановых слотов, 554940 вернувшихся RTT, 5060 missing. В каждом полном сборе соответственно 140000/138735/1265. Потери намеренно инжектируются в loss1: missing не равны сбоям стенда. Они сохраняются с полными знаменателями и unknown RTT. Совпадение drop counts связано с заданными повторно seeds, а не доказывает независимые реализации потерь.

14 подсерий — разные профили, порядок и назначения, а не 14 независимых повторов одного условия. Доли12/14 или13/14 описывают набор проверок, не вероятность сбоя. Четыре полных сбора относятся к последовательно изменённым source/методикам; это не 4 exchangeable replicates. «Ни один из четырёх не принят» описывает admission историю, но не означает оценённую 100% вероятность будущего сбоя;13/14 не означает7.14% брака main.

Последний432ms lag — накопленное отставание, не единичная432ms пауза. Максимальный actual intersend gap129.313667ms; группа5481–5605 содержит125late слотов и несколько задержек с последующим catchup. PCAP подтверждает реальную деформацию offered traffic. Конкретная причина scheduler/syscall/host CPU пока не установлена. Source bug либо роль чужого контейнера из этого не следуют.

## Препятствия main и календарь

Текущий calibration failed блокирует generator и зависимые шаги существующего протокола. Настоящие сравнительные Q/S/U main ещё не измерены; UDP proxy не заменяет браузер. Сейчас актуальны 6 ранних gates build/tls/path/timer/raw/analysis; calibration failed, generator/AА/monitoring not_run. Официальный pilot/power, выбор n, freeze/reproduction/final verification/main не выполнены. Согласованное допущение несовершенства среды уже реализовано; последний отказ относится к оставленному практическому критерию, а не к снятому ACF требованию.

Порядок verification.md: принятая калибровка → generator20/100Hz всех включённых WS/WT-S/WT-D → A/A → monitoring → официальный pilot≥5блоков/профиль → power10000симуляций для n20/30/40/60 → обоснованный n/допуски → freeze/final verify/воспроизведение → main. Failed/inconclusive сохраняется и останавливает зависимые переходы. Без данных нельзя обещать календарь прохождения.

Историческая оценка final-verification.md «не менее15ч07мин» касается двух режимов, A/A+monitoring+pilot без overhead. Сейчас include_wt_d=true: каждый из A/A и monitoring требует20пар×4профиля×3режима×2runs=480runs; минимальный pilot5×4×3=60runs. По нижней границе admission80s/run это10ч40мин+10ч40мин+1ч20мин=22ч40мин. Здесь ещё нет generator, setup/cleanup, новых quiet окон, offline/power/freeze/воспроизведения и разбора отказов. Это оптимистичная нижняя граница, не готовая ETA. Начать подготовительные замеры15ноября можно планировать; обещать начало научно допущенного main15ноября по текущим входам нельзя.

Main имеет отдельный лимит15h. Для3режимов нижние границы при n20/30/40/60:5ч20мин/8ч/10ч40мин/16ч без overhead. n60 уже не помещается; остальные n нельзя выбирать только по времени без pilot/power. Новые quiet окна и setup увеличат runtime; его нужно оценить применимыми данными до допуска. Leaf действует до26ноября19:22:37МСК; перед каждым сбором проверяется резерв всей серии, дата истечения сама не даёт допуска.

## Первичные основания

Пути ниже относительно results/verify/readiness/stage4/:

- release-v4/calibration-lShojabe-raw-review.json;
- calibration-poll0-v1/review/primary-review-v3.json;
- solution-research-v1/full-calibration/review/primary-review.json;
- practical-v1/full-calibration/review/method-results.json, calibration-sFWOAzbo-report.json, verify-failed-sFWOAzbo.json, STOP-sFWOAzbo.json;
- practical-v1/independent-results/derived.json — явно exploratory ретроспектива.

Дополнительно сверены raw/commit/started/ended/exit/captured.json всех четырёх results/verify/diagnostic/calibration.*, документы stage4-calibration-failure.md, stage4-calibration-poll0-result.md, stage4-affinity-full-calibration-result.md; docs/verification.md, protocol.md, experiments.md, final-verification.md; configs/plan.json, admission.py (80s нижняя граница и бюджет main), schedule.py (число режимов/профилей/runs).

Новая сеть и targeted diagnostic последним steering пользователя не разрешены; этот review их не запускает и не разрешает.
