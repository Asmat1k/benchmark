# Полная калибровка после poll0

14 ноября2026, Europe/Moscow. **Sender улучшился:14/14 passed. Этап4 не завершён: обязательные process-проверки3/6 основных echoсерий suspect. Предварительный результат calibration — inconclusive; официальная успешная публикация и bootstrap не выполнялись.** Это первый полный14+4 сбор после poll0. По запросу пользователя дополнительная watchdogдиагностика остановлена до любых её selftest/сетевых запусков и не возобновлялась.

## Сбор и целостность

Пользователь запустил `caffeinate -ims python3 -B results/verify/readiness/stage4/calibration-poll0-v1/run.py` из `/Users/dobrov/Desktop/Code/ITMO/benchmark`.

- Execution: `results/verify/readiness/stage4/calibration-poll0-v1/execution.et3hz8uc`.
- Raw: `results/verify/diagnostic/calibration.gIdWLx7o`.
- Начало09:18:38.470UTC, конец09:48:01.048UTC (12:18:38–12:48:01МСК);1762.578с,29мин22.578с; exit0.
- Все14echo×10000 и4saturation присутствуют;146sealedfiles проверены,45MiBraw. Полнота sealedset проверена отдельно от SHA. exit/ended создаются cleanup после sealing и не объявляются входящими в исторический seal.
- Plan/seeds неизменны, соответствуют штатному `collection_plan()` и заранее сохранённомуfixedplan. Источники134, HEADd4cf0f82f330af1cd188febfa5f3757a5cf37799, actualimages, ENV/TLSidentity до/после совпадают. В identity абсолютный hostпуть PEM при проверке внутри analyzer явно сопоставлен с тем же workspaceфайлом; байты сертификата не менялись.
- ID/tag/finite RTT/grid/spacing/pcap/directional drops/reverse denominators согласованы. Все28 ingresspcap имеют kernelcapture drops0; все loss0echo вернули10000ответов.
- Все28directional profile readbacks подтвердили delay/loss/rate/limit/jitter0/correlation0/seeds и emptyboundaryqueues; packet/byte delta соответствуют deliveredID и298bytes/frame.

Рабочий sender — прежнийpoll0. Новых productionfix, tracing, affinity, samplers, threshold/block/source/образ/TLSизменений нет. CPUценаpoll0≈одноядро установлена прежнимABBA; этот сбор не имеет новых непрерывныхCPUизмерений. Чужой unhealthyqdrant не менялся. После сбора свои контейнеры/сети отсутствуют, lock реально получен и освобождён повторной проверкой.

## Sender

|Серия|Maxlag,мс|Late,%|Processдиагностика|
|---|---:|---:|---|
|baseline-before|4.621|0|clear|
|r20p0-before|29.895|.07|suspect|
|r20p1-before|7.472|0|suspect|
|r80p0-before|.046|0|suspect|
|r80p1-before|.102|0|suspect|
|r20p0-latency|6.197|0|suspect|
|r20p1-latency|1.948|0|clear|
|r80p0-latency|8.724|0|suspect|
|r80p1-latency|7.698|0|suspect|
|r20p0-after|35.468|.04|clear|
|r20p1-after|16.523|.03|clear|
|r80p0-after|11.679|.02|suspect|
|r80p1-after|31.415|.07|suspect|
|baseline-after|14.366|.02|clear|

Все14sender-v2 passed, maxlate.07%≤1%, maxlag35.468481≤50мс, peakburst≤4/10мс. У прежних двухfailedseries lag стал129.225→35.468мс и53.693→16.523мс. Это положительное свидетельство исправления на полном объёме; сравнение двухпрогонов не доказывает устранение редкихпауз навсегда.

## Почему calibration пока не принята

В текущемконтракте processдопуски inference относятся к шести echoсериям:baselinebefore/after и4*-latency. **Из них3suspect:**r20p0-latency,r80p0-latency,r80p1-latency. Обеbaseline иr20p1-latency clear. Расширеннаядиагностика всех14 дала9suspect, но дополнительные6флагов before/after не вводятся как новыеformalprocessgates. Все survivalACF clear; флаги связаны сRTT.

|Основная серия|RTTmedian,мс|rho500|rho1000|rho2000|Fitteddrift,мс|
|---|---:|---:|---:|---:|---:|
|r20p0-latency|20.6240|.28590|−.02121|−.00452|.83990|
|r80p0-latency|82.1339|.46229|.15722|−.27836|.24219|
|r80p1-latency|83.2921|.47363|.38832|.14867|3.66352|

Прежняя отбраковка absrho>3.5/sqrt(n−lag),20окон иdrift>2мс сохранена. Нет выбрасывания хвостов, подбора длинблока, семян, thresholds или коррекции raw.

Вr80p1-latency окна35–100с имеют RTTmedians83.882–84.034792мс против80.544–80.700мс в спокойныхраннихокнах; routeringress→replyingressspan≈43.028–43.179мс против40.297–40.307мс. ОстатокRTT здесь также растёт примерно40.25–40.38→40.84–40.96мс, в отличие от прежнего короткогоprofile-validation, где остаток не рос. Основнойрост снова присутствует до reverseqdisc/clientreceive. Нельзя приписать весьновый эффект только одному компоненту.

Вr80p0-latency routerspan переходит40.293–40.294→~42.13–42.20мс, возвращается~40.296 и растётснова. Вr20p0-latency последние10с spanвыше≈12.09–12.14мс вместо10.29–10.30мс. Это длительные измененияполупути, а не только единичные редкиехвосты. В этом fullraw нет серверных/syscall/scheduler/watchdogtimestamps; точную причину netem/server/guest/host установить нельзя. Предыдущая инструментированная серия не наблюдала именно эти эпизоды и не переносит причиннуюлокализацию на них.

## Потери и capacity

Все16formal directional lossпроверок четырёхпрофилей before/after проходят прежние exactинтервалы99.875%; denominators фактические. В дополнительнойr20p1-latency forward138/10000 выходит за такойинтервал относительно1%; результат сохранён как исследовательский. Эта latencyсерия не входит в formal8serieslossfamily, поэтому её extraпроверка не объявляется новымformalотказом и не меняет thresholds.

Четыреcapacity:9.999321/10.001122/10.000634/10.000796Mbit/s (loss0forward/reverse,loss1forward/reverse), все9–11. Исторические валидированные bytecounts browser-bandwidth-v4.9r51339s повторно проверены по evidenceSHA. Изменились только auxiliarycalibration_probe.py и егоtest; browser/measure/counters/ENV прежние. Их консервативное сопоставление с новойcapacity даёт maxfraction.008378945983=**.837895%<10%**, всеWS/WT-S/WT-D×2направления. Это отдельная applicabilitycomparison, не новый source-boundgenerator/BWgate и не перепривязка старыхreports. Штатный `browser_bandwidth.package` под новыми hashes не выдавался за пройденный на старыхraw.

## Проверки и материалы

`results/verify/readiness/stage4/calibration-poll0-v1/review/`:

- `primary-review-v3.json` — окончательный первичный разбор; `primary.py`, stdout/stderr/argv/start/elapsed/exit отдельно.
- `extra-integrity.json` —28directional profile/counterchecks.
- `components.py/json` — все14×20окон, samepcapspan и остаток без синхронизации разныхчасов.
- `bandwidth-comparison.json` — applicability и ratios из проверенных bytecounts, без новой formalпубликации.
- `independent.py/json`, `independent-findings.md`, execution/stderr — независимый сабагент: существующийsender_quality и stdlibвоспроизведениеprocess. Совпали все14sender/process, maxACFразница4.24e−15. Это внутренний независимый анализ, не выдуманный внешнийreviewer и не автоматическое одобрение assumptions.
- `cleanup-check.json`, `STOP.json`, `summary.json`, `SHA256SUMS.json`.

Offlineкоманды выполнялись безсети в точном analyzerс hostmountedworkspace, timeout90с каждый. Первый primary0.9с/exit1: абсолютный hostпуть PEM не существовал как путь в контейнере; исправлено только сопоставлениеpath. Primaryv2≈2с/exit0 сохранил слишкомширокую классификацию extra-latencyloss; финальныйv3 явно использует прежнююformalbefore/afterfamily, всёчисленноенаблюдение сохранено. Это исправление scopeисследовательскогоразбора, не смягчениеacceptance. Первичныеv2 JSON/logs сохранены и не являются окончательнымвыводом. Components≈1.4с/exit0; независимыйсохранённыйрасчёт.774с/exit0. Дополнительнаяперепроверка профилей/counters<1с. Exacttimings/argv есть вexecutionJSON. Raw/seals/старые reports не правились.

**Дальше не запускались bootstrap, calibrationpublication, generator, новаясеть, watchdogselftest/trace или повторfullcalibration.** Processусловия ужеinconclusive, поэтому зависимости остановлены. Userрезультат отвечает на вопрос «помогло ли исправление»: sender — да на этомполномсборе; RTTprocess — нет. Для дальнейшейлокализации теперь есть воспроизведённые длительныепереходы в полномraw. Следующийэксперимент требует отдельногосогласованногоплана; приостановленнаядиагностика автоматически не возобновляется. Этап4 остаётся незавершённым, применимыйREPORT_MAP с calibration/generatorpassed не опубликован.
