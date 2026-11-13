# Короткая проверка перед замерами · 13 ноября 2026

Шаг 4 выполнен успешно на релизе d1573e82d7b61d01fb9df88f52469f256031f1d3 после пользовательской сборки. Исходники не изменены. Фактические image IDs, версии, срок leaf, UTC, команды, длительности, коды и SHA логов сохранены в results/verify/readiness/host/step4-*.json.

## Соединения, безопасность и маршрут

make smoke, exit 0, 17,978 с. WS/WT-S/WT-D вернули по три точных кадра. Проверены TLS-negative, оба направления TCP/UDP, readback четырёх профилей и блокировка WS/WT при отключённом forwarding. Штатный smoke создал свой временный набор сертификатов для негативных проверок и удалил его.

[Первичные результаты](../../results/verify/path/wswt-smoke.Crq2oPFu/) содержат browser.txt, trace.txt, счётчики, routes, checks.json и cleanup.json с нулём собственных контейнеров/сетей.

## Журналы с пользовательским сертификатом

SERIES_TLS_DIR=/Users/dobrov/Desktop/Code/ITMO/benchmark/build/series-tls.PMYktiWa, sh docker/collect-diagnostic.sh timer, exit 0, 67,308 с. По одному warmup и трём измерительным слотам на WS и WT-S. Валидатор повторно проверил raw, точное эхо 256 байт, schemas, hashes, состояние complete, соответствие контекста и сертификата. Действительный DER SHA256 сертификата 16a9e168db41e4c9d757bedb1c856b15e281d2d66dde931d6f482736db4ba2da совпал с предоставленным пользователем. Таймер монотонный, 100000 интервалов, шаг 0,099999994 мс, p99 0 мс.

[Raw](../../results/verify/diagnostic/timer-timer.gJl7zPBv/) · [Отчёт таймера](../../results/verify/diagnostic/timer-timer.gJl7zPBv-report/report.json) · [Повторная проверка](../../results/verify/readiness/host/step4-validation.txt).

Оба запущенных проекта очищены, измерительная блокировка доступна, остался исходный qdrant. Постоянный сертификат пользователя сохранён. Длительные экспериментальные проверки в этом шаге отсутствуют. Проверка подтверждает короткий путь от соединения до валидного raw. Полное окно нагрузки и экспериментальные условия допуска описаны в matrix.md.

[Проверка очистки](../../results/verify/readiness/host/step4-cleanup.txt).
