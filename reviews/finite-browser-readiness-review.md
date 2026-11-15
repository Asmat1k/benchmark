# Независимый review конечного плана и exact-source replay

15 ноября 2026. Внутренний reviewer `/root/design`. Прочитаны docs/readiness/finite-browser-study-v1.md, browser-historical-replay.py и первый draft /tmp/finite-src/limited_readiness.py и acceptance.py. Во время новой timer сети reviewer не запускал Docker, тесты или тяжёлый анализ; исходники workspace не изменял. Это review метода/кода, не подтверждение будущих измерений.

## План

Вариант24A/A+24monitoring+60pilot+60repeat=168runs доmain соответствует автономному выбору кратчайшего согласованного пути. При120–180с/run5ч36–8ч24; реальные generator/pilot timings обязательны для обновления прогноза относительно абсолютного срока15ноября12:15МСК. Фиксированный main20/profile=240runs остаётся, завершениеmain не обещается в12ч. Отказ от доказательства20-парной эквивалентности раскрыт: однопарные controls являются smoke с inconclusive научным статусом. WT-D описательный, sign/Holm4 и Q/S/U сохранены. Плохие результаты не исключаются, все прежние partial/failed остаются.

Новый план фиксирует repeat tolerances2мс/1п.п. заранее, вместо прежнего AA p95 алгоритма. Это методически допустимое операционное правило, но соответствующая finite ветка freeze обязана иметь честное новое название алгоритма; нельзя записывать прежний `paired side2-side1; linear p95 absolute shifts`, если p95 не вычисляется. Strict ветку сохранять. При малом пилоте широкий/null интервал и inconclusive repeat возможны; план не гарантирует ни80%power, ни будущий usefulgain.

## Historical replay

Root script архивирует конкретный commit и запускает без сети архивный analyzer source view; results/build доступны по прежним путям, полный host workspace также смонтирован по точному absolute path для243исторических receipt-ссылок. Перед validate_gate требует точного равенства archival sources и report.source_hashes. Поэтому replay не заменяет старые hashes текущими и сохраняет научный статус. Receipt связывает report/ENV/source/status и stdout/stderr hashes; это приемлемое проверяемое внутреннее свидетельство повторного offline расчёта, а не новое сетевое measurement.

Operational замечание: timeout900с или ошибка gitarchive/tar сейчас выбрасывает исключение до записи receipt/exit/ended. Успешный replay этим не обесценивается, но при отказе требуется finally/catch с завершённым failure journal. Raw/report не изменять; failed replay не объявлять passed и не подменять stdout. Script должен запускаться из workspace root, что использует его Path.cwd и относительные report ссылки.

## Предварительный draft limited readiness

Положительно: сохраняется10реальных rows со старыми статусами, policy фиксирует дизайн, historical exactsource receipt проверяется вместе с canonical evidence graph, runtime/profiles/thresholds/план сравниваются предметно. Generator требует полный набор6mode×frequency; smoke требует12cells по1паре и inconclusive. Это отдельная readiness completion семантика, а не переприсвоениеpassed старой приёмке. SOURCE_CHANGES содержит точные пути, не wildcard каталогов.

На первом прочитанном draft admission/experiments ещё совпадали со старым workspace; потому готовый controller/prepare/freeze/main этим review пока не удостоверены. Integration сообщил, что новые ветки готовятся отдельно вне frozen source. Reviewer запросил убрать требование эмпирической independence из n1smoke и сохранить только проверяемую fresh-process/order audit и настоящее экспертное рассмотрение; автоматическое присваиваниеtrue не подтверждает ревью. Legacy equivalence остаётся прежним.

Окончательный вердикт требует review завершённой draft цепочки: verify→prepare→accepted_schedule→controllerinitial/restart→coverage→freeze→reproduction. Необходимо сохранить recalculateFalse fastpath между прогонами и все обязательные raw invariants. Пока разрешён review и подготовка, не декларация готовностиmain.

## Review обновлённой полной draft цепочки

Повторно прочитаны изменения admission/experiments/acceptance в /tmp/finite-src. Verify распознаёт exactversion и оставляет strictветку. Prepare требует control-smoke flag именно дляAA/monitoring и фиксированные1/5/20blocks. Accepted_schedule воспроизводит тот же randomized schedule, finite запрещает расширение/replacement; обычный progress меняетledger, неschedule, поэтому equalityсoriginal допустимо. Controller initial/restart проходит черезadmit→verify, основнаяrawcompletion/attribution/source/ENVцепочка сохраняется.

Control evaluator теперь требует hashbound unit_review и проверяет freshprocess/seed/on-off соответствие без недоказанного n1independence. Reviewfile должен быть настоящим предметным рассмотрением выполненных данных, анеplaceholder. Reportstatus сохраняется inconclusive; CIневыдумывается. Coverage использует существующую формуgroups и проверяетвсе12cells.

Freezefinite требуетmain20 и новый честный aa_shift_algorithm=`fixed pre-data 2 ms and 1 pp; smoke controls descriptive`; остаётся обязательная связкаpilot/power,leaf/source/ENV/schedule/inventories. Для выполнения необходим schemaenumpatch, допускающийровностаруюиновуюстрокувместопрежнегоconst. Само добавлениеenumненарушаетstrictветку: runtimeпроверкавыбираетстрокувсоответствиисверсификацией.

Reproduction logic непереписана: новый реальный pilotпослеfreeze,другойseriesid,повтор5/profile,actualexecutorиfullrawcomparison. Новыйreadinessнеснимаетнеобходимостьэтогоэтапа. Успешнаяподготовкаcontrol-smokeневыдаётготовностьmainзаранее.

Operationalзамечание: bound_report передаёт recalculateFalse дляcurrentreports,ноhistorical_reportкаждыйразстроитcanonicalgraphисверяетintegrity,включая≈108MiBcalibration. Это не scientificrecalculation инепричинаослаблятьцелостность,но двойнойhashприкаждомRPCможетувеличитьoverhead. При необходимостикэшироватьтолькодоказаннуюinitialcanonicalgraphвпамятиконтроллера,подобносуществующему_APPROVED_GATES,сcheck_integrityнаfastpath;неподменятьэтодовереннымфайловымфлагом. Фактическийruntimeдолженвключатьэтустоимость.

Поreadreviewпослепримененияschemaenumиобязательноготестовогопакетадополнительныхблокирующихошибокпредложеннойминимальнойцепочкиневыявлено. Это условныйreviewdraft: workspaceещёsourcefrozenнасети,реальноеприменение/cleancommit/тесты/новаяактуальнаяENVпроверяютсяпослеgenerator. Reviewerтестыво времясетинезапускал.
