# Подготовка внутреннего воспроизведения finite-browser-study-v1

15 ноября 2026. Подготовил отдельный внутренний агент `/root/reproduction`, отличный от автора `/root`. Это чтение контракта и рецепт будущего выполнения, не результат воспроизведения. Во время действующего generator не запускались сеть, Docker, hashing архивов, тесты или изменения исполняемых исходников. Изучены AGENTS.md, передача, конечный план, collection/admission/experiments, archive/build/analysis scripts и соответствующие tests.

## Что минимально необходимо

Нужен один реальный `gate=reproduction` с шестью обязательными предметными проверками. Каждый `actual` означает конкретно выполненное действие, подтверждённое typed trace и логами. Протокол сравнения repeat сохраняет собственный фактический passed/failed/inconclusive, независимо от факта рассмотрения. Нельзя назвать drift-review не выполненным только потому, что обнаружен дрейф, либо назвать сравнение passed только потому, что review проведён.

| PRIMARY_ID | Конкретное доказательство | Пока статус |
|---|---|---|
| archive-hashes | SHA256/sidecar текущего source archive, точное сопоставление его executable members с frozen source inventory; SHA256/sidecar существующего image archive и четыре фактических image IDs | not_run |
| offline-build | Реальная offline проверка hash-locked wheelhouse/install и импорт/compile текущих host-mounted analysis modules; явное применение прежних image-build proofs только для неизменённых client/server/runner/runtime dependencies | not_run |
| offline-analysis | Offline known-answer статистические тесты текущего release и повторный расчёт фактического pilot из sealed raw; сохранить analysis JSON/CSV, полную выборку и null | not_run |
| main-negative-guards | Реальные целевые CLI/controller regressions отказа forged/unadmitted/stale/missing-reproduction входам до сети; проверки новой finite ветки | not_run |
| environment-gates | Реальный bounded preflight перед repeat: source/HEAD, ENV, actual VM/images/limits/TLS horizon, power/lid/disk/subnets/lock; проверка applicability старых reports и фактических новых controls | not_run |
| interval-decision-drift-review | После post-freeze repeat5 — реально прочитанные intervals, Q/S/U/completeness, практические решения, lag1/trends обеих серий и сравнение с заранее fixed2ms/1pp; все ограничения n5 раскрыть | not_run |

`offline-build` не означает свежую пересборку всех четырёх образов. Образы уже зафиксированы и по поручению не пересобираются без причины. Предметный trace обязан прямо написать: current host-mounted analysis/dependencies воспроизведены offline; immutable runtime images переиспользованы по применимым прежним build proofs. Если такой scope не подтверждается действительными hashes/dependency comparison, actual остаётся unknown/false; одного `compileall` недостаточно, чтобы заявить воспроизведение образов.

Существующий образный архив: `results/archives/images-05a30d9c5e341462c167a548a5942bc377e5c48de2aee0badb5db3301203a11e.tar`, 1202140160 bytes по прежнему archive-verified.json. Его SHA и IDs нужно реально перепроверить для этого пакета; прежний `load_exit=0` нельзя выдавать за новый load. Не требуется создавать второй такой же образный архив ради новой host-mounted Python версии. Новый source archive нужен, поскольку исторический image archive не содержит новый release source.

## Последовательный рецепт после освобождения сети

1. После окончательного finite commit и успешных целевых тестов получить новый `git archive HEAD` для src/docker/docs/schemas/docs/protocol/configs/Makefile/compose. Сохранить commit, SHA, sidecar; прочитать каждый member и сопоставить с фактическим `admission.sources()` и release-state. Отдельно связать policy/rationale/freeze/main schedule/ENV через path+SHA. Архив не изменять после публикации. Старые архивы и результаты не удалять.
2. В существующем analyzer с `--network none` и read-only wheelhouse выполнить `sha256sum -c /wheelhouse/SHA256SUMS`, hash-locked offline install в отдельную временную среду/target; сохранить argv/UTC/stdout/stderr/exit и dependency checks. Свежий runtime rebuild не заявлять. Сопоставить неизменённые client/server/runner/locks/Dockerfile зависимостей с применимыми прежними proofs и actual four image IDs.
3. В frozen source view с `PYTHONPATH=src/analysis`, `--network none`, read-only raw выполнить нужный known-answer набор `test_analysis.StatisticalTests`, tests finite readiness, reproduction tolerances, actual CLI forged integrity and controller guards. Полный повтор всех исторических проверок не нужен. Во время сетевого сбора никакого такого анализа.
4. Собрать controls/pilot/power/final limited verify, зафиксировать n20 и freeze. Reference pilot обязан завершиться ДО freeze. После freeze я отдельно подготовлю и действительно исполню новый admitted pilot5 на каждый профиль со всеми тремя режимами (60 runs), новым series_id/nonce/seeds, тем же release/ENV и без подбора удобного исхода. До запуска обязательны настоящий успешный preflight и свободное окно без другой сети.
5. После repeat выполнить полную raw validation и существующий `reproduction_comparison`: reference/repeat должны быть разными series IDs, их manifests соответствуют одной release, вся repeat начата ПОСЛЕ frozen_utc, n5/profile/mode coverage. Отдельно прочитать интервалы/решения/дрейф и написать предметный review. Первичные слоты/хвосты/missing сохраняются; null не заменяется.
6. Подготовить шесть trace JSON с реальными files/commands/observations, `checks` expected=true, actual/status по факту; payload document и observations точно совпадают с input. Collection связывает payload через SHA. Input содержит `author_id='/root'`, `executor_id='/root/reproduction'`, freeze/reference_schedule/repeat_schedule, actual current source/ENV и evidence. Опубликовать штатным `experiments.py import-checks --kind real`. Отсутствующий обязательный proof — not_run/inconclusive, не true.

Каждое действие оборачивается отдельными immutable start/end/exit/stdout/stderr; ошибки и timeout сохраняются. Возможная длительность более пяти минут передаётся root для согласованного запуска; команды не дробятся ради обхода ограничения. До начала repeat должен быть подготовлен один bounded последовательный запуск, а не фоновая цепочка будущих серий.

## Проверенные ограничения контракта

- Текущая строгая ветка main требует reproduction passed. Подготовленная finite ветка должна явно допускать фактически завершённый post-freeze repeat с сохранённым nonpassed scientific outcome, если все шесть действий реально выполнены и все технические инварианты соблюдены. Это изменение дальнейшего допуска, не смена результата; integration готовит точный scoped guard.
- Existing `reproduction_comparison()` заново вычисляет D4 по двум actual series и проверяет n≥5, mode coverage, timings, release, freeze binding. Эти проверки необходимы и сохраняются. Простой checks JSON с шестью true их не заменяет.
- Интервалы n5 широки/могут быть бесконечны. Fixed repeat thresholds2ms/1pp — operational predeclared comparison, не 95% доказательство переносимости. Тренды/lag1 описательные и не доказывают независимость.
- Я являюсь отдельным внутренним исполнителем на общей машине и общем коде; внешнее лабораторное воспроизведение не выполняется и не заявляется. Пока я только подготовил рецепт, не исполнил repeat и не подписал готовые шесть checks.
- Нижняя оценка repeat80min, сценарная120–180min. Его нельзя скрыть внутри четырёхчасового окна или назвать выполненным заранее; старт main≤12h планируется по фактическим runtime и remaining prerequisites.

## Уточнение пользователя после подготовки

Main/само сравнительное тестирование запускать запрещено до отдельного нового решения пользователя. Итоговая проверка готовности, acceptance, контроли, pilot и offline подготовка разрешены. Этот документ не является разрешением main. Post-freeze repeat остаётся отдельным подготовительным измерением и требует согласованного окна root; самостоятельно сеть не запускается.
