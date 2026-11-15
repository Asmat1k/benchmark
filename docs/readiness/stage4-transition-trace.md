# Целевая трасса r80p1: результат и ограничения

14 ноября 2026, Europe/Moscow. **Этап 4 не завершён. Исходный многосекундный переход не воспроизведён; его причина остаётся inconclusive.** Нового исправления production-кода нет. Полная калибровка, bootstrap, generator, A/A, monitoring, pilot/power, freeze и main не запускались. Пороги и блоки не менялись. Два сабагента независимо проверили прежние данные и семантику трассы; один повторно разобрал новый raw. Это внутренний независимый анализ, не формальный внешний reviewer для calibration gate.

## Исходные свидетельства

Сначала прочитан полный `stage4-next-agent-prompt.md`, основной отчёт, сводка и материалы deep-review-v1. HEAD `d4cf0f82f330af1cd188febfa5f3757a5cf37799`; 134 source hashes совпали с inventory/release-state. Все 134 записи прежнего SHA256SUMS.json проверены до обновления читабельной документации; все 44 sealed-файла profile-validation проверены независимо. Исторические raw/seals/reports/manifest не исправлялись. Прежняя версия основного отчёта сохранена побайтно в новом исследовательском каталоге: его прежний SHA продолжает обозначать именно ту версию; приложение к текущему читабельному файлу закономерно меняет SHA документа.

У прежнего r80p1 ID4200–4899 median router-span43.196мс, диапазон40.274–45.242; до перехода median40.294. Уточнение границы: центральная область **42≤t<49с**, включая секунду48. Интервалы соседних reverse-пакетов стали5.161–14.960мс вместо9.800–10.197. Это переменная задержка, не один постоянный сдвиг часов. Обе pcap были `-Q in`; разделить forward qdisc/server/guest по ним невозможно. Senderlag в центре≤.017мс.

## Заранее заданный опыт

План и инструменты: `results/verify/readiness/stage4/transition-trace-v1/`. Сначала network-none UNIX-datagram selftest20echo, затем ровно один r80p1-check10000echo/100Hz/256bytes, seeds20261116/20261117, исходные poll0/minspacing/drain и buffered ingress pcap. Без affinity, без периодических resource samplers. Нет повторов до удачи.

Наблюдение: server ID/tag и четыре monotonic отметки вокруг recvfrom/sendto в памяти; server syscall/scheduler trace; net_dev_queue/start_xmit/xmit, netif_receive_skb; qdisc enqueue/dequeue. Не трассируется sender polling. `trace_clock=mono`, overwrite0,16MiB/vCPU, start/end brackets. PID из server-ready совпал с NSpid tracer; все syscall boundaries проверены внутри server brackets с учётом микросекундной точности trace text. Trace losses/overrun/commit-overrun=0 на обоихCPU. Последний блокирующий recvfrom завершился сигналом и отдельно учтён как неуспешный, не потерянное echo.

Linux6.12.76-linuxkit. Проверены runtime formats и upstream stable v6.12.76: net_dev_queue предшествует qdisc enqueue; net_dev_start_xmit следует dequeue перед вызовом драйвера. См. `kernel-placement.md` и первичные ссылки в нём. Мы **не используем -Q out как недоказанную границу** и не склеиваем epochpcap с monotonic. Queue→xmit включает residence и обслуживание kernel, не только вычисления netem. LinuxKit patches — ограничение сравнения upstream.

Mapping проверен:10000 forwardqueues,9925 forwardxmits/serverrecords; ID/tag/порядок совпали с ingresspcap. Каждый сопоставленный queue/xmit имеет тот же skb без промежуточного повторного использования указателя. Все xmits сопоставлены положительным qdisc dequeue поCPU/index/handle. В одном batch3 dequeue описывает три xmit; анализатор учитывает bulk и проверяет указатель головного skb. Ifindex глобально не уникален между namespaces: связь подкреплена именованными router events и жизненным циклом skb, а не одним индексом.

## Результаты

Raw: `results/verify/diagnostic/transition-trace.jNq2hqdS`,75 sealed-файлов. Все SHA проверены. Forwarddrops75/10000, reversedrops115/9925; tc counters и ID-сеты согласованы. Возвращено9810echo. Оба capture kernel drops0. Реальные contexts before/after побайтно равны исходному timer ENV, source hashes неизменны.

|Участок|Медиана,мс|p99,мс|Максимум,мс|
|---|---:|---:|---:|
|Forward queue→driver start|40.245|40.264|61.969|
|Driver start→server received|.047355|.114065|5.568985|
|Server received→before send|.001625|.012439|.2215|
|Server send syscall bracket|.009375|.042157|.421291|
|Router ingress→reply ingress|40.305|40.40976|62.542|
|Actual RTT|80.696083|81.473205|102.928166|

Посекундные median router-span40.298–40.336мс, queue→xmit40.244–40.2495мс, post-xmit→received .036159–.066494мс. Прежних многосекундных +~3мс нет, включая42–48с. Process RTT rho500/1000/2000=.001605/−.005374/−.002534, survival также clear; fitteddrift−.006564мс. Это отсутствие отбраковочного флага на данной инструментированной серии, не доказательство стационарности и не замена исторического suspect.

Sender-v2 passed: late3/10000=.03%, p99lag .019327мс, maxlag22.052288мс, peak3/10мс, mingap2.510мс. В этой инструментированной серии p99/maxlag хуже прежней profile-validation (.007875/3.208мс). Дизайн не позволяет приписать отличие observer без A/B; инструментирование не выдаётся за прежние условия.

### Что теперь удалось разделить

1. **ID2035:** после своевременного xmit до server received5.568985мс; sched_wakeup126242.393467→switch-in126242.399017 =5.550мс. Этот отдельный выброс локализован преимущественно в runnable→running echo-server. Он не объясняет прежний многосекундный переход.
2. **ID8504:** queue126307.043223→xmit126307.105192 =61.969мс; router-span62.542мс, RTT102.928166мс. Следующие два forwardпакета отправлены в том же bulk3, residence51.807/41.860мс. Это задержка **до исполнения echo-server**, её нельзя объяснить только его user-space обработкой.
3. Одновременно reverseпакеты ID8500/8501/8502 вышли bulk3 в126307.105346/.105348/.105348, residence61.674/51.291/41.241мс. Первое reversexmit через154мкс после forward. Senderlag IDs8508–8510 также нарушил10мс. Обе фильтрованные CPUленты не имеют выбранных событий126307.081025→.105183 (24.158мс). Server в этот период blocked S; после wakeup.105296 запущен.105622, всего.326мс runnablewait.

Следовательно, этот отдельный эпизод затронул обслуживание обоих направлений и sender; чистый server userspace stall не подходит. Поддерживается общий сбой своевременного guest/kernel обслуживания, но **тишина выбранных событий не равна остановке всех CPU**. Большинство scheduling/timer events не записывалось; host/vCPU deschedule, watchdog lateness и LinuxKit механизм не разделены. Причинную роль qdrant данные не доказывают. Эти единичные эпизоды не подменяют невоспроизведённый многосекундный переход.

## Цена наблюдения, исполнение и ограничения

Server cgroupCPU delta331109мкс; sender99879644мкс. Общее before/after окно103.73с содержит setup/stop, поэтому это не чистые per-core проценты за100с. Ringbuffers32MiB, дополнительные kernel events, server clock reads/allocations и tracer stop-file polling каждые50мс создают наблюдательную нагрузку. Tracer и server сериализуют после опыта; исходные tcpdump работают как прежде. Нет observer-free контроля; успешная processдиагностика не переносится на calibration.

Все команды из `/Users/dobrov/Desktop/Code/ITMO/benchmark`:

- `caffeinate -ims python3 -B results/verify/readiness/stage4/transition-trace-v1/run.py selftest`:09:00:00.505–09:00:01.675UTC (12:00МСК),1.170с,exit0, каталог `selftest.9lc_yiks`; hard60+10с.
- `caffeinate -ims python3 -B results/verify/readiness/stage4/transition-trace-v1/run.py network`:09:01:18.365–09:03:17.521UTC (12:01–12:03МСК),119.157с,exit0, `network.hkaiwzm_`; hard240+10с. В execution есть stdout/stderr/exit/started/ended/identitybeforeafter; точные shell/tools/plan скопированы в raw.
- Первоначальный hostoffline завершился exit1 до расчёта: нет NumPy. Следующий analyzeroffline1.648с/exit1 обнаружил ошибку предположения анализатора «один dequeue на skb»: реально bulk3. Оба отказа сохранены `offline/`, данные/измерение не повторялись. Исправлен только диагностический разбор bulk, затем analyzeroffline≈2с/exit0, собственный расчёт1.491с. Exactargv/exit/elapsed — `offline/bulk.execution.json`, stdout/stderr отдельно; timeout90с.
- Независимый stdlib разбор<1с: `independent-review.py/json`, `independent-findings.md`. Это исследовательские derived, не formalreview.

AC100%, крышка открыта (`AppleClamshellState=No`),118GiB свободно; measurementlock получен перед опытом и повторно проверен свободным после. Docker2vCPU/4109484032bytes/nativearm64 и все4 точных образа прежние. ENV SHA231ae4819874cf877f8e2234b4331171309906cb4c259b847c7ff8fc403039da. TLS DERfc2a5f4d7bc0fce861baee9207c82ff86bf502fda419cf45c73e3559d1a56d18, notAfter26ноября19:22:37МСК; на момент опыта>12суток, ориентир6+2суток соблюдён, не календарная гарантия. Исходники чисты; новые docs/results untracked сохранены. Свои контейнеры/сети/traceinstance удалены; чужие сети и unhealthyqdrant не тронуты.

## Продолжение

По заранее заданному правилу **никаких повторов этого опыта**: исходный переход не воспроизведён, итог inconclusive. Нового codefix и причин для полной калибровки пока нет. До следующего измерения нужен отдельный предметный план, различающий позднее обслуживание qdisc/watchdog и общую доступность guest/vCPU; текущие события только ограничивают участок задержки. Не вводить обязательную macOStrace и не объявлять hostпричину без соответствующих свидетельств. План обязан учитывать observerload и необходимость воспроизведения исходного перехода, не подбирать seeds/длину/пороги ради удачи.

Poll0 остаётся единственным ранее применённым исправлением. Исторические earlygates относятся к прежним sourcehashes; новый инструментированный processclear не создаёт applicable REPORT_MAP. Этап4 остаётся незавершённым.
