# Независимый обзор первой попытки generator и изменения execution policy

15 ноября 2026 МСК. Reviewer `/root/design`, внутренний отдельный сабагент. Только чтение первичных файлов и короткое суммирование JSON, без Docker/сети и без нового сетевого опыта. Проверен execution.k0tpnz1w и quarantine первого run generator-20.PDOSDsWY. Все исходные файлы оставлены без изменения.

## Что реально произошло

Execution начат 2026-11-14T21:15:51.124164Z и закончен 21:18:12.197326Z, exit1; source HEAD676b1c8a395e8d706f14c6cbf12b3b0b99504c21. Отказ — `Measurement failed at stabilization`. По журналу собственные три контейнера и две сети удалены; wrapper сохранил containers_after только ai-grepa-qdrant-1.

Первая назначенная сторона — WT-S/baseline/20Hz. В quarantine/page.json имеются 1400 slots:200warmup и1200measurement. Server counters: received/echoed/write_attempted1200, errors0, invalid0, active0; warmup200. Это свидетельствует о выполнении браузерного обмена, но не является официальной приёмкой raw: publication не состоялась, полный validator этой попытки не выполнялся. Ledger имеет stopped/incomplete_log и STOP. В сетке6 попытка сделана для одной стороны, пять не запущены; нельзя объявлять шесть runs собранными или gate failed только по численным generator criteria.

CPU baseline peak ceil: browser1%,server1%,router6%. Все четыре наблюдённых сравнения failed:

|Попытка|Idle browser/server/router,%|Причина|
|---|---|---|
|1|1/1/7|router7>6|
|2|2/2/6|browser2>1,server2>1|
|3|2/2/6|browser2>1,server2>1|
|4|2/2/6|browser2>1,server2>1|

Каждый сохранённый queue series содержит11 snapshots,22netem records; во всех qlen/backlog0,drops0. Это наблюдение существующей проверки пустоты, не доказательство CPU стабилизации. Все роли имеют конечные sampler logs без sampler_error и без OOM по сохранённым samples. Причина небольшого CPU превышения не исследовалась и не установлена; новый UDP/VM разбор не нужен.

## Минимальное честное изменение

Явный `execution_policy=finite-browser-study-v1` в plan и source-bound protocol может сделать именно CPU-return-to-baseline наблюдаемым ограничением вместо безусловного запрета публикации. Обязательные пустые очереди, server active0, полноценные ресурсы/журналы, валидные sampler интервалы и временные границы сохраняются. Техническая неполнота по-прежнему закрывает допуск.

Не записывать stable=true при failed CPU comparison. Хранить раздельно queue_empty=true и cpu_baseline_comparison=failed с неизменными первичными CPU рядами/markers/comparison; общий stable может бытьfalse, а execution_admissible=true только при точной конечной policy и всех остальных условиях. Не переписывать штатный вывод comparison и не ставить экспертные review flags без выполненной проверки. Raw validator должен принимать такой статус исключительно для явной policy и заново сверять необходимые evidence, а legacy strict путь оставлять прежним.

Это изменение правила допуска после первой технической остановки, а не доказанное исправление ошибки CPU измерителя. Нельзя говорить, что все правила приёмки остались прежними: неизменны численные **generator** критерии lag/rate/miss/CPU<70%/throttling/OOM; прежняя обязательность CPU возврата изменилась. Исследовательская область теперь включает измеренное остаточное CPU состояние данного стенда, без утверждения одинакового idle перед каждым протоколом.

Однократная новая заранее фиксированная сетка6 после фактического нового ENV и timer обоснована невозможностью закончить исходный collector при старом предусловии. Это новый сбор на изменённом протоколе, а не продолжение или успешная замена первой попытки. Историческая первая попытка и её5not_run остаются отдельно; не использовать её WT-S вместо одной стороны новой сетки и не набирать шесть удачных запусков из двух попыток. На новом сборе плохие performance outcomes сохраняются; автоматического повтора до passed нет.

Новый plan меняет ENV config, а policy/protocol меняют bindings. Требуется новый фактический context; старый timer ENV нельзя редактировать или просто перепривязать hashes. Ранние свидетельства переиспользовать только с предметной applicability, точными old/new sources и disclosed execution-rule delta. Images/client/server/TLS могут оставаться прежними, что не означает неизменность всего исполняемого протокола.

## Вердикт

Допускаю предложенное минимальное изменение как согласованное исследование реального несовершенного стенда при сохранении всех данных. Оно не удостоверяет достаточность готовой реализации: перед сетью нужны independent review нового raw/schema/measure пути и meaningful regressions (failedCPU при строгой policy отклоняется; finitepolicy принимает только complete observations+emptyqueues; missingresources/nonemptyqueues отклоняются). Никакая часть этой попытки здесь не объявлена официальным complete/passed generator.

## Review готового finite пути перед новым timer/generator

Прочитан фактический diff measure.sh, record.py, raw.py, plan/schema и тестов. `record.run_spec` создаёт observation marker только при точном execution_policy. Под finite policy `quiet_cpu` вызывается прямой командой под set-e: selector failure завершает сбор, не является обычным CPU comparisonfailed. `validate_stabilization` заново восстанавливает summaries по сохранённым ресурсам/markers, сравнивает с primary summaries и comparison, требует truthful stable/cpu_recovered и11пустых queue snapshots. После этого общий validate_resources остаётся обязательным. Тем самым недостающий coverage не стал nonfatal. Legacy strict путь продолжает требовать stabletrue.

Обнаружено одно исправимое несоответствие deadline: внутри loop истечение30с ставит stable0, но finite ветка затем делает break по queues_empty1 и после loop проверяет толькоqueues. При CPU comparisonfailed такой просроченный attempt будет принят с декларацией wait_limit_s30. При recoveredtrue он позднее откажет по stable/cpu_recovered mismatch. Перед положительным finite завершением нужна безусловная проверка текущего времени против deadline, сохраняющая настоящий30с максимум; существующей строки, лишь меняющей stable, недостаточно. Сообщено root до сети.

Тесты покрывают строгий отказ при failedCPU, finite принятие тех же истинных наблюдений, отказ при фиктивном stabletrue, непустой финальной очереди и пустом sampler role. Новый класс расположен после unittest.main: module unittest его видит, direct запуск файла — нет; это малое организационное замечание, не причина откладывать module test packet. Тесты reviewer самостоятельно не запускал; root сообщил6+2passed. После deadline исправления, cleanrelease и фактического нового ENV дополнительных блокирующих ошибок готового пути этим review не выявлено.
