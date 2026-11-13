# Этап 2: фиксированный релиз и среда

Статус: обязательное обновление release-state после окончательного коммита ещё ожидается; этап 2 пока не объявляется завершённым.

Дата: 13 ноября 2026. Входной HEAD проверен фактически: `4c4293359a7c21834fb3cf198c15f01ab5c93464`, main, исходное дерево чистое. Прочитаны AGENTS.md, передача этапа 1, методика независимых единиц, browser bandwidth, protocol/verification/experiments и код конфигурации, допуска, сборки, сертификатов. Этапы 3–7 не запускались.

## Принятые пользователем решения

- 40 дневных сессий исключены. Калибровка — один полный сбор, до двух часов вместе с обработкой; исходная величина разности медиан RTT сохранена.
- Согласован приближённый circular block bootstrap с заранее заданными блоками 1/2/5 с и поправкой на множественность. Реализованный контракт, seeds, объём, предпосылки и календарь: [calibration-blocks-stage2.md](calibration-blocks-stage2.md). Это не заявление конечновыборочного точного покрытия.
- **WS, WT-S и WT-D включены**. Bandwidth теперь требует три режима; реальный generator — все три при 20/100 Гц; prepare/admit требуют все три режима.
- Main ограничен 15 часами. n60 с тремя режимами требует минимум 16ч и закрыт guard freeze. n20/30/40 выбираются после pilot/power с учётом реального overhead; при недостижимости мощности в бюджете необходимо новое решение, а не скрытое сокращение объёма. A/A, monitoring и pilot здесь не сокращены.
- Пользователь явно принял фактические ресурсы **2 vCPU, 4109484032 bytes RAM (3,83 GiB)** и раскрытие отклонения от целевых 8 vCPU / 12 GiB. Docker не перенастраивался. Пороги CPU/throttling/OOM не ослаблялись, готовность этой среды определяется будущими gates.

## Конфигурация и реализация

Исходники и параметры закоммичены: `a6b2f90b4fa2c336a3afe90d505ad702b14260ef` — `main - Added bounded calibration and datagram contracts`. Последующий коммит передачи содержит документы и результаты коротких проверок, без изменения исполняемых исходников. Окончательный HEAD и committed source inventory находятся в `build/release-state.json`, штатно обновляемом после коммита передачи; итоговая сверка — `build/stage2-final-state.json`.

`configs/thresholds.json`: preliminary=false; все прежние численные пороги сохранены. Это фиксация параметров до новых source-bound сборов, не freeze. `configs/plan.json` и schema содержат включение WT-D, метод и main_budget_seconds=54000. Профили, frame 256, 20/100 Гц, 200/1200 slots, 5с drain/pause и ресурсы Compose не менялись.

Калибровка сохраняет все 14 echo и четыре saturation. До сети создаётся collection-plan.json с 18 именами и 36 directional seeds; packager требует его совпадение. Новые process-review поля обязательны; lack of justification/long dependence/drift дают inconclusive. Старый IID-путь всё ещё отбраковывает зависимость даже с independent_units=true; для нового real gate он запрещён. Ранние лаговые диагностики публикуются, а новая методика использует явные предпосылки зависимого процесса. Численный bandwidth bound строится для WS/WT-S/WT-D без изменения accounting. Прежние raw/seals/source snapshots не исправлялись.

Технические отказы: сохранить partial/quarantine/STOP и причину. Никаких автоматических повторов или добора до удобного CI. Для новых попыток нужен заранее записанный план. Смена config/source/ENV/leaf требует новых применимых допусков, старые passed не переносятся подстановкой hashes.

## Реальные образы и архив

Native host arm64; образы **linux/arm64**, эмуляция не используется. Штатная сборка чистого исходного коммита — 4,855с; штатный archive — 22,671с. Оценка до запуска опиралась на прежние 6–9с cached build / 22–28с archive, неизменные зависимости и только COPY в analyzer. Первоначальная попытка 5,504с / 23,295с была начата до успешного коммита из-за ограничения Git-записи; она отдельно сохранена как нерелизная и не используется в допуске.

| Tag | Фактический image ID |
|---|---|
| wswt-bench-server:dev | sha256:c2c60585a64d04e8dd7dd6a674625c0aec44cdc385561c8864dab734fbf19c44 |
| wswt-bench-browser:dev | sha256:356b2e1af8773aaf688f3c4e03bbfa73b2c835d88be0a76278030cf55d1c1641 |
| wswt-bench-router:dev | sha256:d78a80d31724881c1adaa57005fae37f4f23e0013945dac759d7ee1f76b6b74d |
| wswt-bench-analyzer:dev | sha256:9e263785dc135db52a216bc358c38218cf3d98f178a9981a365ca79cda7cbd62 |

Архив: `results/archives/images-05a30d9c5e341462c167a548a5942bc377e5c48de2aee0badb5db3301203a11e.tar`, 1202140160 bytes. SHA256: `05a30d9c5e341462c167a548a5942bc377e5c48de2aee0badb5db3301203a11e`, рядом `.tar.sha256`. Проверены имя/содержимое/sidecar hash, повторная загрузка и сохранение всех четырёх IDs. Все 35 встроенных Python-файлов analyzer побайтно совпадают с checkout. Исторические built IDs в images.lock.json не выдаются за текущие: lock закрепляет прежние base manifests, реальные новые IDs перечислены здесь и в release-evidence.json. Независимая экспериментальная репликация остаётся последующим действием.

Фактические версии: macOS 26.5.1 (25F80), Docker Desktop 4.85.0 (235549), Engine/CLI 29.6.2, Compose 5.3.1, Linux 6.12.76-linuxkit. Go server go1.24.6; Node 22.18.0 / npm 10.9.3; Playwright 1.55.0 / Chromium 140.0.7339.16; iproute2 6.15.0; Python 3.12.11 / NumPy 2.2.6 / SciPy 1.15.3 / pandas 2.3.2 / matplotlib 3.10.5 / seaborn 0.13.2. pip check и wheel hashes прошли в build. Полные outputs и package inventory сохранены в `results/verify/readiness/stage2-preflight/`.

## Среда, питание и TLS

Host: 8 CPU, 16 GiB RAM. Docker: принятые 2 CPU / 3,83 GiB, overlay disk 63G, свободно 37G после сборки; host свободно около 120 GiB при исходной проверке. Подсети 172.28.10.0/24 и 172.28.20.0/24 не пересекаются с существующими Docker networks. Существуют пустые transport-lab_front/back в 10.77.1/2; они не удалялись. Измерительных контейнеров нет. Measurement lock дважды реально получен и немедленно освобождён через штатный series.py hold без сети. Это моментальная проверка, её повторяют непосредственно перед измерением.

Посторонний `ai-grepa-qdrant-1` работает (unhealthy) в 172.19.0.0/16. Он не остановлен; его фон может повлиять на будущие gates и обоснование стационарности. Изменение ресурсов не предлагается как доказанное исправление пауз. Нужна оценка фактических traces/CPU при следующих допусках.

AC power, батарея 100%. sleep=1, displaysleep=20, lowpowermode=0. Настройки сна не менялись; будущие пользовательские команды оборачиваются `caffeinate -ims`, питание от сети и открытая крышка сохраняются. Текущая assertion приложения не является гарантией для всей серии.

Единый постоянный TLS-каталог для дальнейшей последовательности:

`/Users/dobrov/Desktop/Code/ITMO/benchmark/build/series-tls-stage2._n__udb0`

Новый leaf выпущен штатным testcert после чистой сборки, **до любых новых средовых gates**. SAN bench.test, ECDSA P-256 по фиксированному генератору. notBefore=2026-11-13T16:22:37Z, notAfter=2026-11-26T16:22:37Z (26 ноября 19:22:37 МСК). DER SHA256 / good pin: `fc2a5f4d7bc0fce861baee9207c82ff86bf502fda419cf45c73e3559d1a56d18`. Цепочка, совпадение public key и pin проверены, key mode0600. Приватные ключи остаются только в ignored build; не добавлены в Git/архив результатов.

Исходный build/series-tls.PMYktiWa не используется: в двух предварительных наблюдениях его fingerprint различался при одинаковых датах. Причина не установлена; исходные наблюдения сохранены, identity не считается стабильной. Новый отдельный каталог не перезаписывается. `smoke.sh` теперь уважает SERIES_TLS_DIR и не заменяет его сертификаты. Двухнедельный верхний предел pinned WebTransport исключает простое продление leaf на 40 дней: [W3C WebTransport](https://www.w3.org/TR/webtransport/).

Рекомендуемое окно всей последующей последовательности — шесть рабочих календарных дней плюс минимум двое суток запаса до notAfter; относительный план приведён в методике. Конкретные даты пока не назначены. При старте позже 18 ноября 19:22 МСК восьмисуточный резерв уже не обеспечен: до новых gates пересчитать календарь и при необходимости выпустить новый leaf. При продолжении после паузы проверить UTC/срок снова. Существующие gates прежнего leaf не применяются.

## Выполненные проверки

Итоговый адресный набор: **19 tests, OK, 40,300с**, `release-targeted.txt`. Проверены fixed method/seed/block envelope, отсутствие RTT, сохранение входов, отбраковка long dependence/drift, сохранённый старый IID guard, loss confidence, WT-D bandwidth membership, контракты generator WT-D 20/100, raw/schema/preliminary/freeze prerequisite и directional losses. Дополнительно **2 host release-guard tests, OK, 7,509с**, с настоящим Git и подставной сетью. `sh -n` затронутых shell и `git diff --check` прошли. Промежуточные отрицательные журналы сохранены; они не считаются passed. Смена protocol hash потребовала обновить только временные тестовые копии и ожидаемый отказ историческому raw.

Реальные qualification/bandwidth/calibration/generator/A/A/monitoring/pilot/main не запускались. Полный сетевой integration не повторялся. Тесты реализации не доказывают coverage bootstrap, независимость процесса или экспериментальный passed. `configs/freeze.json` отсутствует и не создаётся.

## Точная передача этапу 3

Рабочий каталог всех команд: `/Users/dobrov/Desktop/Code/ITMO/benchmark`. Сначала прочитать этот документ, проверить текущий HEAD, source cleanliness, IDs, свободные подсети/lock, питание и остаточный TLS horizon. Окончательный release-state должен соответствовать текущему HEAD; любые последующие коммиты требуют его штатного обновления, а executable изменения — новой сборки/затронутых gates.

```sh
cd /Users/dobrov/Desktop/Code/ITMO/benchmark
export SERIES_TLS_DIR=/Users/dobrov/Desktop/Code/ITMO/benchmark/build/series-tls-stage2._n__udb0
sh docker/check-release.sh "$(git rev-parse HEAD)"
sh docker/release-state.sh
(cd results/archives && shasum -a 256 -c images-05a30d9c5e341462c167a548a5942bc377e5c48de2aee0badb5db3301203a11e.tar.sha256)
```

Эти команды не дают сетевой admission. Актуальные build/TLS/path/timer/raw/analysis gates необходимо получить/оформить в этапе 3. Предметные обязательные predicates — `collection.PRIMARY_IDS`: build locked-install/native-platform/versions/archive-hashes; TLS все 10 secure/negative predicates; path все 9 routing/forwarding/offload/profile predicates; raw все 7 integrity/accounting/coverage/recovery predicates; analysis все 7 metrics/Holm/rank/bootstrap/null/reference predicates. Typed primary payload, observations и checks должны ссылаться на **фактические** collection_id/source inventory/ENV и evidence SHA. Старый development-interop-smoke сам по себе не является таким report.

Проверку TLS/path следующего этапа выполнять с тем же постоянным каталогом:

```sh
caffeinate -ims sh docker/smoke.sh
```

Планировать 2–5 минут плюс setup; если оценка в новых условиях может превысить 5 минут, запускает пользователь. Выход печатается/создаётся в `results/verify/path/wswt-smoke.XXXXXXXX`, нужны три secure echo, все negative TLS и обе блокировки forwarding-off, readback/offloads/MTU/routes, logs и SHA. Нельзя заменить эти predicates одним development summary.

**Реальный ENV пока не существует для нового релиза.** Его получает штатный D3 collector на реальных сервисах нового build/TLS; не копировать прежний context и не собирать его из ожидаемых лимитов. В этапе 3, после подготовки стенда и проверок TLS/path:

```sh
caffeinate -ims sh docker/collect-diagnostic.sh timer
```

Исторический timer около 67с, для новой среды резервировать до 3–5 минут с setup. Скрипт сам создаёт `results/verify/diagnostic/timer-timer.XXXXXXXX`, вызывает measure → context_snapshot/bind_context до нагрузки и после неё и печатает путь `...-report/report.json`. Его `environment.path` указывает на **настоящий** `timer-timer.XXXXXXXX/context.json`: host/VM/leaf/configs/bindings/IDs/лимиты. Этот файл оставить по исходному пути, сверить SHA и применять как ENV остальных gates. Даже failed timer может оставить фактический context, но переход требует passed timer и остальных ранних gates. Если context до/после различается, STOP; ENV не исправлять вручную. Timer должен сохранить 100001 page samples и пройти шаг/p99≤0.1мс; not_run не превращать в true.

После появления ENV импортировать подготовленные реальные build/TLS/path/raw/analysis collections через:

```sh
make verify ARGS="--kind real --input $REPORT_MAP --environment $ENVIRONMENT --output $VERIFY_OUTPUT"
```

REPORT_MAP содержит реальные отчёты, ENVIRONMENT — фактический context выше, VERIFY_OUTPUT — новое имя. До calibration/generator/A/A/monitoring полный verify ожидаемо имеет missing gates/exit2. Это не разрешение следующей серии. Обязательные исходные наблюдения build можно оформить из этого релиза после проверки source inventory и фактического ENV; нельзя переписать historical passed.

Qualification нового sender — последующая отдельная пользовательская команда, **не выполнена здесь**: `caffeinate -ims sh docker/sender-diagnostic.sh qualification`, около 5–6 минут; три passed v2 + неизменные source/ENV/seals и полное покрытие ресурсов. Затем bandwidth всех трёх режимов (schedule **--datagrams**, measure 0/1/2, 5–10 минут) → один новый UDP calibration raw (30–35 минут) → offline bandwidth bound/review → новый package и block report. Все работы с неизвестным/возможным runtime>5 минут запускает пользователь, включая полный научный расчёт, если его время нельзя обоснованно ограничить. Точный трёхрежимный рецепт есть в уточнении [browser-bandwidth-stage1.md](browser-bandwidth-stage1.md); review/расчёт — [docker/calibration.md](../../docker/calibration.md).

Далее generator всех трёх режимов, A/A/monitoring с --datagrams, pilot/power и дальнейшие gates относятся к своим последующим этапам. Разрешение main, freeze, мощность и практические итоги здесь не утверждаются. Этап 2 останавливается на подготовленном релизе; обязательных пользовательских запусков для самой сборки/архива больше нет. Передача этапу 3 не является его выполнением.

## Осталось после автоматической ошибки разрешений

После коммита передачи 490cc10 два запроса штатного `sh docker/release-state.sh` отклонены автоматической проверкой с технической ошибкой `Bad Request`. Команды не выполнялись; это не заключение о небезопасности. Старый snapshot не обновлялся и не выдаётся за актуальный. `build/stage2-final-state.json` также ещё не создан. Сборка, архив, TLS и адресные тесты выполнены; обязательный последний шаг остаётся открытым.

После сохранения этого уточнения коммитом пользователь выполняет из корня репозитория:

```sh
sh docker/release-state.sh
docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONPATH=src/analysis -v "$PWD:/bench:ro" -w /bench wswt-bench-analyzer:dev python -B -c 'from admission import release; print(release())'
sh docker/check-release.sh "$(git rev-parse HEAD)"
git status --short
```

Ожидается менее минуты. Файл build/release-state.json должен содержать фактический HEAD; release() должен вывести тот же SHA без ошибки source inventory; check-release exit0, git status пуст. Пока результат не получен, этап 2 остаётся открытым. Новых сборок или экспериментов для этого не нужно.
