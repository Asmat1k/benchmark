# Исходный код стенда

Код разделён по месту выполнения. Клиент измеряет время в Chromium, runner управляет браузером, сервер возвращает кадры, анализатор готовит расписание, проверяет данные и строит отчёт.

| Модуль | Что делает |
|---|---|
| [client/](#client) | TypeScript-страница: WS/WT-S/WT-D, слоты, таймер, проверка ответов |
| [runner/](#runner) | Node.js и Playwright: запуск Chromium, TLS-проверки и сохранение снимков |
| [server/](#server) | Go: HTTPS, WebSocket и HTTP/3 WebTransport echo-сервер |
| [analysis/](#analysis) | Python: допуск, исполнение серии, валидация raw и статистика |

Сборку и запуск связывают [Makefile](../Makefile), [Compose](../compose.yaml) и [Docker-сценарии](../docker/README.md). Общие форматы задают [configs/](../configs/README.md). Порядок работы — в [docs/run.md](../docs/run.md).

<a id="analysis"></a>

## Подготовка, исполнение и анализ серий

Python-модули готовят допуск и расписание, управляют исполнением серии, проверяют исходные наблюдения и строят отчёты. Текущий путь: `admission.exploratory` → `execution.execution` → `measurement.raw` → `reporting.analyze`. Зависимости закреплены в [requirements.txt](analysis/requirements.txt), параметры — в [configs/](../configs/README.md).

Реализация и её тесты находятся рядом:

| Каталог | Реализация и проверки |
|---|---|
| [admission/](#analysis-admission) | Приёмка, сбор свидетельств, ограниченный и исследовательский допуск |
| [calibration/](#analysis-calibration) | Калибровка и качество UDP-отправителя |
| [execution/](#analysis-execution) | Расписание, контроллер, исполнение, публикация и замена |
| [measurement/](#analysis-measurement) | Raw, метрики, ресурсы, стабилизация и диагностические входы |
| [reporting/](#analysis-reporting) | Статистика, анализ, графики и синтетический генератор |
| [tests/](#analysis-tests) | Общие и интеграционные проверки без отдельного модуля фичи; fixtures |

Команды запуска сохраняются в Makefile. При ручном запуске Python из корня репозитория задайте `PYTHONPATH=src/analysis`; в analyzer это уже настроено. Модули импортируются по полному имени, например `measurement.raw` и `admission.admission`.

Все проверки обнаруживаются рекурсивно:

```sh
docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 -e MPLCONFIGDIR=/tmp/matplotlib -v "$PWD:/bench" -w /bench wswt-bench-analyzer:dev python -B -m unittest discover -s src/analysis -v
```

Можно запускать фичу: `python -m unittest discover -s src/analysis/execution -t src/analysis`, либо модуль: `python -m unittest execution.test_execution`. Полный старый набор содержит известные несовместимые fixtures; перенос не меняет критерии и исходы этих проверок.

<a id="analysis-admission"></a>

## Допуск серии

Проверяет свидетельства готовности, привязку к среде и исходникам и допустимость запуска. Текущий исследовательский путь отделён от сохранённых строгих этапов.

| Файл | Назначение |
|---|---|
| [exploratory.py](analysis/admission/exploratory.py) | Подготовка и проверка exploratory-browser-study-v2: расписание, снимки и ограничения |
| [admission.py](analysis/admission/admission.py) | Общие проверки свидетельств, хешей, freeze и допуска |
| [acceptance.py](analysis/admission/acceptance.py) | Статистические критерии калибровки, генератора и контрольных сравнений |
| [collection.py](analysis/admission/collection.py) | Сбор и проверка входных свидетельств |
| [browser_admission.py](analysis/admission/browser_admission.py) | Допуск браузерного исследования и проверка среды |
| [limited_readiness.py](analysis/admission/limited_readiness.py) | Ограниченная готовность старого finite-пути |

Тесты `test_*.py` лежат рядом. Из корня: `PYTHONPATH=src/analysis python3 -m unittest discover -s src/analysis/admission -t src/analysis -v` (нужны зависимости анализатора). Общие команды и ограничения набора — в [README анализатора](#analysis).

<a id="analysis-calibration"></a>

## Калибровка и качество отправителя

Разбирает наблюдения калибровки и проверяет качество генерации нагрузки. Результаты используются при оценке готовности; текущий исследовательский режим сохраняет исторические отказы.

| Файл | Назначение |
|---|---|
| [calibration_blocks.py](analysis/calibration/calibration_blocks.py) | Агрегация калибровочных блоков |
| [calibration_observed.py](analysis/calibration/calibration_observed.py) | Проверка наблюдённых характеристик профиля |
| [sender_quality.py](analysis/calibration/sender_quality.py) | Оценка качества UDP-отправителя |

Тесты `test_*.py` лежат рядом. Из корня: `PYTHONPATH=src/analysis python3 -m unittest discover -s src/analysis/calibration -t src/analysis -v` (нужны зависимости анализатора). Общие команды и ограничения набора — в [README анализатора](#analysis).

<a id="analysis-execution"></a>

## Исполнение серии

Готовит детерминированное расписание, управляет очередью назначений и сохраняет результаты. Для exploratory-пути отдельный отказ не вызывает повтор или замену: после очистки выполняется следующее назначение.

| Файл | Назначение |
|---|---|
| [schedule.py](analysis/execution/schedule.py) | Расписание, порядок и seeds |
| [execution.py](analysis/execution/execution.py) | Текущий цикл: предварительная проверка, лимиты, исходы, восстановление и отчёт после очистки |
| [controller.py](analysis/execution/controller.py) | Контроллер допуска и команд исполнения |
| [series.py](analysis/execution/series.py) | Блокировка измерений, очередь и привязка контекста |
| [record.py](analysis/execution/record.py) | Спецификация запуска и завершение публикации |
| [quarantine.py](analysis/execution/quarantine.py) | Сохранение неуспешных данных |
| [violation.py](analysis/execution/violation.py) | Обнаружение и диагностика нарушений |
| [experiments.py](analysis/execution/experiments.py) | Строгие этапы и оценка экспериментальных серий |
| [replace.py](analysis/execution/replace.py) | Замена блоков старого строгого пути; не применяется в exploratory |

Тесты `test_*.py` лежат рядом. Из корня: `PYTHONPATH=src/analysis python3 -m unittest discover -s src/analysis/execution -t src/analysis -v` (нужны зависимости анализатора). Общие команды и ограничения набора — в [README анализатора](#analysis).

<a id="analysis-measurement"></a>

## Исходные измерения

Проверяет целостность raw и вычисляет показатели запуска. Проверки формы, идентификаторов, хешей и полноты отделены от статистических выводов по серии.

| Файл | Назначение |
|---|---|
| [raw.py](analysis/measurement/raw.py) | Чтение, валидация и публикация raw |
| [metrics.py](analysis/measurement/metrics.py) | RTT, Q/S/U и описательные показатели |
| [resources.py](analysis/measurement/resources.py) | Обработка наблюдений ресурсов |
| [stabilization_cpu.py](analysis/measurement/stabilization_cpu.py) | Оценка CPU перед измерением |
| [diagnostic_input.py](analysis/measurement/diagnostic_input.py) | Преобразование диагностических данных в свидетельства |
| [smoke.py](analysis/measurement/smoke.py) | Короткая проверка измерительных данных |

Тесты `test_*.py` лежат рядом. Из корня: `PYTHONPATH=src/analysis python3 -m unittest discover -s src/analysis/measurement -t src/analysis -v` (нужны зависимости анализатора). Общие команды и ограничения набора — в [README анализатора](#analysis).

<a id="analysis-reporting"></a>

## Отчёты и статистика

Читает серии после измерений и создаёт производные отчёты. Полнота и валидность данных определяют доступность парных выводов; неизвестное не подставляется как потеря.

| Файл | Назначение |
|---|---|
| [analyze.py](analysis/reporting/analyze.py) | CLI анализа и проверка сравнительной серии |
| [outcomes.py](analysis/reporting/outcomes.py) | Отчёт по всем назначениям, включая неполные и незапущенные |
| [inference.py](analysis/reporting/inference.py) | Парные статистические расчёты |
| [plots.py](analysis/reporting/plots.py) | Графики результатов |
| [power.py](analysis/reporting/power.py) | Оценка мощности старого строгого пути |
| [synthetic.py](analysis/reporting/synthetic.py) | Генерация синтетических серий для проверок |

Тесты `test_*.py` лежат рядом. Из корня: `PYTHONPATH=src/analysis python3 -m unittest discover -s src/analysis/reporting -t src/analysis -v` (нужны зависимости анализатора). Общие команды и ограничения набора — в [README анализатора](#analysis).

<a id="analysis-tests"></a>

## Общие и интеграционные проверки

Здесь находятся тесты взаимодействия модулей: восстановление и checkpoint, интеграция измерителя, защита релиза, контракты порогов и зависимости приёмки/калибровки. Тесты отдельных фич находятся рядом с реализацией в [модулях анализатора](#analysis).

[fixtures/](#analysis-tests-fixtures) содержит синтетические документы для проверки схем и контрактов.

Из корня с установленными зависимостями: `PYTHONPATH=src/analysis python3 -m unittest discover -s src/analysis/tests -t src/analysis -v`. Полный исторический набор содержит несовместимые fixtures; описание охвата — [docs/verification.md](../docs/verification.md).

<a id="analysis-tests-fixtures"></a>

## Тестовые данные

[synthetic/](analysis/tests/fixtures/synthetic) содержит корректные и некорректные JSON-примеры slot, manifest и ledger, корректный checks и скрипт [validate.py](analysis/tests/fixtures/synthetic/validate.py). Он проверяет ожидаемое принятие или отклонение документов по [JSON-схемам](../configs/README.md#schemas).

Из корня: `python3 src/analysis/tests/fixtures/synthetic/validate.py` с зависимостями анализатора. Эту проверку выполняет и [GitHub Actions](../.github/workflows/checks.yml). Эти данные синтетические и не являются результатами сетевого измерения.

<a id="client"></a>

## Браузерный измеритель

TypeScript-клиент работает внутри Chromium. Он устанавливает WS, WT-S или WT-D соединение, выполняет READY/ACK, отправляет кадры по расписанию и записывает слоты, ответы и события часами страницы. Пропущенные слоты не догоняются.

| Путь | Назначение |
|---|---|
| [src/](#client-src) | Протокол, транспорт, измерение и диагностика таймера |
| [index.html](client/index.html) | Страница, которую раздаёт Go-сервер |
| [test.mjs](client/test.mjs) | Проверки клиентского протокола и измерителя |
| [package.json](client/package.json) | Сборка TypeScript и запуск тестов |

`npm ci`, `npm run build`, `npm test` выполняются из `src/client/`; тесты требуют предварительной сборки. При `make build` клиент собирается и проверяется в [образе сервера](../docker/images/Dockerfile.server), результат копируется в `/page`. Правила измерения — [docs/measurement.md](../docs/measurement.md).

<a id="client-src"></a>

## Код страницы

| Файл | Назначение |
|---|---|
| [protocol.ts](client/src/protocol.ts) | Формирование и проверка кадров, чтение границ кадров в потоке |
| [smoke.ts](client/src/smoke.ts) | Открытие WS/WebTransport и короткие проверки обмена |
| [measurement.ts](client/src/measurement.ts) | Расписание слотов, учёт отправки, ответов, очередей и событий |
| [measure-page.ts](client/src/measure-page.ts) | Подключение измерителя к трём транспортам и снимок состояния для runner |
| [timer.ts](client/src/timer.ts) | Диагностика разрешения часов страницы |

Подпапок нет. Код компилируется в `src/client/dist/`; управление браузером находится в [runner](#runner).

<a id="runner"></a>

## Управление Chromium

Node.js-процессы используют Playwright для управления браузером внутри контейнера. Измерение RTT выполняет [страница](#client); runner передаёт ей спецификацию и сохраняет результат.

| Файл | Назначение |
|---|---|
| [main.ts](runner/main.ts) | Smoke: версии среды, secure context, обмен и отрицательные TLS-сценарии |
| [path.ts](runner/path.ts) | Проверка сетевого пути |
| [measure.ts](runner/measure.ts) | Чтение `/tmp/run.json`, запуск измерения, сохранение page/security JSON |
| [checkpoint.ts](runner/checkpoint.ts) | Периодическое сохранение промежуточных данных страницы |
| [test-checkpoint.mjs](runner/test-checkpoint.mjs) | Проверка checkpoint при принудительном падении браузера |

Подпапок с исходниками нет. `npm ci` и `npm run build` собирают runner; штатно это делает [Dockerfile.browser](../docker/images/Dockerfile.browser). Запуск внутри контейнера и импорт CA выполняет [browser.sh](../docker/runtime/browser.sh). Для checkpoint-теста нужна собранная среда с Playwright/Chromium.

<a id="server"></a>

## Echo-сервер

Go-сервер раздаёт клиентскую страницу по HTTPS и возвращает бинарные кадры через WebSocket (`/ws`, TCP) или WebTransport (`/wt`, UDP/HTTP/3). По умолчанию слушает порт 8443 и использует TLS 1.3. Перед кадрами выполняется READY/ACK.

| Путь | Назначение |
|---|---|
| [main.go](server/main.go) | TLS, HTTP/1.1 и HTTP/3, страница и сохранение счётчиков по SIGUSR1 |
| [cmd/](#server-cmd) | Утилита создания тестовых сертификатов |
| [echo/](#server-echo) | Общая логика ответа и счётчики |
| [protocol/](#server-protocol) | Проверка бинарного кадра |
| [transports/](#server-transports) | Обработчики WS, WT stream и WT datagram |

Из `src/server/` `go test -mod=readonly ./...` проверяет Go-код. Штатная сборка и тестирование проходят в [Dockerfile.server](../docker/images/Dockerfile.server). Формат кадра — [docs/protocol.md](../docs/protocol.md).

<a id="server-cmd"></a>

## Вспомогательные Go-команды

[testcert/](server/cmd/testcert) создаёт тестовый CA, серверные сертификаты и публичные pins для браузера, включая сертификаты для отрицательных TLS-проверок. Собирается в бинарник `testcert` внутри образа сервера.

Обычное измерение запускает [main.go](server/main.go), а не эту команду. Создание общего сертификата серии описано в [инструкции запуска](../docs/run.md); приватные ключи хранятся в локальном `build/`.

<a id="server-echo"></a>

## Общая логика echo

[echo.go](server/echo/echo.go) проверяет READY до начала обмена, отвечает ACK, затем проверяет и возвращает кадр. [count.go](server/echo/count.go) учитывает приём, валидность, запись и активные соединения; тесты счётчиков — [count_test.go](server/echo/count_test.go).

Логику используют [транспортные обработчики](#server-transports). Подпапок нет; тесты запускаются через `go test ./...` из [server/](#server).

<a id="server-protocol"></a>

## Проверка кадров

[frame.go](server/protocol/frame.go) задаёт размер кадра и проверяет его бинарный формат. Этот пакет используется серверным echo; аналогичная клиентская реализация находится в [protocol.ts](client/src/protocol.ts).

Описание полей — [docs/protocol.md](../docs/protocol.md), машинный контракт — [configs/contracts/](../configs/README.md#contracts). Подпапок нет.

<a id="server-transports"></a>

## Транспортные обработчики

[websocket.go](server/transports/websocket.go) обслуживает WS, [webtransport.go](server/transports/webtransport.go) — один двунаправленный WT-поток либо WT-датаграммы. Обработчики передают данные общей [echo-логике](#server-echo) и учитывают серверные счётчики. Поток собирается в кадры фиксированного размера.

[webtransport_test.go](server/transports/webtransport_test.go) проверяет потоковый обмен. Подпапок нет. Запуск всех серверных тестов — `go test ./...` из [server/](#server).
