# Независимый итоговый review quiet-selector

14 ноября 2026. Внутренний независимый review сабагентом Codex. Повторно прочитаны исправленные sampler, measure, resource schema/validator, stabilization_cpu и соответствующие tests. Production не изменял; сеть и дополнительные тесты не запускал.

## Исправления

- Fixture начинает sample_index с0; выбранные IDs1/2 согласованы с непрерывностью.
- quiet_summary проверяет каждую строку текущей JSONschema, общую run identity, resource coverage/continuity/OOM, наличие корректных brackets. Отрицательный,NaN,boolean CPU и mixedrun отказывают; dedicated regressions присутствуют.
- Baseline/idle comparison проверяет совпадение run_id. Выбираются все полностью contained rows, минимум2, окно3s и прежнее maxceilcomparison фиксированы.
- Marker/read/sleep в quiet_cpu имеют явные return при отказе. Per-selector stderr/exit добавлены. Уникальные streams/markers/queue snapshots сохраняются для каждой попытки.
- Actual sampler regression запускает настоящий shell sampler без сети на4s, проверяет≥2rows, schema и соответствие обоих bracket bounds.

## Независимо проверенные результаты

`results/verify/readiness/stage4/practical-v1/quiet-fix-tests/exit` =0; сохранённый stderr заканчивается **37tests за48.529s, OK**.

`results/verify/readiness/stage4/practical-v1/quiet-fix-tests/final/exit` =0; сохранённый stderr заканчивается **21tests за5.662s, OK**. Финальный набор включает новый selector с actualsampler/invalidCPU, browserbandwidth и measurement regressions. Эти результаты не являются полным проектным suite и не доказывают успех будущего сетевого timer/generator.

## Последняя локальная shell поправка

На момент чтения оставалось `analyze ...; quiet_exit=$?`: при вызове baseline без `||` глобальный set-e способен выйти до записи selector.exit. Предложенная замена `quiet_exit=0; analyze ... || quiet_exit=$?; printf ...; return ...` корректно сохраняет реальный exit и работает при обоих контекстах вызова. Она не меняет численный selector, sampler или тестированные Python-ветки. До фиксации исходников эту замену нужно внести и проверить shell syntax/прочитать итоговый фрагмент; математический/ресурсный бюджет не меняется.

Остаточные ограничения из designreview сохраняются: CPU% использует прежний elapsed denominator; fullycontained интервалы не покрывают непрерывно все края3s; внешняя marker-команда может влиять на scheduling общей VM. Эти ограничения раскрыты в summary и не дают права удалять failed или повышать CPU допуск. После указанной shell поправки новых блокирующих замечаний по повторно проверенному коду нет; следующий эмпирический опыт должен оставаться заранее заданным и source-bound.

Повторное чтение после записи: последняя shell поправка уже внесена ровно в описанном виде. Короткая `sh -n docker/measure.sh docker/sample.sh` завершилась exit0. Замечание об exitfile снято; блокирующих замечаний не осталось.
