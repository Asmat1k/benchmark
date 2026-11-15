# Структура Docker-окружения

Все команды выполняются из корня репозитория. Основные точки входа остаются в `Makefile`.

| Каталог | Содержимое |
|---|---|
| [images/](#images) | Dockerfile четырёх образов: server, browser, router, analyzer |
| [config/](#config) | Закреплённые образы, список пакетов и профиль Chromium seccomp |
| [commands/](#commands) | Команды сборки, запуска, измерения, анализа, диагностики и очистки |
| [runtime/](#runtime) | Скрипты, выполняемые внутри контейнеров: браузер, сеть, сбор ресурсов |
| [lib/](#lib) | Общие части команд: маршруты, контроллер, проверки релиза и очистка |
| [diagnostics/](#diagnostics) | Python-инструменты калибровки и диагностики |
| [tests/](#tests) | Проверки Python-инструментов и служебных сценариев |
| [docs/](#docs) | Описание запуска калибровки |

`make build` собирает образы, `make docker-test` запускает проверки из `tests/` без измерительной сети. Остальные команды Make сохранены.

Старые пути в сохранённых результатах и исторических отчётах описывают расположение файлов на момент сбора. Эти артефакты не переписываются при реорганизации.

<a id="commands"></a>

## Команды стенда

Shell-сценарии, которые вызываются из корневого [Makefile](../Makefile). Рабочая папка при запуске — корень репозитория.

| Файл | Назначение |
|---|---|
| [build.sh](commands/build.sh) | Сборка образов и свидетельств среды |
| [smoke.sh](commands/smoke.sh) | Проверка TLS и сетевого пути |
| [measurement-smoke.sh](commands/measurement-smoke.sh) | Короткая проверка измерения |
| [measure.sh](commands/measure.sh) | Одно назначение: сеть, браузер, ресурсы и сохранение raw |
| [experiment.sh](commands/experiment.sh) | Вход в исполнение серии; требует явного ALLOW_REAL_EXPERIMENTS=yes |
| [analyze.sh](commands/analyze.sh) | Повторный анализ серии |
| [acceptance.sh](commands/acceptance.sh) | Строгие этапы приёмки и подготовки |
| [calibration.sh](commands/calibration.sh) | Сетевая калибровка |
| [collect-diagnostic.sh](commands/collect-diagnostic.sh) | Сбор диагностических данных |
| [sender-diagnostic.sh](commands/sender-diagnostic.sh) | Диагностика отправителя |
| [sender-scheduling.sh](commands/sender-scheduling.sh) | Проверка планирования отправки |
| [sender-scheduling-selftest.sh](commands/sender-scheduling-selftest.sh) | Самопроверка диагностики планировщика |
| [cleanup.sh](commands/cleanup.sh) | Очистка своего path-smoke проекта |
| [archive.sh](commands/archive.sh) | Архив четырёх Docker-образов с SHA-256 |

<a id="config"></a>

## Параметры Docker-среды

Файлы закрепления и настройки среды контейнеров.

| Файл | Назначение |
|---|---|
| [images.lock.json](config/images.lock.json) | Закреплённые версии и хеши образов |
| [os-packages.txt](config/os-packages.txt) | Сведения о системных пакетах |
| [chromium-seccomp.json](config/chromium-seccomp.json) | Профиль системных вызовов Chromium, подключённый в Compose |

<a id="diagnostics"></a>

## Диагностика стенда

Python-инструменты для исследования сети, калибровки и качества отправителя. Их вызывают [команды диагностики](#commands); это отдельные проверки среды, а не основной статистический отчёт.

| Файл | Назначение |
|---|---|
| [calibration_probe.py](diagnostics/calibration_probe.py) | Сетевые пробы калибровки |
| [calibration_report.py](diagnostics/calibration_report.py) | Разбор результатов калибровки |
| [browser_bandwidth.py](diagnostics/browser_bandwidth.py) | Проверка полосы браузерного пути |
| [sender_diagnostic_probe.py](diagnostics/sender_diagnostic_probe.py) | Проба отправителя с диагностикой |
| [sender_diagnostic_plain.py](diagnostics/sender_diagnostic_plain.py) | Вариант пробы без расширенной диагностики |
| [sender_diagnostic_resources.py](diagnostics/sender_diagnostic_resources.py) | Наблюдения ресурсов отправителя |
| [sender_qualification_probe.py](diagnostics/sender_qualification_probe.py) | Квалификационная проба отправителя |
| [sender_scheduling_probe.py](diagnostics/sender_scheduling_probe.py) | Наблюдение планирования отправки |
| [sender_scheduling_trace.py](diagnostics/sender_scheduling_trace.py) | Трассировка планирования |
| [sender_scheduling_check.py](diagnostics/sender_scheduling_check.py) | Проверка результатов планирования |

<a id="docs"></a>

## Документация диагностики

Дополнительные инструкции для отдельных Docker-процедур.

| Файл | Назначение |
|---|---|
| [calibration.md](docs/calibration.md) | Запуск и разбор сетевой калибровки |

<a id="images"></a>

## Сборка образов

Четыре Dockerfile используют корень репозитория как build context. Сборка выполняется через `make build` и корневой [compose.yaml](../compose.yaml).

| Файл | Назначение |
|---|---|
| [Dockerfile.server](images/Dockerfile.server) | Сборка и тесты TypeScript-клиента и Go-сервера, сервер и testcert в итоговом образе |
| [Dockerfile.tests](images/Dockerfile.tests) | Отдельный образ Python-тестов с Git на базе analyzer; не используется для измерений |
| [Dockerfile.browser](images/Dockerfile.browser) | Playwright, Chromium, Node.js и собранный runner |
| [Dockerfile.router](images/Dockerfile.router) | iproute2/tc, сетевые инструменты и настройка netem |
| [Dockerfile.analyzer](images/Dockerfile.analyzer) | Python, зависимости с хешами, wheelhouse и модули анализа |

<a id="lib"></a>

## Общие части сценариев

Переиспользуемые shell-части для [commands/](#commands). Здесь нет самостоятельного пользовательского интерфейса запуска.

| Файл | Назначение |
|---|---|
| [links.sh](lib/links.sh) | Работа с сетевыми интерфейсами и маршрутами |
| [controller-client.sh](lib/controller-client.sh) | Обмен с Python-контроллером |
| [check-release.sh](lib/check-release.sh) | Проверка релиза |
| [release-state.sh](lib/release-state.sh) | Подготовка состояния релиза |
| [measurement-cleanup.sh](lib/measurement-cleanup.sh) | Очистка измерительного окружения |
| [interop-result.sh](lib/interop-result.sh) | Фиксация результата проверки совместимости |
| [calibration-neighbors.sh](lib/calibration-neighbors.sh) | Контроль соседних контейнеров при калибровке |

<a id="runtime"></a>

## Сценарии внутри контейнеров

Обеспечивают сетевую среду и наблюдения для измерения. Вызываются сценариями хоста, часть файлов копируется в образы при сборке.

| Файл | Назначение |
|---|---|
| [browser.sh](runtime/browser.sh) | Подготовка доверия CA и запуск browser runner |
| [network.sh](runtime/network.sh) | Маршрутизация и netem |
| [check-seed.sh](runtime/check-seed.sh) | Проверка поддержки seed для сетевой эмуляции |
| [sample.sh](runtime/sample.sh) | Сбор наблюдений ресурсов |
| [sample-backlog.sh](runtime/sample-backlog.sh) | Сбор состояния очередей |
| [check-sample.sh](runtime/check-sample.sh) | Проверка среды сбора ресурсов |

<a id="tests"></a>

## Проверки Docker-инструментов

Python unittest-проверки калибровочных проб и отчётов, контроля соседних контейнеров, полосы браузера и планирования отправителя. Выполняются командой `make docker-test` из корня в analyzer без измерительной сети.

| Файл | Назначение |
|---|---|
| [browser_bandwidth_test.py](tests/browser_bandwidth_test.py) | Полоса браузерного пути |
| [calibration_test.py](tests/calibration_test.py) | Калибровочные сценарии |
| [calibration_probe_test.py](tests/calibration_probe_test.py) | Калибровочная проба |
| [calibration_neighbors_test.py](tests/calibration_neighbors_test.py) | Контроль соседей |
| [sender_scheduling_check_test.py](tests/sender_scheduling_check_test.py) | Проверки планирования отправки |
