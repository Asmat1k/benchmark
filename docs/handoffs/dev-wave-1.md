# Передача D1

Вход — main, `5cb82dcff06188132d50b2b3412b34bcc88f3627`. На входе в рабочей копии только пользовательский каталог .agents/plan/. Контракты D0 и пороги не менялись.

## Компоненты

Go-сервер в src/server обслуживает один HTTPS/WSS и один HTTP/3 WebTransport endpoint. Общая проверка READY и fixed256 находится в echo/ и protocol/. Двоичный клиент src/client и Playwright runner src/runner собираются из локальных lock-файлов. Makefile, compose.yaml, docker/ и .dockerignore задают сборку и одноразовый smoke. Использован профиль Chromium из microsoft/playwright v1.55.0, utils/docker/seccomp_profile.json, SHA256 cc3e61cabda6bbc1e53e54d27ba4d55a9d3be829b6dd1a596f4a7b31b1cc7849. Chrome работает от pwuser с chromiumSandbox=true.

## Воспроизведение и результаты

1. Выполнить `make build`. Обе установки npm ci, tsc, пять тестов client (1/255, 255/1, по байту, объединение трёх кадров, обрезанный EOF и порча байтов), Go test включая полный и оборванный stream/короткие записи и сборка linux/arm64 прошли.
2. Выполнить `make smoke`. Каждый вызов создаёт свой временный Compose project, новые leaf и отдельный каталог результатов. SHA256 CA обозначает хеш файла PEM, leaf — хеш DER. Private CA keys существуют только в памяти генератора, сертификаты и ключи листа удаляются после завершения. Страница всегда загружена с доверенного origin до endpoint-проб. Разные порты отрицательных endpoint доступны только в этом internal project.
3. Итоговая [проверка](../../results/verify/interop/wswt-smoke.IRiAPY6U/checks.json) связывает browser/server/build traces через SHA256. WSS Upgrade 101 (ALPN http/1.1, TLS1.3), WT CONNECT (ALPN h3, QUIC1, SETTINGS и draft02), три точных эхо каждого режима. WT-D согласовал 1024 байт и вернул 256-байтные datagrams. HTTPS/WSS отвергли wrong SAN, expired и unknown CA по соответствующим ошибкам. Pinned WT отверг wrong pin и expired по CERTIFICATE_VERIFY_FAILED. Runner завершился с кодом 0. Ранний smoke QjGH36f1 сохранён до усиления автоматической проверки причин TLS и graceful close WT-S. Сценарий ограничен таймером 45 с, обе итерации заняли по несколько секунд, нагрузочных проверок не проводилось.
4. Сверить npm locks (SHA256): client 85d2b0ddd22ec7a8fc82222b1a8ea1246d68ed1564c2600f530b6aa7d11acb96, runner b4f3d56e4a78682ed6e695f596698b5f43cf67ac79b4ff6312048129e149a276. Точные версии и SHA бинарников Go, go.mod/go.sum, image IDs в build.txt. Браузерный trace содержит Chromium 140.0.7339.16 rev1187, Node 22.18.0/npm 10.9.3, TypeScript 5.9.2, Playwright 1.55.0, @types/node 22.18.0. Checks проверен по схеме D0.

## Ограничения и переход

В D1 используется прямой диагностический путь в одной внутренней сети. D2 должен подтвердить два сегмента, маршруты/forwarding-off и readback, закрепить образы и обследовать среду. quic-go при старте сообщил фактический UDP receive buffer 416 KiB при запросе 7168 KiB. npm audit при получении lock runner сообщил одну high severity advisory; baseline сохранён по плану. Применимость и версии для релиза требуют отдельного рассмотрения. Данные smoke отделены от pilot/main. Экспериментальные gates остаются not_run/deferred_by_user. Независимый вердикт и замечания находятся в docs/reviews/ws-wt-bench/dev-wave-1/. После приёмки итоговый SHA передаёт координатор.
