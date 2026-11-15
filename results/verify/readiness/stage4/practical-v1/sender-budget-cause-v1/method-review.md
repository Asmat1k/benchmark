# Независимая методика одного targeted sender diagnostic

14 ноября 2026, method_review. Только read-only анализ source и сохранённого calibration.sFWOAzbo/r80p1-after. Этот документ фиксирует прогнозы до новых diagnostic данных; численные acceptance thresholds не меняет. План code_review: один r80p1,10000ID,около102s полезного выполнения, исходный pinned poll0 sender,100Hz wall/threadCPU/task schedstat/context-switch snapshots, без per-select tracing. Это диагностический, инструментированный source, не новый qualification/calibrationpassed.

## Что уже установлено исходным failed

Независимое чтение sent/reply records подтверждает: группа late5481–5605 включает125слотов, maximum accumulatedlag432.064733ms на5530, maximum actual timestamp intersendgap129.313667ms на5508. Дополнительные разрывы62.459ms на5501,73.431ms на5511,77.639ms на5523 постепенно накапливают отставание; после5530 множество spacing≈2.5ms постепенно восстанавливает сетку. Это не одна432ms пауза. Утверждение «надо убрать единственную432ms VM паузу» не следует из raw.

Независимый cause-evidence PCAP audit уже показывает129.319/62.462/73.425ms browser-ingress gaps для5508/5501/5511. Поэтому solely ошибка planned-grid summary не объясняет деформацию: трафик фактически нерегулярен. Иная картина у5523: sender timestampgap77.639ms соответствует лишь.164ms PCAPgap, при5522 положительный centered timestamp-to-capture residual≈77.442ms. Source сохраняет timestamp **до** sock.send, поэтому задержка предыдущего send между timestamp и ingress — допустимое объяснение; realtime/monotonic mapping также не исключено. Ни один из этих offsets нельзя вычитать из RTT, и PCAP не является независимыми host часами внеVM.

Текущие сведения не доказывают ошибку production алгоритма. Правило max(plan,previous_send+2.5ms) объясняет catchup и сохранение backlog после задержек, а не источник задержек. Неизвестны per-episode actual CPU/affinity, runnable timeline, syscall blocking и host/vCPU scheduling. Прежняя affinity причина касалась watchdog колокации; её повторное появление в новой форме пока не доказано.

## Различимые прогнозы одного опыта

| Наблюдение при воспроизведении delayed-send интервала | Поддерживаемая интерпретация | Что не доказано |
|---|---|---|
| Wall delta значительно больше threadCPU delta, schedstat runqueue wait также растёт | Guest task ждала runnable исполнения | Какая host/foreign задача причинила задержку; рольVM idle |
| Wall−threadCPU растёт, voluntary switches растут, runqueue wait мал | Возможны blocking syscalls/read/receive/observer waits | Какой syscall блокировал без entry/exit меток; нулевойwait не исключает scheduler с отключённойstat |
| Wall≈threadCPU, observercost мал, долгая работа остаётся | Задержка преимущественно в учтённом выполнении task | Детерминированный sourcebug, receive backlog vs syscallCPU vs частотаCPU без дополнительной локализации |
| Разрыв в probe timestamps и browser PCAP совпадает | Реальная deformation offered traffic | Локализация доsend/вsend/наcapturepath поодним clocks |
| Observer snapshot имеет сопоставимый wall cost/CPU cost | Сам инструмент мог изменить событие | То же происхождение исходного неинструментированногоfailed |
| Событие не воспроизведено | Этот единственный диагностический период не выявил механизм | Исправление/отсутствие исходной причины, calibrationготовность или разрешение повторять доevent |

Schedstat runtime/wait/count и voluntary/involuntary counters полезны как отдельные cumulative observations. Их reads неатомарны относительно clocks и друг друга; небольшое расхождение runtime/threadCPU допустимо как инструментальное наблюдение, не повод менять критерии. Если kernel schedstats отключены/пусты, нули маркируются как отсутствие соответствующей диагностической способности. Guest runqueue accounting не измеряет непосредственно host-vCPU descheduling/steal; отрицание последнего по отсутствию guestwait неверно.

## Требования к минимальному observer

Сэмпл один раз на send, не в высокочастотном select цикле. Накопление структуры в памяти и один вывод после сбора; без printf/JSON/filewrite на каждой отправке. Фиксировать точную позицию observer относительно packet creation, productiontimestamp, sock.send и sent.append; она влияет на интерпретацию. Предпочтительно task reads послеsend, чтобы они не искусственно оказались между основным timestamp и send. Если добавлены дешёвые entry/exit wall/threadCPU метки вокругsend, они прямо локализуют gap source; без них честно оставить syscall блокировку неразличимой.

Каждому observer snapshot нужны собственные wall/threadCPU begin/end и ID, чтобы стоимость read/parse/append не растворилась в обычной нагрузке. Чтение /proc и rusage само может вызывать switches и page faults; соответствующие счётчики нельзя целиком приписать исходному механизму. Полезно хранить raw schedstat/status fields и temporal brackets. Нет нового произвольного acceptance порога observercost: публиковать все distribution/max/event совпадения и ограничить выводы при существенном вмешательстве.

Полные исходные sent/reply/RTT/ID/tag/pcap/qdisc/capture logs и все telemetry rows сохраняются; пропавшее RTT не good. Collection tag новый, seeds/workload/order фиксируются заранее. Фактическая affinity/CPU identity и probe cgroup принадлежат именно instrumented sender, а не только endpoint namespace. Если sampledCPU из /proc/stat обозначает last executed CPU, так и назвать; это не непрерывная CPU trace. Низкочастотные дополнительные clock/cgroup наблюдения допустимы только с явной привязкой кплану и cost, без нового бесконтрольногоtrace framework.

## Stop и допустимый вывод

Один заранее заданный r80p1 diagnostic, bounded execution с полным timeout/cleanup, без параллельного тяжёлого анализа и без автоматического follow-up. Partial/failed/clean результаты сохраняются. При ошибке telemetry/integrity/tags/source/ENV — технически непригодный diagnostic с явной причиной, не положительная научная оценка. При clean result без причинногоepisode — inconclusive for cause; не повторять неизменённо. При reproduced episode — сопоставить все wall/CPU/wait/switch/observer timelines и PCAP до предложенияfix; корреляции недостаточно для утверждения оконкретном чужомконтейнере/VMмеханизме.

Если механизм остаётся неразличимым, основнойfailed всё равно доказан и сохраняется; не требуется бесконечное VM jitter расследование. Productionpatch допускается только после конкретного воспроизводимого source/instrument failure или интервенционного свидетельства заявленного механизма, с regressions и прежними thresholds. Новый main или ещё одна полная calibration этой диагностикой не разрешаются автоматически.

## Сверка подготовленного candidate

До новых данных прочитан подготовленный probe.py: wrapper сохраняет основной production sender и timestamps; send_call_before/after — отдельные монотонные метки вокругsock.send; запись создаётся послеsend, CPU/proc/switch snapshot одинразнаID. Schedstat handle открывается одинраз, seek/read повторяются; cumulative runtime/wait/timeslices и RUSAGE_THREAD switches сохраняются соreadbrackets. Основнойрезультат иpartialtrace приошибке не теряются. Нетperselecttrace иправки productionthresholds. Это соответствует минимальному диагностическому вопросу; замечаний, требующих расширения trace, нет.

Snapshot threadCPU brackets исключают небольшую row/id allocation и append до snapshot; их нельзя назвать полной стоимостью всейwrapper. Дополнительный wallgap send_after→snapshot_after включает этуработу. Sendcallwall отдельныйполезныйhint syscall delay, но отдельногоthreadCPU bracket этогоsyscall нет. Affinityдо/после не измеряетнепрерывнуюexecutionCPU/watchdogcolocation; этотcandidate не можетдоказатьотсутствие такойпричины. Нулевыеschedstatwait неявляютсядоказательствомотсутствияguestwait, если kernelaccounting выключен. Эти ограничения переданыcode_review дляanalysishelper/плана; дополнительных инструментов самreview не вводит.
