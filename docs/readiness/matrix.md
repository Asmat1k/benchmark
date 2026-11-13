# Матрица экспериментальной приёмки

Исходный релиз D6 — `aeda8e1d36bc5bc87042a6e497eefaf84213397e`. Обозначение «рабочая версия» ниже указывает на исходники после D6. Конкретный набор SHA измерения находится в его отчёте. Параметры и версии на момент исполнения зафиксированы в [инвентаризации](../../results/verify/readiness/audit/) и [журналах команд](../../results/verify/readiness/host/). Для каждого запуска host/*.json приводит команду, рабочий каталог, UTC, длительность, exit и SHA256 соответствующего stdout/stderr.

| Требование | Проверка и артефакт | Версия | Статус | Замечание |
|---|---|---|---|---|
| Происхождение исходников | git, 648 SHA по [перечню D6](../../results/verify/readiness/host/d6-manifest.json) | D6 | подтверждено | Пользовательский план отделён от релиза |
| Закреплённая сборка | [Пересборка](../../results/verify/readiness/host/clean-build.json), [версии и 21 wheel](../../results/verify/readiness/host/clean-versions.txt) | D6, linux/arm64 | подтверждено | Чистая копия, отдельные теги, без кэша шагов. База закреплена digest, apt без snapshot |
| Архив и load | [SHA](../../results/verify/readiness/host/archive-check.json), [image IDs](../../results/verify/readiness/host/archive-ids.txt) | D6 | подтверждено | Все четыре ID соответствуют исходной сборке |
| Среда | [Питание, реальные CPU/RAM и фон](../../results/verify/readiness/host/host-resources.txt) | macOS 26.5.1, Engine 29.6.2 arm64 | частично | VM 2 vCPU, 3,83 GiB; устойчивость в длительной серии не проверялась |
| WS, WT-S, WT-D, TLS и маршруты | [Короткий smoke](../../results/verify/path/wswt-smoke.mPWE7sYw/) | D6, Chromium 140.0.7339.16 | подтверждено | По 3 точных эха; отрицательные TLS-пробы, разрыв при отключённом forwarding, два направления, readback четырёх профилей. WT-D поддержан в этом запуске, решение для freeze не принято |
| Страничные часы и raw, исходная итерация | [Реальный сбор](../../results/verify/diagnostic/timer-timer.dkKn7fVu/), [решение](../../results/verify/diagnostic/timer-timer.dkKn7fVu-WS-report/report.json) | Рабочий снимок 12 ноября, 112 source SHA | частично | 100001 отсчёт, критерий выполнен в данном снимке. На каждую сторону всего 1+3 слота |
| Таймер принятой версии | [Новый raw](../../results/verify/diagnostic/timer-timer.RKMg3sCH/), [публикация](../../results/verify/diagnostic/timer-timer.RKMg3sCH-report/report.json), [предварительный verify](../../results/verify/readiness/host/partial-verify.json) | d1573e8, clean, 13 ноября | подтверждено | 100000 интервалов, монотонность, шаг 0,099999994 мс, p99 0 мс. Verify вернул 2 при девяти отсутствующих отчётах |
| Слоты, восстановление и неизменность raw | [Контрпримеры D6](../../results/verify/readiness/host/d6-counterexamples.txt), [короткие тесты](../../results/verify/readiness/host/generator-offline.json) | D6 и рабочая версия | частично | STOP, ledger, запись по адресу опубликованного raw проверены; полное окно генератора отсутствует |
| Статистика на эталонах | [5 тестов](../../results/verify/readiness/host/numerical-references.txt) | Модули D4 в текущем дереве | подтверждено | Full-n sign со связями, Holm4, ранговые интервалы, bootstrap целыми блоками, null/границы |
| Допуск до сети | [Хостовый guard](../../results/verify/readiness/host/host-guards.txt), [Git в Docker](../../results/verify/readiness/host/host-boundary.json), [приёмка исправлений](reviews/) | D6, затем рабочая версия | частично | Подставной исполнитель в тестах. Полного экспериментального пакета для положительного main admission нет |
| Задержка, потери, полоса | [Сборщик и регрессии](../../results/verify/readiness/calibration-dev/) | Рабочая версия | не выполнено | Длительный реальный сбор пропущен по уточнению пользователя; фактических ДИ и скорости нет |
| Запас генератора, CPU, OOM, очереди | [Реализация и проверки](../../results/verify/readiness/generator-dev/) | Рабочая версия | заблокировано | Полный сбор 20/100 Гц после успешной сетевой калибровки |
| Эквивалентность A/A и monitoring on/off | [Интервальные критерии](../verification.md) | План D6 | не выполнено | Две длительные серии пропущены по указанию пользователя; эквивалентность не установлена |
| Официальный пилот и power | [Порядок допуска](../experiments.md) | thresholds preliminary | заблокировано | Обязательные предыдущие проверки не приняты. Длительный пилот также пропущен по указанию пользователя |
| Final verify, freeze | [Правила заморозки](../verification.md) | Рабочая версия | заблокировано | Нет полного verify, эмпирического n и обоснованных итоговых параметров |
| Независимое экспериментальное воспроизведение | [Контракт](../experiments.md) | Рабочая версия | заблокировано | Требуется действительный freeze и отдельный повтор |
| Основная серия и ПР4 | Границы поручения | Все версии | неприменимо | Для приёмки не запускались |

Текущий допуск UDP sender — [v2](sender-quality-v2.md); исторические оценки every-slot сохранены. Ретроспектива timing не закрывает полную calibration и оставшиеся gates.
