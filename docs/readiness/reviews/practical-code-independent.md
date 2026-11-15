# Независимый разбор реализации observed-profile-check-v1

14 ноября 2026. Внутренний независимый code review сабагентом Codex; это не внешний рецензент и не приёмка новых измерений. Проверены текущий diff, новый модуль и тесты; сетевых/долгих команд не выполнялось.

## Найденные проблемы до исправлений

1. **Публикация failed при пустом окне:** `observed_intervals` создаёт `[-inf, inf]`, если хотя бы одно500-слотное окно полностью missing. Итоговая запись через `raw.write(... allow_nan=False)` завершается ошибкой вместо JSON с failed и явными null bounds. Нужен JSON-safe результат и regression на пустое окно lossy latency (остальные окна непустые). Ошибка не даёт ложный passed, но теряет предусмотренный машинный отчёт отказа.
2. **Неожиданный объём targeted tests:** импорт `AcceptanceTests` напрямую в новый тестовый модуль приводит к сбору всех методов этого TestCase при `unittest test_calibration_observed`; это видно в `/tmp/practical-tests.stderr`. Следует импортировать модуль и использовать `test_acceptance.AcceptanceTests`.
3. **Падающая проверка немутируемости:** существующая `calibration` добавляет `mbit_s` в записи входного `saturation`. Новый тест `data == before` поэтому не может пройти. Проверять неизменность raw/echo/egress или минимально копировать saturation при расчёте.
4. **Legacy contract check:** условие `configured['method'] == 'observed-profile-check-v1' or ...` принимает повреждённые observed parameters при прямом вызове legacy branch. Лучше проверять полное равенство одному из двух известных contracts либо отделить historical constant contract от current config. Тест должен отлавливать изменённый численный параметр.

## Что проверено по коду

- Ветка по method сохраняет legacy sender по умолчанию и старые интервалы. Новая ветка не использует ACF как gate, но публикует process diagnostics; отдельный `observed_period_reviewed is True` обязателен.
- Empirical loss check `entered <= 200*drops <= 3*entered` корректно реализует включительные .5%–1.5% без float tolerance. Loss0 требует0drops.
- Медианы строятся по ID-плану20×500, только по реально вернувшимся RTT. Две baseline-envelope используют min/max всех окон; RTT не усечены и sender lag не вычитается.
- Proxy перебирает пять фаз×801окон и сохраняет все counts. lag≥50ms и получение строго после planned100ms соответствуют согласованным границам. На loss1 full joint pass не заявляется; missing IDs и число missing сохраняются. Поле unknown_reply является остаточной неопределённостью union при отсутствии уже известного lag-нарушения, а не всеми missing RTT; полные missing доступны отдельно.
- late≤1%, burst≤4/10ms сохранены; minspacing2.5ms добавлен только observed и согласован с collector limiter с допуском округления. Большие RTT остаются в полных метриках и tail_records. Отдельный максимум lag публикуется.
- P99 body/tail не меняет gate и не удаляет записи. Ties остаются в body.
- Collection packager получает method из preregistered plan, сохраняя source/ENV/seal/pcap/qdisc проверки. Независимый raw review capture logs остаётся необходимым: package не заменяет предметную проверку всех raw свидетельств.

## Недостающие граничные regressions на момент обзора

Помимо устранения описанных ошибок нужны: exact loss endpoints и выход за них с согласованными ID denominators/survivors, пустое500-окно с JSON-safe failed, phase budget12/13, нарушения late/burst/minspacing, schema rejection изменённого practical contract, сохранение исторической ветки. Новые подтверждающие измерения пока не запускались; historical failed этим review не переоценены.

## Повторная проверка исправлений

Проверен исправленный diff до завершения `implementation/regression` без изменения source/tests во время тестов. Все четыре замечания устранены: пустые окна дают null bounds и failed с валидным JSON; импортируется тестовый модуль; неизменность проверяется по raw echo/egress; обе версии config сопоставляются полностью. Добавлена metadata-проверка всех14UDPпроб (10000/256/100), exact-loss helper и граничные проверки .5%/1.5%, loss0drops, malformed IDs/denominators, late, burst, minspacing, повторных deadline, JSON emptywindow. Контрпример500мс отвергается;499мс может пройти, что соответствует явно ограниченному смыслу бюджета доли.

Независимо прочитаны сохранённые результаты: `results/verify/readiness/stage4/practical-v1/implementation/regression.exit` =0; `regression.stderr.log`: **30tests за50.060с, OK**. В наборе присутствуют новый observed method, legacy sender/block/dependence/threshold contracts, collector directional/rate/affinity/neighbors tests. Это не полный проектный suite и не подтверждающий сетевой сбор. Новых блокирующих замечаний по повторно проверенному diff не найдено. Основной сравнительный Q/S/U/парный анализ этим diff не изменены; пригодность новой калибровки на новых данных ещё должна быть проверена отдельным заранее фиксированным сбором и независимым raw/results review.
