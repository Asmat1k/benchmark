# Этап 3: шесть реальных gates и частичный verify

Статус: **этап 3 завершён**. Build/TLS/path/timer/raw/analysis — passed. Calibration/generator/aa/monitoring — not_run. Штатный make verify вернул **exit2**, final=false именно из-за четырёх отсутствующих последующих gates. Это частичная проверка; допуска A/A, pilot или main нет. Freeze отсутствует.

Дата:13 ноября 2026. Сборы выполнены примерно21:29–21:32МСК. Qualification, bandwidth, calibration, generator, A/A, monitoring, pilot и main не запускались.

## Релиз и применимость

Начальный HEAD:f7772cca12efd9bb75055551b87743344fb08a4d,main,чистый. Подготовка:1879620e25ec990c394a9d8785b00e3d5c20d85d. **Релиз реальных smoke и D3:1879620e25ec990c394a9d8785b00e3d5c20d85d**, чистые исполняемые исходники. Evidence и отдельный упаковщик сохранены коммитом53c85c7. Заключительный документальный коммит следует после этого файла; его точный HEAD и release-state SHA находятся в `build/stage3-final-state.json` после штатного обновления release-state. История не переписывалась.

Все134 release source hashes неизменны относительно этапа2. Новый инструмент `docs/readiness/stage3-primary.py` находится вне executable inventory; его SHA включён в каждый primary trace и замкнутую integrity отчётов. Он проверяет фактические источники и готовит typed inputs; штатная публикация выполняется experiments.py. Исполняемый релиз, зависимости, thresholds, ресурсы, режимы и методика не менялись; пересборка не требовалась. preliminary=false сохранено, это не freeze. Последующие документальные коммиты не меняют source-bound применимость этих шести отчётов.

| Образ (native linux/arm64) | Фактический image ID |
|---|---|
| wswt-bench-server:dev | `sha256:c2c60585a64d04e8dd7dd6a674625c0aec44cdc385561c8864dab734fbf19c44` |
| wswt-bench-browser:dev | `sha256:356b2e1af8773aaf688f3c4e03bbfa73b2c835d88be0a76278030cf55d1c1641` |
| wswt-bench-router:dev | `sha256:d78a80d31724881c1adaa57005fae37f4f23e0013945dac759d7ee1f76b6b74d` |
| wswt-bench-analyzer:dev | `sha256:9e263785dc135db52a216bc358c38218cf3d98f178a9981a365ca79cda7cbd62` |

Архив:`results/archives/images-05a30d9c5e341462c167a548a5942bc377e5c48de2aee0badb5db3301203a11e.tar`,1202140160bytes,SHA256=`05a30d9c5e341462c167a548a5942bc377e5c48de2aee0badb5db3301203a11e`. Имя/sidecar/байты проверены заново; ранее проверенные состав архива/загрузка применимы к тем же134 источникам и фактическим IDs. Исторические built IDs images.lock не использовались как текущие. Существующая кешированная сборка раскрыта в build trace; это не независимое воспроизведение.

## TLS, ресурсы и календарь

Постоянный SERIES_TLS_DIR:`/Users/dobrov/Desktop/Code/ITMO/benchmark/build/series-tls-stage2._n__udb0`. DER SHA256/good pin:`fc2a5f4d7bc0fce861baee9207c82ff86bf502fda419cf45c73e3559d1a56d18`. notBefore2026-11-13T16:22:37Z; фактический notAfter**2026-11-26T16:22:37Z (26 ноября19:22:37МСК)**. PEM SHA до/после smoke и timer:`ff69b4145dbd13f610506b4c5324ed515b5d58dd5556c81ff087cf845a0933b9`. Leaf не заменялся, старый series-tls.PMYktiWa не использовался, приватных ключей в evidence нет.

Docker2vCPU/4109484032bytes, native arm64. Лимиты фактических сервисов — в неизменённом ENV. Host118GiB/VM37G свободно при preflight; лабораторные подсети свободны перед запуском. Measurement lock получен/освобождён до и после; последние проверки AC Power,100%. Настройки сна не менялись, сетевые команды выполнялись с caffeinate -ims. В момент сбора оставалось почти13суток TLS, рекомендованный резерв6дней+2суток соблюдался. Конкретные даты этапов4+ не назначены; перед продолжением заново проверить AC,UTC,leaf horizon и календарный план. При смене leaf/ENV/исходников применимость gates проверяется заново.

## ENV и опубликованные файлы

Все пути в таблице — от `/Users/dobrov/Desktop/Code/ITMO/benchmark`. ENV получен штатным D3 на реальных сервисах; не скопирован из прежнего опыта и не собран из ожидаемых параметров. Этот исходный файл должен оставаться по своему пути.

| Артефакт | Точный путь | SHA256 |
|---|---|---|
| ENV | `results/verify/diagnostic/timer-timer.2ST8NYBU/context.json` | `231ae4819874cf877f8e2234b4331171309906cb4c259b847c7ff8fc403039da` |
| build | `results/verify/readiness/stage3/reports/build.json` | `625ea949f84c28e11e074149178f0584160cf31bb9ad987b28bb6fe7c8e1c766` |
| tls | `results/verify/readiness/stage3/reports/tls.json` | `ed488823cb3a1628274c3b7c703cf3310f93a2a668120b1ff17f3b91cfb16da2` |
| path | `results/verify/readiness/stage3/reports/path.json` | `9523a7f08709775b3f2d53586392be78970a96dbdd878eb78f26c16ff6c4432b` |
| timer | `results/verify/diagnostic/timer-timer.2ST8NYBU-report/report.json` | `814e249999a62eb9dcce49e98af595b12fdd73933761da1d4738c41d0e375fda` |
| raw | `results/verify/readiness/stage3/reports/raw.json` | `5db9773b62c32f01d92fab4a84b4137ef64ef0f703b240f414e36161a62d2cc5` |
| analysis | `results/verify/readiness/stage3/reports/analysis.json` | `5ef267c5a0192e62c16cafac47efa29e2861194dde15dd4e46ebd1f287f16d9d` |
| REPORT_MAP | `results/verify/readiness/stage3/REPORT_MAP.json` | `f6df38e2725bdd5d569ccb4efbf0c8c70fab82d5bc032fb9dcfaebe6f564a56d` |
| verify | `results/verify/readiness/stage3/verify-partial-real.json` | `d814359d5c4cab2534ac361b351473a22dadeac3084e4413b18f4f6ea514d9f9` |

Source inventory134 — `results/verify/readiness/stage3/source-inventory.json`,SHA256=`71efbe891b780d73946b9e7cea0f38f54c28b65253557c9133159d26a7f91830`. Во всех отчётах source_hashes одинаковы,environment.path/SHA точно совпадают с timer. Полный verify повторно проверил каждую первичную collection/observation/check/trace и научные timer данные, а также замкнутую integrity.

## Команды, длительности, результаты

| Команда | Секунды | Exit |
|---|---:|---:|
| caffeinate -ims sh docker/smoke.sh (пользователь) |16.396|0|
| caffeinate -ims sh docker/collect-diagnostic.sh timer |68.907|0|
| import-checks build | 3.574 | 0 |
| import-checks tls | 0.858 | 0 |
| import-checks path | 1.178 | 0 |
| import-checks raw | 0.979 | 0 |
| import-checks analysis | 1.072 | 0 |
| make verify --kind real, частичный |6.171|2|

Smoke: `results/verify/path/wswt-smoke.wXwojaYN`. Журнал и точные параметры пользовательского запуска:`results/verify/readiness/stage3/smoke-run-20261113T182944Z/`. Подтверждены secureContext,WS handshake101,exactFrames=3 для WS/WT-S/WT-D,WT-D supported=true; все10 TLS predicates; TCP/UDP в обе стороны через оба router интерфейса; WS/WT-S timed_out при forwarding=0; маршруты,MTU1500,TSO/GSO/GRO/LRO off; четыре tc readback,seed20261108/20261109,jitter/correlation0,limit1000,10Mbit/s accounting. Это readback, не bandwidth/calibration.

Timer журнал:`results/verify/readiness/stage3/timer-execution/`.100001finite исходных clock_samples,100000delta,монотонность=true,positive step=0.09999999403953552мс,p99 overhead=0мс. Оба raw `b0-a0-m0` и `b0-a0-m1` полностью провалидированы,1warmup+3measurement slots каждый,ledger complete,context до/после совпадает. Штатный timer payload содержит samples первого run; collection-sources.json создаётся только для этого timer run. Второй run проверен через validate_raw,attribution/context/schedule и тот же чистый release commit,без требования отсутствующего по контракту timer snapshot. Сбой первой версии отдельного упаковщика,ошибочно потребовавшей этот snapshot у второго run,сохранён `primary-preparation.txt`; сам коллектор и timer не отказывали,повторного сетевого запуска не было.

Точные argv и времена пяти публикаций:`publication-execution.json`;шаблон:

```sh
docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 -v "$PWD:/bench" -w /bench wswt-bench-analyzer:dev python -B src/analysis/experiments.py import-checks --kind real --input results/verify/readiness/stage3/primary-real-01/GATE/input.json --environment results/verify/diagnostic/timer-timer.2ST8NYBU/context.json --output results/verify/readiness/stage3/reports/GATE.json
make verify ARGS="--kind real --input results/verify/readiness/stage3/REPORT_MAP.json --environment results/verify/diagnostic/timer-timer.2ST8NYBU/context.json --output results/verify/readiness/stage3/verify-partial-real.json"
```

Команды выше документируют уже выполненные операции,повторять их с теми же immutable output paths нельзя. Подготовка primary: `python -B docs/readiness/stage3-primary.py results/verify/path/wswt-smoke.wXwojaYN results/verify/diagnostic/timer-timer.2ST8NYBU-report/report.json results/verify/readiness/stage3/primary-real-01` в текущем analyzer без сети. Источники/план до сборов:[stage3-evidence-plan.md](stage3-evidence-plan.md).

Offline:13 адресных Python tests,1.960s,OK;9клиентских framing/clock/slot tests на встроенном /page из текущего server в текущем browser image,151.952084ms,OK. Null-family исходный тест отказал из-за устаревшего protocol hash fixture; первая временная адаптация отказала на context; окончательная новая явно synthetic fixture с актуальными protocol/context прошла тот же тест за11.182s. Все отказы сохранены;исторические inputs не изменялись. Mock executor не используется как свидетельство реального успеха. Численные references,full-n sign с нулями,Holm4,rank intervals,paired bootstrap,null-family и metric boundaries проверены fixture assertions. Реальная performance generator этими проверками не подтверждается.

## Связь predicates с первичными свидетельствами

Каждый trace содержит collection_id/gate/id/actual,scope,command,наблюдённый результат и files[{path,sha256}],а также SHA упаковщика и inventory. Payload observations и checks ссылаются на один и тот же trace. Real short raw проверяет фактические инварианты;fixture edge/recovery/statistical behavior явно раскрыт в scope. Evidence этапа2 переиспользовано только для идентичного build,а старые passed reports не перепривязывались.

| Gate/predicate | Результат | Typed trace | SHA256 trace | Область доказательства |
|---|---|---|---|---|
| build/locked-install | passed | `results/verify/readiness/stage3/primary-real-01/build/locked-install.json` | `f476d930c72a67a70805dcc022c69b84b5b0b63231333b6cea7c1d8e859ec064` | stage2 build reused after exact 134-source and actual image-ID comparison; cached steps disclosed |
| build/native-platform | passed | `results/verify/readiness/stage3/primary-real-01/build/native-platform.json` | `cab6ec513dc3d8a80ccebd7609da09c4cb62fb08d40ecbc1a37f5f3f73b0aca9` | actual host, Docker and unchanged release images |
| build/versions | passed | `results/verify/readiness/stage3/primary-real-01/build/versions.json` | `b3f0c01ed941fd3a8e72bd9fb522ccaac70d3bc2e74ebf807a344d106669c303` | current browser runtime plus unchanged image package inventory |
| build/archive-hashes | passed | `results/verify/readiness/stage3/primary-real-01/build/archive-hashes.json` | `6f338ad41ae83f61ae4874575a6f6a681c413cb9333795e720a64aae0dbda0c0` | current archive bytes/sidecar and applicable stage2 archive content validation |
| tls/ws-secure | passed | `results/verify/readiness/stage3/primary-real-01/tls/ws-secure.json` | `1aaa206e9b5cd781ebbc34adafdeadb9fabf5ffee6de91848458ccc8f09e2c09` | real browser TLS and exact echo |
| tls/wts-secure | passed | `results/verify/readiness/stage3/primary-real-01/tls/wts-secure.json` | `deff4aef71bfc89dbab2d3a31488a863030b5cabde0911fad7a0aef975130539` | real browser TLS and exact echo |
| tls/https-wrong-ca | passed | `results/verify/readiness/stage3/primary-real-01/tls/https-wrong-ca.json` | `14afb11bbd018c5c1d9a9694af56a176c227bc661707e0663f792ad0189f3179` | real negative TLS probe with specific certificate error |
| tls/ws-wrong-ca | passed | `results/verify/readiness/stage3/primary-real-01/tls/ws-wrong-ca.json` | `716674f31fe185c7b19b4d0739d6a9d30c93e5c5fe6756d1af39cb3dda088647` | real negative TLS probe with specific certificate error |
| tls/https-wrong-san | passed | `results/verify/readiness/stage3/primary-real-01/tls/https-wrong-san.json` | `8bf7cd497a07ca09462b578aa68f334dc81b42eea616ebdd8ef3792c255bae0f` | real negative TLS probe with specific certificate error |
| tls/ws-wrong-san | passed | `results/verify/readiness/stage3/primary-real-01/tls/ws-wrong-san.json` | `d3522a3be6e12ff2c36ae1ddc6b7b17ddc187829a1bb6e1d147fae8f538bdae8` | real negative TLS probe with specific certificate error |
| tls/https-expired | passed | `results/verify/readiness/stage3/primary-real-01/tls/https-expired.json` | `97fc12e5e2ffd155f1fc104a913584aa389199b69a32a0855dec5f09d493b879` | real negative TLS probe with specific certificate error |
| tls/ws-expired | passed | `results/verify/readiness/stage3/primary-real-01/tls/ws-expired.json` | `923ba42900deb18c6d22033f5be78c4a866e48d26dffcaf78a8034908d0f674a` | real negative TLS probe with specific certificate error |
| tls/wt-wrong-pin | passed | `results/verify/readiness/stage3/primary-real-01/tls/wt-wrong-pin.json` | `2f09f3459761609c3bb299e3b980f467760ee353c4ddc3046f0530b723ea40f8` | real WebTransport negative TLS probe |
| tls/wt-expired | passed | `results/verify/readiness/stage3/primary-real-01/tls/wt-expired.json` | `f5e8988f62627e6359edf26c9dc7abf53fc7ea98300f8f51428524b683eb3258` | real WebTransport negative TLS probe |
| path/routes | passed | `results/verify/readiness/stage3/primary-real-01/path/routes.json` | `62dee322bf520d0d642610594414a5ed02f573c7a3add7724a744496dd8f5204` | real route readbacks |
| path/tcp-forward | passed | `results/verify/readiness/stage3/primary-real-01/path/tcp-forward.json` | `d5a79619b34481f3bf1cc664f7a11d35f1fcd4f021ac8c5c606da366fb063c8f` | real router packet capture on both interfaces |
| path/tcp-reverse | passed | `results/verify/readiness/stage3/primary-real-01/path/tcp-reverse.json` | `88d023ab1bee1c8fece0e7e9521d9b38be93a838607e89af0f4cc6269ab7376d` | real router packet capture on both interfaces |
| path/udp-forward | passed | `results/verify/readiness/stage3/primary-real-01/path/udp-forward.json` | `1e59106c1f335b1b3d59990bcd7e863b4c7c805deecb9c60c6a5e73b11b18699` | real router packet capture on both interfaces |
| path/udp-reverse | passed | `results/verify/readiness/stage3/primary-real-01/path/udp-reverse.json` | `f7a307c9ed97050e525db90aa7f04d5b408681468b5b49a782be80c84555eed4` | real router packet capture on both interfaces |
| path/forwarding-off-ws | passed | `results/verify/readiness/stage3/primary-real-01/path/forwarding-off-ws.json` | `4e3239608b3478822a5d426a64cc175e2b850ed5a6744d239a1a46694edf06a3` | real forwarding-off probe |
| path/forwarding-off-wts | passed | `results/verify/readiness/stage3/primary-real-01/path/forwarding-off-wts.json` | `dd517dd408e2ff36fda9756d1fbd095f6979d3d3fc0c2489b3048f37586d890c` | real forwarding-off probe |
| path/offload-mtu | passed | `results/verify/readiness/stage3/primary-real-01/path/offload-mtu.json` | `2fa281ceb310624731903eb5ff7accb8b0c1fe47ab6ceb5a6a49be5fcc1a732f` | real D3 before/after endpoint and router readbacks; validate_raw also checks |
| path/profile-readback | passed | `results/verify/readiness/stage3/primary-real-01/path/profile-readback.json` | `4ae968f9b3112d74f8bfd15fa3ec73c08f009154a05d7dd8c97758f423852b1e` | real four-profile tc readbacks; no bandwidth/calibration claim |
| raw/framing | passed | `results/verify/readiness/stage3/primary-real-01/raw/framing.json` | `2e92e92d90c5a00e9f3b5fc4c132aaabb1136c289de963aca7ae4d5952b8eb92` | real three-mode smoke and short raw; framing edge cases use synthetic client transport |
| raw/clock-boundaries | passed | `results/verify/readiness/stage3/primary-real-01/raw/clock-boundaries.json` | `ccf1956aa2a200c3c9dd7588adc3083546b9b9a6b07dc3343189c9b5bd27d4d4` | real raw clock invariants; exact deadline/late edges use injected fixture clocks |
| raw/slot-accounting | passed | `results/verify/readiness/stage3/primary-real-01/raw/slot-accounting.json` | `944958fb7821e86fa540618337ba95760f619b043ce2013958429cb3337faaea` | real short slots/events/counters; missed wakes/loss/late/disconnect use fixtures |
| raw/hash-integrity | passed | `results/verify/readiness/stage3/primary-real-01/raw/hash-integrity.json` | `e960ca7a37ec03e086ec7a25537601c6eae9464fdd49daa8db3af57026ced309` | real full raw hash validation plus tampered temporary copy rejected |
| raw/log-completeness | passed | `results/verify/readiness/stage3/primary-real-01/raw/log-completeness.json` | `ee60fff896f5a38471b20455e2ff06113ad01fd4f10d42c9d946a564a600f747` | real completion/events/server logs; missing-journal STOP uses fixture |
| raw/resource-coverage | passed | `results/verify/readiness/stage3/primary-real-01/raw/resource-coverage.json` | `52b5de7bcda191385ba943de6b100d8b7955ab2f0cc788938c4dd4a5e2ea1198` | real three-role resource windows; missing intervals use fixtures |
| raw/replacement-recovery | passed | `results/verify/readiness/stage3/primary-real-01/raw/replacement-recovery.json` | `deb6f03569696c66c5324bf5c7235b3509f58dbc374631f65003d930f083cb40` | fixture behavior only: replacement, lock and recovery; no successful real series claimed |
| analysis/metrics-boundaries | passed | `results/verify/readiness/stage3/primary-real-01/analysis/metrics-boundaries.json` | `45faded4df092d914eae7a3abc84d31036a380472d6dcbf576e7c79a100a7d37` | offline numerical known-answer fixture, no network performance claim |
| analysis/full-n-sign | passed | `results/verify/readiness/stage3/primary-real-01/analysis/full-n-sign.json` | `97bb707f2cbc03d733ce1bed38bdefc36f5aef822c390b608de0b36e66c1754b` | offline numerical known-answer fixture, no network performance claim |
| analysis/holm4 | passed | `results/verify/readiness/stage3/primary-real-01/analysis/holm4.json` | `a69bc2dff442e4112ad66a3b7e78adad871c598298db63855caa135d5b36edc8` | offline numerical known-answer fixture, no network performance claim |
| analysis/rank-intervals | passed | `results/verify/readiness/stage3/primary-real-01/analysis/rank-intervals.json` | `e58f9bfb2f79634297b0cc07403fed82bcc90526ab49940f22eac876b233cf4b` | offline numerical known-answer fixture, no network performance claim |
| analysis/paired-bootstrap | passed | `results/verify/readiness/stage3/primary-real-01/analysis/paired-bootstrap.json` | `18deaa0752140d4117786d4fea84615d880cdd3054529339325853dc1fbe2454` | offline numerical known-answer fixture, no network performance claim |
| analysis/offline-reference | passed | `results/verify/readiness/stage3/primary-real-01/analysis/offline-reference.json` | `01dbbc7a5c50189f5e64134cdfd0a38ca661889e7212e00bdc00c467f7a6e3e4` | offline numerical known-answer fixture, no network performance claim |
| analysis/null-family | passed | `results/verify/readiness/stage3/primary-real-01/analysis/null-family.json` | `698fe7d37e95fd49cb5f37b3134badebbb15936eebd6d8cf978bb9a44a6b5028` | new temporary SYNTHETIC fixture with current protocol/context; original failures retained |


## Очистка и сохранность

Штатный smoke cleanup.json:0containers/0networks. После timer отдельно проверены точные Compose labels трёх собственных проектов:wswt-d2-wswt-smoke-wxwojayn,wswt-d3-wswt-measure-jgdedue0,wswt-d3-wswt-measure-tvuzukyh. Остатков контейнеров/сетей нет;measurement lock свободен. Первичные записи:`final-cleanup-tls.json`,SHA256=`311bde3a221904ee10edab787706fab5259899a336834b1b41915253d94abdd4`. Чужой ai-grepa-qdrant-1 продолжает работать(unhealthy),прежние чужие сети сохранены. Его влияние на performance и стационарность оценивается будущими gates.

Исторические raw,seals,source snapshots,reports и stage2 evidence не менялись;добавлены только новые evidence и отдельные инструменты/документы. SHA smoke и обоих D3 raw перепроверены: `collected-checksums-validation.txt`. Исходный preparation SHA256SUMS относится к снимку документов внутри неизменённого `results/archives/stage3-preparation-evidence.tar.gz`;последующая редакция этого handoff не переписывает исторический пакет подготовки.

## Пакет и точка продолжения этапа 4

Итоговый пакет:`results/archives/stage3-final-evidence.tar.gz`,контрольная сумма рядом `.sha256`. Состав и SHA каждого текущего файла:`results/verify/readiness/stage3/final-SHA256SUMS`. Пакет содержит новые real raw,primary collections/inputs/traces,reports,ENV,REPORT_MAP,verify,журналы,подготовительные evidence,нужные транзитивные build/test источники и эту передачу. Уже проверенный1.2GB архив образов остаётся отдельным неизменённым файлом по прежнему пути;он указан в `external-evidence.json` с SHA и входит в final-SHA256SUMS. Приватные ключи исключены. Итоговый post-commit state:`build/stage3-final-state.json`.

Продолжать в отдельном чате этапа4 с этой передачи и настоящего ENV. Сначала повторно проверить HEAD/cleanliness,release-state,134hashes,IDs,AC/диск/подсети/lock/TLS horizon. Открыты qualification/bandwidth и calibration/generator/A/A/monitoring согласно ранее согласованной последовательности;их здесь не запускали. n выбирается позже,main budget15ч не менялся. Не считать этот partial verify полным допуском. На этом этапе3 остановлен после требуемого результата.
