# Выбор минимального исправления UDP sender

13 ноября 2026. Исследование выполнил Codex. Выбран кандидат: ограничить один вызов ожидания echo максимум1мс, сохранив абсолютный deadline и минимальный интервал2.5мс. Это небольшая правка существующего Python sender. Она подготовлена и проверена в отдельной копии, но **не применена к принятому релизу**. Причина редкой паузы57мс в E243q4gg ретроспективно полностью не установлена; кандидат не объявляется доказанным исправлением или принятым qualification.

## Новый фиксированный диагностический сбор

План опубликован до запуска: `results/verify/readiness/stage4/cause-diagnostic-v1/plan.md`. Одна baseline-проба10000ID/256байт/100Гц, прежний production calibration_probe.send. Убраны старые per-call usage/rusage/schedstat обёртки; добавлены захват первого monotonic timestamp и preallocated GC callbacks. Существующий Linux ftrace использован без потокового чтения,8192KiB/CPU; длительность guard увеличена до180с для100-секундной пробы. Вся новая диагностическая оснастка находится вне executable inventory, сохранена в raw/diagnostic-tools и проверена до/после. Права privileged относятся только к отдельному Linux tracer. MAC trace не требуется.

Команда агента `caffeinate -ims python3 results/verify/readiness/stage4/cause-diagnostic-v1/run.py`. Оценка2–4минут по прежним124с и37с; общий timeout240с с15с TERM/KILL резервом, фактическая длительность125.736с, exit0. Это отдельный диагностический опыт с новой наблюдаемостью, а не повтор неизменённой qualification и не попытка получить первый удобный passed.

Execution `results/verify/readiness/stage4/cause-diagnostic-v1/execution.6kzvbwbm/`: stdout.log,stderr.log,exit,started,ended,identity-before/after.json. Raw `results/verify/diagnostic/sender-cause-v1.AUXViDiC/`. Все82sealed файла проверены;16source snapshots до/после/копии совпали;134production hashes неизменны. Все10000sendto/recvfrom и19978pselect6 имеют entry/exit пары; PID/NSpid совпали, mono bracket покрывает весь sender, trace losses0 на обоихCPU. До/после каждого endpoint имеется ресурсное покрытие. Pcap10000ID/tag в обоих направлениях, netem2980000bytes/10000packets/drop0; capture kernel drops0, queues0 на границах. Throttling/OOM0; MemAvailable не ниже~3GiB.

Для этой диагностической пробы standalone v2 timing passed: late0.56%, max35.006086мс, burst4. Этот результат не заменяет failed E243q4gg и не засчитывается ни одной из трёх qualification-проб: instrumentation и план различаются. Автоматического повтора нет.

## Что установлено по причинам

85разрывов между отправками≥15мс:92.25% их суммарной длительности — sleeping по guest scheduler,2.46% — runnable wait,5.29% — состояние running. В наиболее длинном разрыве42.546мс (ID9699):40.491мс sleeping,1.863мс runnable,0.192мс running. Deadline107088104382719ns, sched_wakeup107088136054000ns: пробуждение позднее на31.671мс. Длинный pselect6 возвращает timeout, а не готовность socket. Следовательно, основной наблюдённый механизм — позднее обслуживание ожидания/пробуждения, а не большая очередь runnable Python.

GC28сборок, максимум2.1105мс wall/2.08525мс CPU; ни одна не пересекается с85длинными разрывами. В данном опыте GC не объясняет эти разрывы. Нельзя утверждать, что GC отсутствовал или был безвреден в историческом E243q4gg: там callbacks не собирались.

Есть вторичный эпизод ID35:15.793мс guest-running внутри17.089мс gap, безGC. Без CPU-stack/host-trace нельзя отличить Python/allocator CPU от отсутствия исполнения vCPU, пока guest считает задачу running. Поэтому вывод «все паузы только select» был бы слишком сильным. Новый опыт не воспроизвёл исторические57мс, но воспроизвёл десятки более коротких пауз и позволил классифицировать их механизмы.

Quota/память: ни throttle,ниOOM; низкая средняя нагрузка не исключает короткие host/VM задержки. ДополнительныеCPU/RAM не выбираются как исправление. Qdrant оставлен работать, его причинное влияние не доказано. CPU affinity/RT priority не устраняют установленное позднее пробуждение автоматически и не выбраны.

Отдельный analyzer process показал timerslack50000ns=0.05мс и CPUs0–1; это не прямое измерение slack исторического sender. Оснований считать default slack причиной30–57мс нет. Docker Resource Saver по официальному контракту выключаетVM при отсутствии работающих контейнеров; во время эксперимента контейнеры работали, поэтому обычный idle-механизм не объясняет паузу. Чтение settings-store macOS не завершилось и было прервано; фактическая настройка не подтверждается и не менялась. Host lowpowermode0, AC100%, caffeinate применялся. Эти проверки не дают гарантии непрерывного исполненияvCPU.

## Сравнение дешёвых вариантов без сети

Новый фиксированный diagnostic:30заранее заданных перемешанных блоков по1с,1000ticks/вариант, общий объём3000ticks. Абсолютная сетка10мс и минимальный интервал2.5мс, настоящий guest select/monotonic; безUDP/receive. Три варианта: исходный select до deadline, cap1мс, sleep до deadline−0.5мс с активным ожиданием хвоста. Скрипт `results/verify/readiness/stage4/cause-diagnostic-v1/wait-comparison.py`; caffeinate+network-none analyzer+timeout90с, exit0. stdout/stderr/exit рядом. Это описательное сравнение короткого ожидания, не оценка вероятности редких57мс пауз и не доказательство причинного улучшения на сети.

|Вариант|p99 lag,мс|max lag,мс|CPU одного ядра|
|---|---:|---:|---:|
|Исходный select|5.011|6.240|0.752%|
|Ожидание порциями≤1мс|0.771|1.853|2.082%|
|Активный хвост0.5мс|4.415|4.906|0.891%|

Cap1мс — наименьший кандидат с измеренным преимуществом на этой диагностике; CPU добавляет около1.33процентного пункта одного ядра, абсолютный расход остаётся малым. Механизм возможного улучшения: несколько коротких ожиданий вместо одного длинного, с повторным чтением абсолютного времени. Это не обеспечивает верхней границы OS/VM задержки: и1-мс ожидание может проснуться поздно. Гибрид не выбран, так как здесь sleep нередко уже перескакивал активный хвост. Native sender дороже и не устраняет тот же sleeping/VM механизм одним фактом смены языка. GC/буферы не выбраны из-за отсутствия подтверждённой связи с длинными паузами.

## Подготовленный кандидат и проверки

`results/verify/readiness/stage4/cause-diagnostic-v1/candidate.patch`:3добавленные строки и1заменённая; новый внутренний MAX_ECHO_WAIT_NS=1000000. На echo применяется min(remaining,cap); saturation получает прежний remaining. Финальный2-секундный drain не меняется. Payload/tag,10000ID,100Гц,2.5мс limiter, actual RTT, пороги и статистический метод не меняются.

7существующих sender/pacing tests прошли на отдельном candidate module за3.149с. Адресная проверка cap подтвердила main-loop≤.001с, полные100ID/replies и прежний drain2с. Первый вариант standalone assertion ошибочно считал drain только последним вызовом; проверка исправлена по числу уже отправленных сообщений, candidate не менялся. Это ошибка проверки, не production failure; раскрыта в candidate-cap-test.json. Offline mocked selftest диагностической обёртки также сохранил10000ID/replies. Ни одна из этих проверок не является реальной приёмкой таймингов кандидата.

## Следующий порядок без потери provenance

Применение кода требует нового source-bound релиза, release-state и пересмотра всех шести ранних gates с новым inventory; старые отчёты нельзя перепривязать заменой hashes. До этого кандидат остаётся отдельной копией. СменаENV/ресурсов сейчас не требуется. Далее нужен один заранее определённый полный qualification3×10000 сSTOP по первойfailed/inconclusive, запускаемый пользователем (5–6минут+setup). Только если он принят — browser bandwidth→calibration→generator. Если cap1мс не помогает, сохранить failed и пересмотреть именно среду/пробуждения; не подбирать cap по повторным qualification до успеха. Native переписывание не является выбранным следующим шагом.

Новых долгих команд сейчас нет. Source/ENV/TLS неизменны, шесть отчётов этапа3 сохраняют прежнюю применимость; qualification failed остаётся STOP, calibration/generator not_run. Контейнеры/сети диагностики удалены, measurement lock вновь получен/освобождён, qdrant не трогали. Полный verify не повторялся.

Воспроизводимые данные/числа и SHA256: `results/verify/readiness/stage4/cause-diagnostic-v1/{analysis.json,audit.json,wait-comparison.json,SHA256SUMS}`.

Первичные справки: [Linux ftrace](https://www.kernel.org/doc/html/latest/trace/ftrace.html), [timer slack](https://man7.org/linux/man-pages/man2/PR_SET_TIMERSLACK.2const.html), [Docker Resource Saver](https://docs.docker.com/desktop/use-desktop/resource-saver/), [clock_nanosleep](https://man7.org/linux/man-pages/man2/clock_nanosleep.2.html). Справки описывают механизмы, не удостоверяют причину конкретной пробы.
