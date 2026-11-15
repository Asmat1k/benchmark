> Исследование14ноября: применёнUDPecho poll0 (commit12ba5e5),11testsOK,короткийABBAпоказалсильныйвыигрышsender/RTTзацену~одноговиртуальногоядра. Остаточныйпереходr80p1неустранёндоказанно;capture/affinityкакfixнеподтверждены. Этап4по-прежнемуне завершён. Читаемыйполныйотчёт:[stage4-deep-investigation.md](stage4-deep-investigation.md).

> ТекущийSTOP: полнаяcalibration.lShojabe собрана(exit0), но первичнаяприёмкаfailed:2из14senderподсерийmaxlag>50мс. Дополнительноlong-dependenceflagsв2latencyподсериях. Полосаpassed(0.838%),calibrationreportнеопубликован/bootstrapне запускался,generatornot_run. Этап4не завершён;новыхкоманд/повторовнет. Подробности:stage4-calibration-failure.md.

> Текущее состояние: браузерныеraw новогоBW_RUN browser-bandwidth-v4.9r51339s приняты длявсехтрёхрежимов. Полнаякалибровкаподготовлена, ожидаетпользовательскогозапуска. Ещёнетcalibration/generatorpassed, этап4не завершён.

> Актуально: исправлениеbaseline применено в494e1a9. Шестьновыхраннихgatespassed; qualificationMbdvg8v6 применима по отдельномуdependencyreview. НовыйBW_RUN browser-bandwidth-v4.9r51339s подготовлен, сбор ожидаетпользователя. Calibration/generatornot_run, этап4не завершён. Подробнее — разделrelease-v4вконце.

> Текущий STOP: сбор browser-bandwidth.oc6op_bb завершилсяexit1 наstabilization первогоWT-S. Qualification Mbdvg8v6 принята; остальные режимы/calibration/generator не выполнены. Причина и кандидат исправления — [stage4-bandwidth-failure.md](stage4-bandwidth-failure.md). Исходники не менялись, повтор не назначен.

> Актуально: qualification нового релиза3605994 принята (Mbdvg8v6, триpassed). BW_RUN browser-bandwidth.oc6op_bb подготовлен, сетевой сбор полосы ожидает пользовательского запуска. Calibration/generator ещёnot_run; этап4не завершён.

> Текущее состояние после согласованного исправления: новый релиз3605994, шесть новых ранних reports passed; qualification нового релиза ожидает пользовательского запуска. Исторический STOP ниже сохранён. Актуальные пути — в разделе «Новый релиз bounded-wait v3» в конце документа. Этап4не завершён.

# Этап 4: STOP на qualification UDP sender

Этап **не завершён**, передачи допуска этапу 5 нет. Первая проба qualification failed; согласно заранее заданному плану сбор остановлен, q2/q3 не запускались. Никаких повторных измерений, bandwidth, calibration, generator, A/A, monitoring, pilot/power, freeze или main здесь не выполнялось.

## Идентичность и предпроверка

HEAD `0fee7038dc2597f451f4e2c57381aa2d185dd5b4`. Все134 source hashes совпадают с inventory этапа3 до и после; исполняемые исходники не изменялись. build/release-state.json SHA256 `e98ab993450ff9501d3b32aa3b27b8f068fb7b042bfe4d8e476dfc85b574e149`, commit совпадает с HEAD. Короткий штатный admission.validate_gate повторно проверил каноническую целостность и результат шести прежних reports за4.177с. Измерения smoke/timer/build не повторялись.

ENV `results/verify/diagnostic/timer-timer.2ST8NYBU/context.json`, SHA256 `231ae4819874cf877f8e2234b4331171309906cb4c259b847c7ff8fc403039da`. TLS `/Users/dobrov/Desktop/Code/ITMO/benchmark/build/series-tls-stage2._n__udb0`, DER SHA256 `fc2a5f4d7bc0fce861baee9207c82ff86bf502fda419cf45c73e3559d1a56d18`, PEM SHA256 `ff69b4145dbd13f610506b4c5324ed515b5d58dd5556c81ff087cf845a0933b9`. notAfter2026-11-26T16:22:37Z; при старте13ноября оставалось почти13дней, резерв6+2дня соблюдался. Новый календарный допуск после паузы требует повторной проверки даты.

Фактические четыре image IDs совпали с этапом3; точные значения в preflight JSON. Docker2vCPU/4109484032bytes, image IDs и limits трёх сервисов из inspect совпали с ENV. preliminary=false в thresholds; поле preliminary=true в sender-quality — жёстко заданная описательная характеристика standalone UDP checker, исходный config не менялся. WS/WT-S/WT-D включены.

Питание AC100%, host118GiB/VM37G свободно; лабораторные подсети и lock были свободны. Незавершённых собственных измерительных проектов не было. Посторонний qdrant оставлен работать; его причинное влияние не установлено.

## Запуск и результат

Рабочий каталог `/Users/dobrov/Desktop/Code/ITMO/benchmark`.
Пользователь выполнил `caffeinate -ims sh results/verify/readiness/stage4/run-qualification.sh`; wrapper вызывает штатный `sh docker/sender-diagnostic.sh qualification` с постоянным SERIES_TLS_DIR. Оценка5–6минут+setup; фактический ранний STOP за124с:18:46:29–18:48:33UTC13ноября2026. Exit1.

Журналы `results/verify/readiness/stage4/qualification-execution.5wKWhtpC/{stdout.log,stderr.log,started,ended,exit,identity-before.sha256}`; основной внутренний журнал — `results/verify/diagnostic/sender-diagnostic.E243q4gg/commands.log`.

baseline-q1:10000посылок,256байт,100Гц; sender-quality failed из-за max lag57.23525мс>50мс, ID9151 (план91510мс, отправка91567.23525мс). Late42/10000=0.42%≤1%; максимум4пакета/полуоткрытое окно10мс≤4. Исходный timing checker повторно пересчитан и полностью совпал с сохранённым JSON. Средняя99.99805Гц не отменяет отказ max lag.

Все10000 reply IDs присутствуют, pcap ID/tag и directional denominators согласованы:10000в каждом направлении, drops0; каждый netem передал2980000байт/10000пакетов, очереди на границах пусты. Capture kernel drops0 в обоих логах. Сетка и монотонность валидны, seals всех53файлов проверены,13source snapshots до/после/текущие и сохранённые копии совпадают. Маршруты идут через router, permanent neighbors подтверждены до нагрузки, offloads отключены.

На endpoint по105resource samples (~104.5с), UDP counters от0до10000 покрывают всю нагрузку, UDP errors/OOM/throttle delta0 у дополнительных probe containers. Эти процессы не имеют cgroup CPU cap; это не доказательство запаса браузерного generator. Router105снимков сохранены. Причина паузы не установлена, macOS trace не назначалась новым условием допуска.

## Ограничения доказательств

Коллектор qualification не создаёт context.json: не требовали отсутствующий файл и не выдумывали ENV. Сверены фактические Docker info/inspect/host, mount TLS и внешняя неизменная ENV identity; полной повторной D3context snapshot нет. После раннего отказа штатно отсутствуют after-neighbors/final stats. Launcher identity-after отсутствует из-за set-e после exit1; отдельная последующая проверка подтвердила неизменность ENV/TLS/release и134источников, не дописывая исходный execution или sealed raw.

Pcap snaplen96 доказывает headers/ID/tag и prefix, но не все256байт payload. Код receive проверяет полный фактически вернувшийся payload; все10000reply получены. Отсутствие полной wire-копии явно раскрыто.

Разбор выполнил Codex по реальным файлам, независимая рецензия не заявляется. Новые derived/review/STOP расположены вне sealed raw; historical package этапа3 не менялся.

## Статусы и дальнейшая передача

Новый REPORT_MAP содержит только шесть применимых ссылок этапа3 (build/tls/path/timer/raw/analysis passed); calibration/generator/aa/monitoring остаются not_run. Qualification — отдельная failed диагностика, а не поддельный calibration report. Новый verify не запускался: требуемых новых passed нет. Ожидаемый финальный пакет8passed пока не получен; final допуска нет.

Очистка подтверждена: контейнеры и сети sender-diagnostic.E243q4gg отсутствуют, measurement lock снова получен и освобождён; qdrant не трогали. STOP сохранён отдельно. Повтор неизменённого плана запрещён; сначала нужен обоснованный разбор причины и новое заранее описанное решение. Конкретный дефект исходников сейчас не доказан; изменения и ослабление порогов не выполнялись.

## Точные артефакты

Все пути ниже относительно рабочего каталога.

|Путь|SHA256|
|---|---|
|`results/verify/readiness/stage4/qualification-E243q4gg-review.json`|`66fcb50b620ecb3c72448b244b1d4ad5a1b825a0e555b360d3385d8ba28f1a41`|
|`results/verify/readiness/stage4/STOP-qualification-E243q4gg.json`|`7ab76ef68b8c2ae6850d4a0b664c75111811ad78dd4ff988ece5fd5dabdd1847`|
|`results/verify/readiness/stage4/REPORT_MAP.json`|`f6df38e2725bdd5d569ccb4efbf0c8c70fab82d5bc032fb9dcfaebe6f564a56d`|
|`results/verify/readiness/stage4/preflight-20261113T184524Z.json`|`ff05319c01f737440ce2243af062e1600e8d29ecedd68c4480d9bef92718277f`|
|`results/verify/diagnostic/sender-diagnostic.E243q4gg/captured.json`|`0b0218ae9d1faf96867e521c50c17349a30c66e339dbd44f4d2bf6ed3d293ab4`|
|`results/verify/diagnostic/sender-diagnostic.E243q4gg/baseline-q1/sender-quality.json`|`5d73963a7f1ddcfe0144af41f648dd838a24d0369cfa7705ef8afab585393cc8`|
|`results/verify/diagnostic/sender-diagnostic.E243q4gg/baseline-q1/probe.json`|`7422431f4446338f6d16bb12700d51e8baff0587db44149f904285580b8101d8`|

## Дополнительное исследование после STOP

Выполнено по просьбе пользователя без изменения рабочего релиза: одна новая диагностическая baseline-проба с Linux trace иGCcallbacks (125.736с,exit0), плюс фиксированное30-секундное сравнение ожиданий без сети. Результаты и выбранный минимальный кандидат cap1мс: [stage4-sender-decision.md](stage4-sender-decision.md). Кандидат сохранён вне executable inventory и не применён; historical qualification failed и STOP остаются действующими. Диагностический timing passed не является qualification или новым gate. Рабочие134source hashes иENV/TLS неизменны. Новых допусков этапа4 не получено.

## Новый релиз bounded-wait v3

Применён выбранный cap1мс и регрессионная проверка. Коммит3605994e8359a70443621517e11dd2383a726f48, меняет только docker/calibration_probe.py и docker/calibration_probe_test.py в134-file inventory; план до измерений — docs/readiness/stage4-qualification-v3-plan.md. 7tests прошли за2.886с. Финальный drain/saturation/10000ID/100Гц/256bytes/2.5мс limiter и численные thresholds прежние.

Кешированный build выполнен. После него обнаружены новые manifest IDs; у server/browser/router Config/RootFS совпали с исходными; у analyzer отличается только __pycache__/sender_quality.cpython-315.pyc. Сравнение всех non-cache файлов /analysis подтвердило идентичность. Восстановлены прежние точные imageIDs, источник sender монтируется с host. Промежуточные новые образы не использовались в измерениях и не объявлены прежним ENV. Полные сравнения/логи сохранены в release-v3; прежний архив применим к восстановленным образам и проверен по байтам при новой публикации build. Нового архива нет.

Повтор smoke:results/verify/path/wswt-smoke.vMSax84H,16.278с,exit0. Timer:results/verify/diagnostic/timer-timer.Bqgsgj12,67.385с,exit0. Execution:results/verify/readiness/stage4/release-v3/early-execution.uw80ebe4/. Новый фактический context побайтно совпал с исходным ENV; для единой path/SHA identity новый timer input/report опубликован в release-v3/timer-original-env, без изменения raw и автоматически опубликованного timer report.

Все новые reports имеют актуальный source inventory и исходный ENV path/SHA. Typed primary подготовлен новым docs/readiness/stage4-primary-v3.py: новое реальное smoke/raw плюс явно раскрытое переиспользование старых offline/client/null проверок после установления точной source delta (их исходники/протокол/config/зависимости неизменны). Исторические отчёты не редактировались и не перепривязывались. Publication/execution logs содержат argv,exit и длительности. Первоначальный запрос запуска цикла публикаций был отклонён автоматической проверкой из-за суммы пяти90-секундных пределов; пересмотренный запуск с единым общим120-секундным пределом принят и выполнен успешно.

REPORT_MAP нового релиза:results/verify/readiness/stage4/release-v3/REPORT_MAP.json. Штатный verify-prequalification.json:build/tls/path/timer/raw/analysis passed, calibration/generator/aa/monitoring not_run; expectedexit2,finalfalse. Это не финальный результат этапа4. Предыдущий REPORT_MAP этапа3 и исходный pre-change stage4 map сохранены.

Перед следующим сбором подтверждены AC100%,118GiB host free, прежние2vCPU/4109484032bytes, TLS DERfc2a5f4d7bc0fce861baee9207c82ff86bf502fda419cf45c73e3559d1a56d18 и остаток>8суток, свободные подсети и measurement lock, отсутствие измерительных контейнеров. Qdrant не трогали.

Следующая пользовательская команда из корня: caffeinate -ims sh results/verify/readiness/stage4/release-v3/run-qualification.sh. Резерв5–6минут+setup. Один новый фиксированный сбор3×10000; перваяfailed/inconclusive останавливает. Уникальные логи/stdout/stderr/exit/started/ended/identity-before-after/plan будут в release-v3/qualification-execution.XXXXXXXX, raw — results/verify/diagnostic/sender-diagnostic.XXXXXXXX. Шесть gate identities и все134source hashes проверены. Команда ещё не запущена. Остальные этапы4и5+не запускались.

Точные SHA всех шести reports, inventory, REPORT_MAP, verify и launcher:results/verify/readiness/stage4/release-v3/prequalification-SHA256SUMS. release-state SHA и фактическая дата проверки:release-v3/prequalification-state.json. После результата qualification продолжить по исходному порядку только при принятом сборе; не выполнять неизменённый повтор до удобногоpassed.

## Принятая qualification Mbdvg8v6 и подготовка bandwidth

Пользователь запустил release-v3/run-qualification.sh. Execution results/verify/readiness/stage4/release-v3/qualification-execution.QnNt51TQ,13ноября19:43:52–19:49:34UTC,342с,exit0. Raw results/verify/diagnostic/sender-diagnostic.Mbdvg8v6. Все3baseline sender-quality passed: late0.19/0.22/0.07%,maxlag32.677493/27.954759/20.552996мс,peak4/4/3. По10000полных ID/ответов, tag/IP/UDP length/pcap Ethernet MAC сверены с permanent neighbors, full payload подтверждён receive. В обоих направлениях каждой пробы delta10000packets/2980000bytes/drop0, capture kernel drops0, ARP0. Нет socket errors/throttle/OOM. По105sampler snapshots endpoint/router на пробу; начальные/конечные cumulative UDP/qdisc counters охватывают baseline→baseline+10000. Абсолютный sender start этим коллектором не сохраняется — точное временное покрытие не выдумывается. Endpoint/router neighbor snapshots до/после равны. Все79sealed files,13source snapshot entries и134current sources проверены; ENV/TLS/release identity до/после/current совпадают. Исторический failed E243q4gg сохраняется, новый план разрешён после конкретного исправления, непрерывного подбора повторов не было.

Подробный review и ограничения:release-v3/qualification-Mbdvg8v6-review.json. Первоначальные локальные assertions разбора исправлены: neighbor MAC direction и cumulative UDP/qdisc counters сохраняются между пробами (а не сбрасываются на0). Это ошибки подготовительного проверяющего кода, raw/collector не менялись, сетевого повтора не было.

Очистка qualification подтверждена: измерительных контейнеров/сетей нет;measurement lock получен/освобождён;AC100%,host118GiBfree;qdrant оставлен работающим.

Новый точныйBW_RUN:results/verify/diagnostic/browser-bandwidth.oc6op_bb. Schedule создан штатным schedule.py diagnostic --blocks1 --sessions1 --baseline --datagrams --generator-hz20. Порядок0=WT-S,1=WT-D,2=WS;baseline loss0,256байт,200warmup/1200measurement. Schedule SHA256148ce62cb6db3d0360abc95c96cf2f83c87aebd621b982a47198acae6baf2f2d. Статусprepared_not_run; сеть ещё не запускалась. Планrelease-v3/bandwidth-plan.json связывает принятый qualification review и исходныйENV.

Следующая пользовательская команда из корня:caffeinate -ims sh results/verify/readiness/stage4/release-v3/run-browser-bandwidth.sh. Оценка5–10минут+setup, один фиксированный сборmeasure0/1/2 в указанном порядке. Unique execution stdout/stderr/exit/identity/start/end создаются вrelease-v3/bandwidth-execution.XXXXXXXX. Wrapper проверяетHEAD/134sources/images, исходныйcontext после каждого режима и запрещает повтор уже начатогоBW_RUN. Ошибка сохраняетSTOP/partial/quarantine; без автоматического повтора. Raw ожидаются вBW_RUN/raw/b0-a0-m0,m1,m2 соштатными slots/warmup/resources/backlog,qdisc-before/stable,sources,manifest/SHA256SUMS; context/schedule/ledger остаются по исходным путям.

Это только диагностика полосы. Формальныйgenerator gate и численная доляполосы ещёnot_run: capacity появится после одного полного calibration raw, затем штатныйbrowser_bandwidth.py проверит три режима/два направления иfraction<0.1. Расчёт по частоте×payload не используется. Следующий сборcalibration не выдаётся до проверки браузерных raw. ТочныеSHA review/plan/launcher:release-v3/qualification-bandwidth-SHA256SUMS.

## Отказ browser bandwidth oc6op_bb

Execution bandwidth-execution.AmGbbSCv,131с,exit1. WT-S200/1200slots всеsent/echo, но стабилизацияrouterCPU не принята: baselineceil1%,lastidleceil6%. Вmeasure.sh дополнительныйbacklogobserver запускается послеbaseline, поэтому условияbaseline/idle различаются. ТочныйCPUawkcheck воспроизведён offline. Остальные попытки и полная стоимость observer не атрибутируются без данных. Подробныйreview/ограничения/новыеSHA и отдельныйнеприменённыйкандидат — stage4-bandwidth-failure.md и release-v3/bandwidth-oc6op_bb-failure-review.json. STOP/quarantine сохранены; полныхraw/manifest/stabilization/resource-window/backlog нет. Cleanup/lock проверены,ENV/source/image/TLS неизменны. Qualificationpassed сохранена,calibration/generatornot_run. Новых сетевых команд не назначено.

## Release-v4: исправление baseline и новый сбор полосы

Коммит494e1a99bf9c92bd2a26af7dce6a8752af23d448. Относительноv3 меняются толькоdocker/measure.sh иdocker/browser_bandwidth_test.py: backlog observer запускается передresource samplers иbaseline. Все пороги/нагрузка/очереди/срок30с прежние. Новыйпланзаранее:docs/readiness/stage4-bandwidth-v4-plan.md. Регрессионныйshellmock воспроизвёл old-orderfailure только приbacklogenabled; послеисправления11testsOK,2.843с. Первыйзапусксамогоmock завершилсяошибкойнеинициализированногоrun_id, окружениетестаисправлено; обаотрицательныхжурналасохранены. Новоесетевоедоказательствоисправленияещёнет.

Образы/ресурсы/ENV/TLS сохраненыточно. Новаясборканенужна:обаизменённыхфайлаhost-mounted, imagebuildinputs прежние. Release-stateобновлёнштатно,134-sourceinventoryновый. QualificationMbdvg8v6непереписывалась:qualification-applicability.json сохраняетoldmeasurementcommit3605994, current494e1a9 иtwo-filedelta,проверяетвсе13captureddependencies и79sealedfiles, исходныеimages/UDPsender/configs/ENV/TLS. Qualificationcollectormeasure.shневызывает. Переносневыдаётсязанеизменность134oldhashes; отдельныйтехническийreviewзаписанCodex, независимаярецензиянезаявлена.

Повторёнкороткийsmoke results/verify/path/wswt-smoke.82a9x9l5:15.527с,exit0. Timer results/verify/diagnostic/timer-timer.kT54gbDY:73.235с,exit0. Execution release-v4/early-execution.r_7e7qpb. ФактическийcontextпобайтноравенисходномуENV231ae481...039da. НовыйtimerreportсединойисходнойENVpathidentityвrelease-v4/timer-original-env. Пятьновыхprimary/reportsоформленыdocs/readiness/stage4-primary-v4.py,неизменённыеanalysis/clientfixtures явно переиспользованыпослепроверкиsource delta;старыеraw/reportнеправились. Publication/execution.csvнеиспользуется:точныеargv/seconds/exitвrelease-v4/publication-execution.json.

НовыйREPORT_MAP:release-v4/REPORT_MAP.json. Штатныйverify-pre-bandwidth.json:build/tls/path/timer/raw/analysispassed,calibration/generator/aa/monitoringnot_run,finalfalse,exit2. Всеоперациипубликацииимелиобщий120-секундныйпредел. Доcalibrationдорогихнаучныхрасчётовнет. Очистка/lockсновапроверены,AC100%,host118GiBfree,qdrantнетронут. TLSleaf/pinпрежние,остаток>8суток.

НовыйBW_RUN results/verify/diagnostic/browser-bandwidth-v4.9r51339s. Scheduleштатныйdiagnostic--baseline--datagrams--generator-hz20,1block/1session;порядок0WS,1WT-D,2WT-S.256байт,200warmup/1200measurement. ScheduleSHA c0e30b877be258a4c2541159888649d0852005b605b858319a9d93e89c30ba3f. Сборprepared_not_run;предыдущийoc6op_bbостаётсяSTOP/quarantine.

Следующаяпользовательскаякомандаизкорня:caffeinate -ims sh results/verify/readiness/stage4/release-v4/run-browser-bandwidth.sh. Резерв5–10минут+setup. Uniqueexecutionrelease-v4/bandwidth-execution.XXXXXXXX:stdout/stderr,exit,start/end,identitybefore/after. RawожидаетсявновомBW_RUN/raw/b0-a0-m0,m1,m2,context/schedule/ledgerпоточнымпутям. WrapperфиксируетновыйHEAD/sourceinventory/qualificationapplicability,проверяетcontextпослекаждогорежима,останавливаетсяприпервойошибке,повторзапрещён. Всевходы/отчёты/план/launcherSHAвrelease-v4/SHA256SUMS. Доразбораполныхrawкcalibrationнепереходить.

## Принятые браузерные raw и подготовка полной calibration

Пользовательскийexecution release-v4/bandwidth-execution.i3D0OccS,13ноября20:09:54–20:15:15UTC,321с,exit0. ТочныйBW_RUN results/verify/diagnostic/browser-bandwidth-v4.9r51339s,порядокWS/WT-D/WT-S. Все3rawпрошлиdiagnostic_raw/validate_raw,ledgercomplete,queueпустая,STOPнет,source134/HEAD494e1a9/ENV/TLSidentityсовпали. Каждыйрежимсодержит200warmup/1200measurement,всепосылки/полныеecho,стабилизацияподтверждена. Штатныйload_ratesпроверилположительныеbyte/packetsдельты,drop0,неизменныеqdiscoptions/handleиочереди0награницах. generator_runиспользовантолькодляпроверкиresource/backlogcoverageиописательныхметрик,безформальногоgeneratorрешения.

ByteдельтыиR_upperМбит/с(forward/reverse):WS601698/514796,0.0802264/0.06863947;WT-D575105/628471,0.07668067/0.08379613;WT-S569703/488313,0.0759604/0.0651084. Этоизмеренныйвесьsetup/warmup/measurement/draintraffic,делённыйна60с,не20Гц×payload. Долюполосынепубликуемдополучениячетырёхsaturationcapacityоконновойcalibration. Capacity/fractionещёnot_run.

Описательныйp99lagWS5.3мс,WT-D5.8мс,WT-S5.3мс,miss0. Числапревышаютбудущий20Гцgeneratorlagпорог5мс;этоотдельныйбудущийформальныйgate,оннеобъявленpassed,порогнеизменялся. ПолнотаrawпозволяетпродолжитькUDPcalibrationпосогласованномупорядку. Нельзяподменитьбудущийgeneratorэтимсбором.

Полныйreview:release-v4/browser-bandwidth-v4-raw-review.json,содержитссылкиSHAкаждогоrawфайла,actualaccounting/coverageиограничения. Независимыйисполнительнезаявлен. Cleanup/lockподтверждены,AC100%,host118GiBfree,прежние2vCPU/4109484032bytes,qdrantоставленработать. TLS/pinнеизменны,остаток>8суток.

Одинполныйcalibrationсборподготовленштатнымdocker/calibration.sh. Фиксированныйпланзаранеесохранёнrelease-v4/calibration-fixed-plan.json;самколлекторсоздаётcollection-plan.jsonвновомCAL_RUNпослеполученияlockиДОcomposeup.14echoимён+4saturationокна,forwardseeds20261110+2i/reverse20261111+2i,i0..17;методcircular-block-medians-v1,блоки100/200/500,20000bootstrapреплик,исходныепоправки/пороги. Планнеадаптируетсяпорезультатам.

Следующаяединственнаяпользовательскаякомандаизкорня:caffeinate -ims python3 results/verify/readiness/stage4/release-v4/run-calibration.py. Ожидание30–35минут,выходнойобъёмоколо350MiB;обёртканевыполняетнаучныйbootstrap/package/acceptance. Uniqueexecutionrelease-v4/calibration-execution.XXXXXXXXсstdout/stderr/exit/start/end/identity,копиейcollector/ожидаемогоплана,точнымargvипутёмCAL_RUN. СамCAL_RUNвыбираетсяштатнымскриптомresults/verify/diagnostic/calibration.XXXXXXXX;обёрткафиксируетновыепутидажеприошибке. ПриошибкеSTOPсохраняетсявоexternalexecution,raw/sealsнеправятся. Успешныйshellозначаеттолькозавершениесбора,непринятуюcalibration. Сборещёнезапущен.

Входы/BWreview/план/launcherSHA:release-v4/bandwidth-calibration-SHA256SUMS. Послерезультатапроверитьполноту14+4,seals,source/ENV,ID/tag/pcap/dropdenominatorsиsaturationокна. Затемштатныйbrowser_bandwidth.py,содержательныйprocessreview,packageиcalibrationreport;всякийпотенциально>5минутрасчёт/глубокийverifyзапускаетпользователь. Никакихcalibration/generator/AА/monitoring/pilot/power/freeze/mainещёнебыло.

## STOP полной calibration.lShojabe

Executionrelease-v4/calibration-execution.562299sa,20:20:42.956701–20:50:05.404317UTC13ноября2026,1762.448с(29мин22с),exit0. ТочныйCAL_RUNresults/verify/diagnostic/calibration.lShojabe. Все14echo+4saturationприсутствуют,146sealedfiles/46112677bytesпроверены;plan/source134/ENV/TLS/releaseHEAD494e1a9совпадаютдо/после/current. Сохраняетсяфиксированныйcircular-block-medians-v1план,никакихдобавочныхподсерий.

12из14senderpassed.Дваfailedпоmaxlag: r20p0-after129.224986мс(ID5928),r20p1-after53.692504мс(ID891),порог50мс. Late0.43%/0.18%,burst4/4сами проходят,но неотменяютmaxlagfailure. Всеsent10000ID/100Гц/256bytesпроверены,replyID/RTT/tag/pcapсогласованы;zero-lossподсерииполучили10000ответов. Во всех14directions()подтвержденоточноесоответствиеUDPsurvivors/netemdrops,seed/readback/limit/rate/options/handleиqueues0награницах,capturekernel drops0. Reverse denominatorsфактическидоставленныеforwardID. Все8формальныхненулевыхdirectionalbefore/afterClopperPearson99.875%интерваловвключают.01;latencyr20p1forward138/10000выходитзаэтуописательнуюграницу,ноlatencyнеподменяетпредусмотренныеlossbefore/afterподсерии.

Штатнаяprocess_diagnosticsflaggedbaseline-beforeRTTrho500=.037819,rho1000=.051714 иr20p0-latencyrho1000=.044615. Fittedmedian5s-chunkdrift−.004188/.003153мс,но малыйдрейфнеотменяетlonglagflags. Ихналичиепоисходномуконтрактудаётinconclusiveдляпроцессноговыводадажеприsenderpassed. ОтсутствиеGC/CPU/schedulertraceвэтомcalibrationсборенепозволяетприписать129мспаузуточномумеханизму.ОбязательныйmacOStraceнепредлагается.

Saturation61-секундныеокнапокрытыload,directionaloffered>=forwarded,stablequeue0. Скорости:loss0forward10.0009699/reverse9.9994940;loss1%forward10.0011221/reverse10.0012849Мбит/с,все9–11. Штатныйbrowser_bandwidth.pyBW_RUN+CAL_RUNвернулexit0/statuspassed,maxfraction=.008380037347=0.8380037%<10%;всешестьmode/directionотношенийоснованынаизмеренныхbytes.Весьрезультатвrelease-v4/browser-bandwidth-lShojabe.json,rawнеправились.

Reviewиограничения:release-v4/calibration-lShojabe-raw-review.json;STOPсохранёнВОвнешнемrelease-v4/STOP-calibration-lShojabe.json,неinside sealedraw. Полныйcircularbootstrap(6×3×20000репликпо10000плановыхслотов)не запускался;оценкавозможновыше5минут,прибудущемнеобходимомформальномрасчётезапускаетпользователь. ЭтоSTOPпообязательнымпервичнымусловиям,неупрощённаяверсиярасчёта;официальныйcalibrationreportнеопубликованиpassedнезаявлен.Никакихавтоматическихtrueдляпредпосылок,добора/пересбора/сменыпорогов/блоковнет. Генераторидальнейшиеэтапынезапускались. ПоследнийREPORT_MAPпо-прежнемусодержиттолько6раннихpassed;обязательных2новыхpassedнет,этап4не завершён.

Cleanupконтейнеров/сетейcalibrationпроверен,measurementlockполучен/освобождён,qdrantнетронут. ИсторическаяqualificationMbdvg8v6остаётсяеёсобственнымpassedнаблюдением,нополнаяcalibrationпоказывает,чтоононегарантируетнадёжностина30минут. ТочныеSHAновыхreview/BW/STOP/plan/seal:release-v4/calibration-lShojabe-SHA256SUMS. Новыхпользовательскихкомандневыдаётсядодокументированногорешенияопричинахиновогофиксированногоплана.

## Глубокое исследование и применённый poll0

Актуальныйчитабельныйотчёт:stage4-deep-investigation.md. КодUDPprobeMAX_ECHO_WAIT_NS=0применёнв12ba5e5;testmockпродвигаетclockприtimeout0,11testsOK7.352с. Исследованиевresults/verify/readiness/stage4/deep-review-v1/,точныевходы/результаты/планы/execution/stdout/stderr/exit/sealsсохранены. Четырефиксированныхкороткихопыта223.055/223.301/214.369/225.736с,всесexit0;никакогоновогополногосбора/bootstrap. ПользовательподтвердилсвободнуюмашинупередпоследнимaffinityABBA.

Poll0baselineABBAподтвердилp99lag~0.86→0.017мсиуменьшениетрёхфазовыхметрикприCPU~95.5%ядра. Вновыхполных10000-IDshortprofilesmaxlag9.79/3.21мс,обаsenderpassed. r20p0processclear,r80p1processflaggedиз-за8-секундногоростаforwardrouter-spanпримернона3мс;сenderвэпизодеонлайн,clientresidualнерастёт. ПоследующийaffinityABBAвсе4processclear,включаяконтроли,поэтомуpinningнеприменён/необъявленрешением. Immediatecaptureтакженеулучшилпериодичностьиотвергнут. ДанныеoldlShojabefailedнепереписывались.

Причинаобщихисторических129мспаузнеточноустановлена:двунаправленныйingressquietиdelayedalready-sentechoнеобъясняютсятолькоPythonGC. Конкретныеhost/guest/netem/serverсоставляющиетребуютсобытийвмоментперехода;обязательныйmacOStraceнеставится. Нельзяскрытьнеуспешныйr80p1илиперенестидопускипоудобнымпоследующимуспехам. Текущиегейтыисторические,подновыеsourcehashesнеперепривязывались. Длявозобновленияприёмкипонадобитсяновыйприменимыйsource-boundпакет;получасовойпересборпокакакготовоеисправлениенепредлагается.
