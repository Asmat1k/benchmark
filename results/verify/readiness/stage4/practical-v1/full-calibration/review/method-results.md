# Независимая численная проверка calibration.sFWOAzbo

Новый prospective сбор **не прошёл** фиксированный observed-profile-check-v1 из-за r80p1-after. Exit0 означает завершение сбора, не его приёмку. Причина отказа не требует изменения порогов, исключения хвостов либо нового неизменённого повтора.

Исполнение независимого standard-library script method-results.py:1.369s,120s timeout,exit1,stderr пуст. Точные argv/UTC/cwd/exit в method-results.execution.json. Скрипт не импортирует production acceptance/calibration_report/calibration_observed и сам разбирает PCAP/счётчики, timestamp decimal-предикаты, deque rolling windows, statistics median и nearest-rank p99. Сохранены method-results.json/stdout/stderr/exit; source/script/captured refs указаны в JSON. Ни raw, ни историческиеreports не менялись. Это внутренний review команды, не внешний reviewer.

## Причина отказа

| Показатель r80p1-after | Наблюдение | Фиксированный допуск |
|---|---|---|
| Late sender slots, lag≥10ms | 242/10000=2.42% | ≤1% |
| Максимумы lag≥50ms на1200слотов, фазы0/1/2/3/4 | 27/28/26/27/26 | ≤12 в каждом окне |
| Количество нарушивших lagproxy окон | 4005/4005 | 0 |
| Maximum lag | 432.064733ms | diagnostic, не отдельный gate |
| Minimum spacing | 2.500625ms | ≥2.5ms |
| Burst в полуоткрытом10ms окне | 4 | ≤4 |

Witness max окна по фазам:0:IDs0–5995;1:216–6211;2:2–5997;3:3–5998;4:4–5999. Все счётчики каждого окна сохранены, не только выгодная фаза/среднее. Среди отмеченных lag≥50ms IDs есть3583–3596,5485–5487,5490–5599,5838–5843 и6211. Это идентификаторы наблюдений, не доказанная полная причинная footprint паузы.

Loss1 серия имеет9817RTT и183missing. Max known joint-bad по фазам70/65/70/64/68, unknown29/20/23/27/27; эта частично наблюдаемая joint deadline часть публикуется как lower bound, не дополнительный полный loss1 gate. Достаточные причины отказа — полные lag counts и latefraction, которые missing не скрывают.

Медленный хвост r80p1-after не удалён. Все RTT:median80.681042ms,p95 87.408ms,p99 111.687292ms,max264.405417ms. Строго выше observedp99 находятся98RTT; их исходныеIDs/RTT сохранены, ties остаются вbody. Tail median130.236229ms,mean139.984406ms. RTT по фактическому send сохранён, lag из него не вычитался. Остальные серии также имеют полные all/body/tail и missingID accounting.

## Остальные численные проверки

Проверены146seals, фиксированные источники/FIXED-SHA256, равенство captured/fixed collection-plan и неизменность ENV/source до/после. Полные ordered10000ID всех14echo, finite timestamps/RTT, correspondence массивов и independent PCAP tags/flow/denominators/counter deltas проверены; нарушений этих численных integrity условий не обнаружено. Detailed integration/network/readback/source applicability review выполняет root отдельно.

Все120 median окон шести latency/baseline коллекций содержат вернувшиесяRTT. Все8difference envelopes с **обеими** baseline лежат внутриtarget±2ms. Общий диапазон20msконтрастов19.8548535–20.101833ms;80msконтрастов79.991187–80.1145205ms. Это наблюдённые оконные диапазоны, неCI. Успешные latency medians не отменяют нарушения нагрузки другой коллекции.

Все16formal directional losschecks проходят0drops/loss0 и exact `[.005,.015]` loss1 по фактическим denominator. Кроме формального семейства сохранены12diagnostic directional checks latency/baseline. Всеloss0 RTT полны. Loss1 missing не заменяются числами и не становятся своевременными.

Все4capacitychecks проходят:10.000796461/10.000633656/10.000308045/9.999158060Mbit/s в порядкеloss0forward/reverse,loss1forward/reverse. Из historical applicable bytecounts и **новых** capacities отдельно рассчитаны6conservative ratios по минимуму capacity направления средиloss0/loss1; максимальнаяfraction.008380318906<.1. Это новый производный ratio, не переписанный старыйreport, и он не устраняет senderfail. Baseline-only workload applicability и ограничение observed overhead остаются.

Итог: numeric review failed. Не выставлять observed_period_reviewed как автоматическое одобрение, не объявлять calibration/generator/stage4/mainpassed. Сохранить STOP, полную коллекцию и все результаты, затем исследовать конкретную причину деформации sender без сетевого неизменённого повтора и без численных послаблений под этот результат.
