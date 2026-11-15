# STOP браузерной полосы: несопоставимый CPU baseline

BW_RUN `results/verify/diagnostic/browser-bandwidth.oc6op_bb`. Пользовательский execution `results/verify/readiness/stage4/release-v3/bandwidth-execution.AmGbbSCv`,13ноября2026,19:55:17–19:57:28UTC,131с,exit1. Сбор остановлен на индексе0,WT-S;WT-D/WS не запускались. Calibration/generator не запускались. Повтор без исправления запрещён.

## Наблюдённый отказ

Стандартный measure.sh дошёл до стадииstabilization и не подтвердил условия в течение предусмотренного30-секундного окна. Ledgerstopped,STOP и quarantine сохранены штатно. Все1400слотов WT-S (200warmup/1200measurement) имеютsent и корректный256байтовый echo; серверactive0,measurementreceived/echoed/write_attempted1200,errors0/invalid0. Это не полный принятый raw: publication не выполнялась.

Повтор точного штатного awk-предиката на сохранённых baseline/idle файлах дал browserexit0,serverexit0,routerexit1:

|Role|Baseline peakCPU|Baseline ceil|Last idleCPU|Idle ceil|Predicate|
|---|---:|---:|---:|---:|---|
|browser|1.12455%|2|0.93574%|1|passed|
|server|0.87347%|1|0.53436%|1|passed|
|router|0.94525%|1|5.49158%|6|failed|

Это проценты одного ядра по фактическим interval/cpu_usage, как в measure.sh, а не формальный generator CPU gate. Router имеет1vCPUлимит. Ресурсные sampler logs пусты,throttled_usec0/OOM0 во всех120снимках каждого сервиса. До/после нагрузки netem backlog0/qlen0/drop0; qdisc-stable отсутствует, поэтому длительное пустое окно не объявляется доказанным.

## Конкретный дефект коллектора

В docker/measure.sh baseline CPU сохраняется на строках91–95. Дополнительный sample-backlog observer запускается только затем,строки96–100, и остаётся работать при сравнении idle CPU. Значит, исходный baseline и idle содержат разные наборы наблюдателей. Baseline router здесь<1%, а последние15снимков содержат3.3–26%CPU, включая работу последующих stabilization tc/jq probes. Конкретный последний CPU reject воспроизводится без сети.

Персональная CPU-стоимость backlog observer не записана. Поэтому несоответствие условий подтверждено кодом, но нельзя приписать все5.49%CPU одному процессу или исключить все прочие вклады. Отдельные попытки stabilization не журналируются; причины каждой из них задним числом не восстанавливаются. Предупреждения quic receive-buffer/stream reset сохранены вserver-log; они не являются наблюдённым местом выхода — все1400ответов получены,exit произошёл наstabilization.

## Минимальная правка и затронутые допуски

Отдельный кандидат `results/verify/readiness/stage4/release-v3/bandwidth-stabilization-candidate/candidate.patch` переносит существующий запуск sample-backlog перед запуском resource samplers и baseline. Порог CPU,30с ожидания,1000мс пустой очереди и все численные правила сохраняются. Другая конфигурация наблюдателей исключается из сравнения. sh-n отдельной копии прошёл; сетевой опыт с ней не выполнялся. Рабочий measure.sh не изменён.

Применение изменит executable source hash: нужен новыйcommitted release/release-state, проверка и новая публикация шести ранних gates, новый BW_RUN и заранее заданный план. Нельзя править baseline/raw/quarantine или обновлять их hashes радиpassed. Допуск UDP sender остаётся историческиpassed для релиза3605994; перенос его применимости на изменение measure.sh требует явного dependency review (его коллектор measure.sh не вызывает), а не объявления прежнего134-file inventory неизменным. При невозможности обосновать применимость нужен новый фиксированный qualificationплан, без скрытого повтора.

## Сохранность и очистка

Source inventory134,ENV/TLS/release иimages до/после/current совпали; исходный ENV совпал с фактическим context. Измерительные контейнеры/сети удалены,measurement lock получен и освобождён. Постороннийqdrant не трогали. Предыдущаяqualification Mbdvg8v6 не отменена этим техническим отказом. Нового bandwidth/calibration/generatorpassed нет, этап4не завершён.

Review: `results/verify/readiness/stage4/release-v3/bandwidth-oc6op_bb-failure-review.json`. Inventory всех сохранённых partial/execution файлов: `results/verify/readiness/stage4/release-v3/bandwidth-oc6op_bb-failure-inventory.json`. Это отдельный post-failure снимок, не выдуманный штатный seal. Quarantine не редактировался.
