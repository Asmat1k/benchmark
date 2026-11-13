# Этап 3: подготовка и ожидание пользовательского smoke

Статус: НЕ ЗАВЕРШЁН. Нет нового реального ENV, шести passed и частичного verify. Это промежуточная передача для продолжения того же этапа3, не этапа4. Последующие измерения не запускались.

Входной HEAD: f7772cca12efd9bb75055551b87743344fb08a4d, main, чистый. Изменены только документы/отдельные инструменты подготовки evidence вне release source inventory и новые результаты этапа3. 134 исполняемых хеша совпали с этапом2. Документальный коммит подготовки следует после этого файла; его SHA доступен в Git и обновляемом штатно build/release-state.json. После коммита обязательна повторная сверка134 хешей, source inventory отчётов пока отсутствует.

## Проверенный релиз

| Образ | ID |
|---|---|
| server | sha256:c2c60585a64d04e8dd7dd6a674625c0aec44cdc385561c8864dab734fbf19c44 |
| browser | sha256:356b2e1af8773aaf688f3c4e03bbfa73b2c835d88be0a76278030cf55d1c1641 |
| router | sha256:d78a80d31724881c1adaa57005fae37f4f23e0013945dac759d7ee1f76b6b74d |
| analyzer | sha256:9e263785dc135db52a216bc358c38218cf3d98f178a9981a365ca79cda7cbd62 |

Native arm64, Docker2vCPU/4109484032bytes. Image IDs сверены с фактическими docker image inspect. Архив results/archives/images-05a30d9c5e341462c167a548a5942bc377e5c48de2aee0badb5db3301203a11e.tar:1202140160bytes,SHA256=05a30d9c5e341462c167a548a5942bc377e5c48de2aee0badb5db3301203a11e. Sidecar и повторный hashlib совпали. Образы не пересобирались.

Постоянный TLS: /Users/dobrov/Desktop/Code/ITMO/benchmark/build/series-tls-stage2._n__udb0. Фактический DER SHA/pin=fc2a5f4d7bc0fce861baee9207c82ff86bf502fda419cf45c73e3559d1a56d18; notBefore2026-11-13T16:22:37Z,notAfter2026-11-26T16:22:37Z. Сертификат не менялся; ключи не копировались в evidence. На13ноября восемь суток резерва обеспечены; календарные даты дальнейших сборов не назначены. Перед задержанным запуском срок проверяется снова.

Host118GiB/VM37G свободно. Подсети172.28.10.0/24 и172.28.20.0/24 свободны. Measurement lock штатно получен и освобождён без сети. Чужой qdrant и остальные сети не изменялись. Последняя проверка13ноября21:27:43МСК: AC Power,100%,charged; ранее зафиксирован переход на батарею. Глобальные настройки сна не менялись.

## Результаты и ограничения

13 адресных offline tests:OK,1.960s. Клиентский код из текущего server image в текущем browser image:9tests,OK,151.952084ms. Null-family: исходный штатный тест отказал на protocol/config hash; первая отдельная synthetic fixture отказала на старом context; окончательная новая временная synthetic fixture с текущими protocol hash и context_snapshot прошла тот же тест за11.182s. Все журналы отказов сохранены. Это проверка анализа и recovery на fixtures, не реальные сетевые измерения и не допуск серии. Исполняемые исходники и исторические raw/context/SHA/seals/reports не менялись.

Карта всех37 predicates, точные команды и первичные источники: [stage3-evidence-plan.md](stage3-evidence-plan.md). Происхождение отдельных инструментов подготовки сохраняется в Git и SHA256SUMS. Ни одного boolean true ради заполнения схемы не создано.

ENV, build/tls/path/timer/raw/analysis reports, REPORT_MAP и verify: НЕ СОЗДАНЫ, пути/SHA пока отсутствуют. Все шесть gates остаются открытыми. Calibration/generator/aa/monitoring не запускались; preliminary=false сохранено, freeze отсутствует. Сетевые контейнеры этапа3 ещё не запускались, поэтому нового cleanup.json нет. После smoke отдельно проверить штатный cleanup.json и отсутствие ресурсов только его проекта.

## Продолжение

Smoke оценён2–5мин плюс setup; превышение5мин нельзя исключить. По правилу пользователя запускает пользователь:

```sh
cd /Users/dobrov/Desktop/Code/ITMO/benchmark
python3 docs/readiness/stage3-smoke.py
```

Упаковщик выполняет штатный caffeinate -ims sh docker/smoke.sh с постоянным SERIES_TLS_DIR. Перед сетью сверяет AC/HEAD/cleanliness/release-state/IDs/resources/subnets/lock/pin/horizon. Сохраняет results/verify/readiness/stage3/smoke-run-UTC/{smoke.txt,execution.json,SHA256SUMS}; штатные файлы остаются в results/verify/path/wswt-smoke.XXXXXXXX. Не повторять после отказа автоматически. Exit0 недостаточно: разобрать все TLS/path predicates, exact echo WS/WT-S/WT-D, сохранение leaf и очистку.

После результата вернуться в этот чат: оценить и получить штатный timer diagnostic, взять точный environment.path из timer report, полностью проверить оба raw. Затем подготовить typed traces/observations/checks и новые collections/inputs; импортировать пять gates с --kind real, повторно валидировать все шесть, выполнить make verify с новым REPORT_MAP/ENV/выходным именем. Требуется шесть passed, четыре not_run,exit2,final=false. Обновить эту передачу окончательными путями/SHA/длительностями; сохранить итоговый пакет evidence, сделать документальный коммит и штатно обновить release-state. Только после этого этап3 завершён. Этап4 в этом чате не запускать.

## Сохранённые материалы подготовки

Пакет: results/archives/stage3-preparation-evidence.tar.gz; рядом .sha256. Это пакет подготовки, не окончательный пакет шести gates. Индивидуальные контрольные суммы: results/verify/readiness/stage3/SHA256SUMS (пути от корня репозитория).

| Файл | SHA256 |
|---|---|
| results/verify/readiness/stage3/source-archive-preflight.json | be1a16e593e23c1de2ebeeb9177fc6dc6b1f6e46d8c6b27bd32ea2b174e260ba |
| results/verify/readiness/stage3/environment-preflight.json | 9f57dac619bbbe81fc786ae679165e843603e208e13b3098c3835a5b15045a70 |
| results/verify/readiness/stage3/source-inventory.json | 71efbe891b780d73946b9e7cea0f38f54c28b65253557c9133159d26a7f91830 |
| results/verify/readiness/stage3/offline-tests.txt | f38015a7ce9a7fb38a443d854d7705dba8e301df9b34af04b809f38b67081c86 |
| results/verify/readiness/stage3/client-framing-tests.txt | 282b31545d88e089ba3959b43e3bb916bb3d398d68a4270b5263af84ebfffe70 |
| results/verify/readiness/stage3/null-family-test.txt | 65083aae1494fb12c88e4a74a8ea325e34cf6c1f1509377a9fc4c7bd3b678b85 |
| results/verify/readiness/stage3/null-family-current-fixture.txt | 38894c35bd4a32cf968c6500d2b1398f9928e32609b6876cf82a0bf53e896099 |
| results/verify/readiness/stage3/null-family-current-context.txt | bb097487affdac1633feee10d24a88d1875ac786a5067399ee481c63f4ee0348 |
