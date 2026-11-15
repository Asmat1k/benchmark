# benchmark

Локальный стенд для сравнения WebSocket, WebTransport stream и datagram на Docker VM. Измеряет Chromium; Go-сервер возвращает кадры через router/netem; Python готовит расписание и строит отчёт.

Актуальные инструкции: [документация](docs/README.md), [запуск и продолжение](docs/readiness/run-today.md), [правила исследовательского сбора](docs/readiness/exploratory-browser-study-v2.md). Устройство Docker-каталогов — [docker/README.md](docker/README.md).

Текущий режим сохраняет все 240 назначений, включая отказавшие и незапущенные; исторические failed/partial остаются без изменений. Основной эксперимент запускает пользователь. Данные и отчёты хранятся в results/, зависимости и сборочные файлы — в build/.
