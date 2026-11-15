# Локализация RTT и закрепление UDP sender

14 ноября 2026, Europe/Moscow. Минимальное исправление применено коммитом `d66559066b704fde567b6c9f92f57e2dcde22698`: только UDP echo sender закрепляется за минимальным разрешённым CPU перед началом сетки. Poll0 сохранён. Saturation и браузерный генератор не менялись. Дополнительного занятого ядра, изменения ресурсов Docker или численных допусков нет.

**Статус:** причинный механизм подтверждён для наблюдавшихся переходов; применённая версия проходит 16 связанных unit/regression tests. Проверка рабочего кода и дальнейшие gates описываются ниже; весь этап 4 ещё не принят. Это не обещание устранения любой редкой паузы VM.

## Что удалось установить

Полный `calibration.gIdWLx7o` после poll0 имел sender14/14passed, но process3/6suspect. Мы исследовали именно оставшуюся RTT-проблему, не повторяя полную калибровку до удачи.

Новая `watchdog-trace.zk2E5PYS` записала programmed expiry, actual callback и sampled kernel now для netem watchdog, CPU процессов и пакетов, server syscalls, два исходных ingress pcap. PID/NSpid, mono brackets, all ID/tag/counters и 87seals проверены; trace losses/overrun0. Sender/process этой серии clear, но посекундно виден характерный эпизод на24–26с:

|Состояние|Sender CPU|Forward watchdog CPU|Median callback lateness|Median residence|
|---|---:|---:|---:|---:|
|До миграции|0|0|около.003мс|около40.244мс|
|Секунда24|1|0|1.883мс|42.125мс|
|Секунда25|1|0|1.958мс|42.173мс|
|После возврата|0|0|около.003мс|около40.244мс|

Sender мигрировал наCPU1 в23.460839с и обратно в26.854010с. Во время задержки он занималCPU1 почти всю секунду и отправлял вовремя: maxlag≈.123мс. Reverse watchdog оставался наCPU1 и был своевременным: callback≈.00275мс, residence40.244мс. Sampled kernel now даёт ту же задержку forwardcallback; это не только поздняя запись trace.

Таким образом, задержка уже присутствует при обслуживании kernel watchdog, раньше echo-server. Точный механизм host/vCPU idle или доставки виртуального timer interrupt не установлен. Нельзя объявлять паузу всего host/VM по фильтрованным guest-событиям.

Upstream Linux6.12.76 объясняет возможность сохранения timer на прежнем CPU: [sch_api.c](https://raw.githubusercontent.com/gregkh/linux/v6.12.76/net/sched/sch_api.c) использует pinned watchdog и ставит NET_TX; [dev.c](https://raw.githubusercontent.com/gregkh/linux/v6.12.76/net/core/dev.c) планирует его на CPU callback; [sch_netem.c](https://raw.githubusercontent.com/gregkh/linux/v6.12.76/net/sched/sch_netem.c) назначает следующий срок головы очереди. Повторный запрос уже ожидающего того же срока не обязан переносить timer на CPU нового sender.

## Причинное вмешательство и уточнение модели

Заранее заданный `migration-causal.6itZemcx`, execution `migration-causal-v1/network.2oi9u1_y`:232.094с,exit0. A:10000echo, sender0→1 наID3000→0 наID6000. B:10000echo, постоянныйCPU0. Одинаковые r80p1/seeds20261116/20261117, прежние packet/grid/drain/capture, никаких исключённых boundary samples. 146seals и нулевые потери trace проверены. Общие seeds — shared random numbers, не независимые реализации потерь.

**Контроль A сохранён как failed/suspect:** sender maxlag50.531934мс>50,processsuspect. Его искусственная нестационарность не засчитывается как qualification.

Первоначальная упрощённая гипотеза «watchdog остаётся наCPU0 весь участок и возврат немедленно восстанавливает задержку» оказалась неполной. Forward watchdog позднее перебазировался: CPU0до36.142639с, CPU1с36.166246до68.652110с, затемCPU0с68.670160с. Поэтому исходный упрощённый причинный критерий не объявляется полностью пройденным задним числом.

Но обе принудительные миграции воспроизвели более точный механизм:

- После0→1 осталось613callback на прежнемCPU0, medianlateness2.806741мс. После переноса watchdog наCPU1, при sender всё ещёCPU1, medianlateness≈.002735мс.
- После1→0 осталось858callback на прежнемCPU1, medianlateness1.872060мс. После переноса watchdog наCPU0, при sender всё ещёCPU0, medianlateness≈.002640мс.
- Kernel sampled now подтверждает≈2.805891/1.870975мс. Поздний callback, а не только задержка последующего dequeue, несёт основную добавку.

Точный rebase разобран отдельно: новый packet приходит на новом CPU уже после срока прежней головы, его `qdisc_run` обслуживает просроченную голову и программирует timer следующей головы на новом CPU. Для этого не требуется доказывать пустую очередь. Точные строки raw и SHA — `kernel-review/dynamic-rebase-review.md`.

B с постояннымCPU0 прошёл sender/process: maxlag25.876875мс,late.09%,burst3; rho500/1000/2000≈−.000429/−.001779/−.001858. Forwardcallbacks всеCPU0, callbackmedian.003118мс,p99.011131мс; queue→xmitmedian40.244мс,p9940.257мс. Единичные задержки остаются: maxRTT119.476мс и maxforwardcallback24.006мс. Они не скрыты и не доказывают провал sender, чей фактический maxlag ниже50мс.

Решение применить минимальный кандидат опирается на естественную миграцию, оба принудительных изменения и восстановление при co-location, а не только на успешный B. Новая отдельная проверка рабочего кода обязательна; B не подменяет полную калибровку.

## Почему выбран этот вариант

|Вариант|Дополнительные затраты|Свидетельства|
|---|---|---|
|Закрепить только echo sender|Однократный syscall, без нового занятого CPU|Устраняет наблюдавшееся расхождение sender/watchdog CPU|
|Server poll0|Примерно ещё одно занятое vCPU|Основная задержка наблюдалась до server; не выбран|
|nice+10 для sender|Без нового ядра|Проверял бы конкуренцию с server, но не установленный late watchdog|
|Thread timer slack|Малые|Не относится напрямую к untimed recvfrom, poll0 и собственному kernel watchdog; не применялся|
|Глобальные настройки VM, RT priority, новые CPU/RAM|Больше изменений и цена|Причинная необходимость не показана|

Выбор CPU производится из фактической разрешённой маски, а не жёстко из CPU0. В текущей DockerVM minallowed=0. Сужение task affinity — новая политика исполнения, даже при прежних численных лимитах и одинаковом ENV. Стоимость прежнего poll0≈одно vCPU остаётся; эта правка не добавляет ещё один busy loop.

## Регрессии и рабочая версия

Новая проверка выбора min{3,7}=3 перед timeline на старом коде воспроизвела отсутствие affinity (FAIL), saturation-no-affinity осталасьOK. После правки все16тестов прошли за5.548с unittest /7.429с вместе с Docker: pacing/grid/ID/actualRTT, affinity ordering, saturation, directional loss/tag, saturation window, neighbors, browser byte counters/baseline order и trace coverage/loss. Логи `solution-research-v1/candidate/red.*` и `green.*`. Значения thresholds и существующие тесты не ослаблялись.

Source commit и release-state обновлены. Старые passed reports не перепривязаны к новым hashes, образы не пересобирались: sender/test монтируются с host. Порогов/сэмплов/блоков/seed selection/RTT correction нет.

## Ограничения инструментов и технические отказы

До основного watchdog опыта два network-none selftest отказали: отсутствие standalone kill, затем неправильное предположение оPID1 в host-PID namespace. Оба отказа сохранены; остановка исправлена на Docker-container-targeted USR1, собственные оставшиеся trace instances удалены. Третий selftest:20echo,40timerpairs,zero-loss,passed. Основной watchdog опыт запущен только после него.

Привязка timer→direction проверяется по same-CPU start и следующему qdisc dequeue, включая positive bulk-lookahead: вариант «только следующийNULL» терял большинство соответствий. Первые parser outputs сохранены, окончательное независимое соответствие всех19707start консистентно. Init/cancel/expire_exit не записывались; direction/time semantics и CPU подтверждены доступными событиями, host-причина не доказана.

В исторических pcap независимо обнаружены отрицательные epoch-скачки≈17.760/4.449мс. Они не совпадают с началом длительных режимов и не объясняют независимый monotonic RTT, но не позволяют наивно склеивать эпоху pcap с monotonic. Новая причинная локализация основана на одном mono clock. Полный список timestamp discontinuities сохранён в transition-review/clock-analysis.json.

Попытка запустить production validation была сначала не исполнена из-за лимита сервиса автоматической проверки разрешения. После команды пользователя «продолжи» внешний preflight обнаружил BatteryPower, но из-за ошибки shellfailfast коллектор всё же стартовал. Он остановлен SIGTERM: execution.9k9hi6k6 exit130/raw affinity-validation.C9bJRLo6 сохранены как технически недействительные; неполные probe/pcap могли не сериализоваться. Никакой численный результат из этого сбора не используется. Preflight перенесён внутрь set-e коллектора до создания raw/network и под общий deadline270+10с. Отдельная регрессия проверяет отказ BatteryPower до первого Docker вызова. Пользователь подтвердил подключение AC перед новой проверкой.

Все материалы исследования находятся в `results/verify/readiness/stage4/solution-research-v1/`: независимые agent findings, планы, scripts, raw paths, executionstdout/stderr/start/end/exit, SHA. Никаких правок прежних raw/seals/reports; данные сохраняются также для неудачных и неполных попыток. Все самостоятельно выполненные измерения ограничены<5мин; более длинные команды запускает пользователь. Generator/A/A/monitoring/pilot/power/freeze/main не запускались.

## Итог проверки рабочего кода

После подтверждения AC выполнен единственный полный запланированный сбор `affinity-validation.83SwishH`, execution `production-validation/execution.da9vk1_q`:13:29:23.980–13:33:01.968UTC (16:29–16:33МСК),217.988с,exit0. R80p0→r80p1,по10000echo, без ftrace/server instrumentation/ресурсных периодических samplers. Применённый probe побайтно равен `docker/calibration_probe.py` нового коммита, source134 до/после совпали, реальные ENV совпали с исходным timer ENV. 50seals проверены, kernelcapture drops0, очереди опустели, counters/ID/tag согласованы.

|Проверка|r80p0|r80p1|
|---|---:|---:|
|Sender|passed|passed|
|Maxlag,мс|35.367858|12.990372|
|Late,%|.15|.02|
|Burst/10мс|4|3|
|RTTmedian,мс|80.511125|80.496167|
|Process|clear|clear|
|Fitteddrift,мс|−.001232|.000228|
|Возвращено|10000|9810|
|CPU после сбора|[0]|[0]|

R80p1 forward75/10000 и reverse115/9925; оба прежних exactинтервала включают1%. SenderCPU≈97.60/97.69% одногоядра, throttling0; additionalbusycore не появился. Пятисекундные median routerspan40.251–40.260/40.249мс, прежних длительных состояний+1.84/+2.84мс нет. Независимый расчёт подтвердил те же итоги за.258с; основной offlineрасчёт и его exactargv/exit/time сохранены отдельно. Unit16/16 и shortprofiles2/2 прошли; полный набор gates пока не пройден.

Следующий обязательный длинный шаг подготовлен, но НЕ запускался: `caffeinate -ims python3 -B results/verify/readiness/stage4/solution-research-v1/qualification/run.py` из корняпроекта. Это ровно прежние три baseline qualification по10000echo, около6–7минут, запускает пользователь. Журналы/execution/RAW_RUN уникальны; остановка при первой failed/inconclusive сохранена. Эта команда не запускает полную calibration/generator. После результата нужны все3quality/integrity/resourcechecks, затем применимые earlygates и полная14+4calibration/научнаяприёмка иgenerator. Старые reports не перепривязаны. Этап4 остаётся незавершённым до их прохождения.

Перед передачей команды подтверждены отсутствие своих контейнеров/сетей и свободный lock; чужойqdrant не тронут. Читабельная передача обновлена; raw/seals и технически невалидные попытки сохранены отдельно. Полный набор входов, scripts, execution, выводов и SHA находится в `solution-research-v1/`.
