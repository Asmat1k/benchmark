# Этап 3: план первичных свидетельств

Статус: подготовка, до нового сетевого сбора. Это не опубликованные gates и не допуск.

Исходный HEAD f7772cca12efd9bb75055551b87743344fb08a4d, main, чистый checkout; 134 хеша совпали со stage2 release-sources.json. Каталог ниже сокращён до stage3 = results/verify/readiness/stage3; stage2 = results/verify/readiness/stage2-preflight. Проверены collection.py, experiments.py, admission.py, diagnostic_input.py, схемы collections/primary/checks, smoke/measure/cleanup/release scripts и документы verification/experiments.

## Правило происхождения

Каждый predicate получает собственный typed trace JSON (collection_id/gate/id/actual), ссылки path/SHA256 на приведённые журналы, команду, утверждение и фактический результат. Trace включается в observation/check через одинаковую ссылку path/SHA256. Payload, collection, input и report создаются заново с sources() и настоящим ENV из нового timer. Ни одна строка не получает true до проверки перечисленных файлов. Журналы fixture обозначаются synthetic behavior; они не доказывают реальную успешную серию.

Source inventory этапа2 и actual image IDs проверены заново, поэтому его build evidence применим к тем же байтам. Исторические passed reports не используются и hashes в них не меняются. В stage2 build есть CACHED шаги: это существующий проверенный образ, а не новая независимая сборка.

## Карта обязательных predicates

| Gate / predicate | Первичный источник | Проверяемое утверждение |
|---|---|---|
| build/locked-install | stage2 release-build.txt + Dockerfiles + release-sources.json | npm ci, go -mod=readonly, pip --require-hashes; источники и image IDs совпадают |
| build/native-platform | stage3/environment-preflight.json | host arm64, VM aarch64, четыре linux/arm64 |
| build/versions | stage2 release-python.txt/release-os-packages.txt; новый smoke browser.txt/build.txt | фактические версии в тех же проверенных образах |
| build/archive-hashes | stage3/source-archive-preflight.json; sidecar; stage2 archive-verified.json | SHA архива, sidecar, имя и четыре ID совпадают |
| tls/ws-secure | новый smoke/browser.txt | secureContext и точные 3 echo ws-secure |
| tls/wts-secure | новый smoke/browser.txt | secureContext и точные 3 echo wts-secure |
| tls/https-wrong-ca | новый smoke/browser.txt | https: wrong-ca отвергнут с ожидаемой причиной |
| tls/https-wrong-san | новый smoke/browser.txt | https: wrong-san отвергнут с ожидаемой причиной |
| tls/https-expired | новый smoke/browser.txt | https: expired отвергнут с ожидаемой причиной |
| tls/ws-wrong-ca | новый smoke/browser.txt | ws: wrong-ca отвергнут с ожидаемой причиной |
| tls/ws-wrong-san | новый smoke/browser.txt | ws: wrong-san отвергнут с ожидаемой причиной |
| tls/ws-expired | новый smoke/browser.txt | ws: expired отвергнут с ожидаемой причиной |
| tls/wt-wrong-pin | новый smoke/browser.txt | WebTransportError + CERTIFICATE_VERIFY_FAILED |
| tls/wt-expired | новый smoke/browser.txt | WebTransportError + CERTIFICATE_VERIFY_FAILED |
| path/routes | новый smoke/*-route.txt/router.txt/*-net.txt | маршруты обеих сторон через router |
| path/tcp-forward | новый smoke/trace.txt/counters.txt | tcp на to_browser и to_server в обоих In/Out; направление forward |
| path/tcp-reverse | новый smoke/trace.txt/counters.txt | tcp на to_browser и to_server в обоих In/Out; направление reverse |
| path/udp-forward | новый smoke/trace.txt/counters.txt | udp на to_browser и to_server в обоих In/Out; направление forward |
| path/udp-reverse | новый smoke/trace.txt/counters.txt | udp на to_browser и to_server в обоих In/Out; направление reverse |
| path/forwarding-off-ws | новый smoke/forwarding-disabled.txt | forwarding=0; WS rejected/timed_out |
| path/forwarding-off-wts | новый smoke/forwarding-disabled.txt | forwarding=0; WT rejected/timed_out |
| path/offload-mtu | новый smoke/router-links.txt/*-route.txt; timer raw/network_before.json/network_after.json | MTU1500; TSO/GSO/GRO/LRO off на router и endpoints |
| path/profile-readback | новый smoke/r20p0.txt/r20p1.txt/r80p0.txt/r80p1.txt | tc readback каждого из четырёх фиксированных профилей |
| raw/framing | stage3/client-framing-tests.txt; stage2 release-build.txt (go test); новый smoke/browser.txt; timer raw validator | разделённые/объединённые рамки, corrupt/EOF; exact echo всех трёх режимов |
| raw/clock-boundaries | stage3/offline-tests.txt; новый timer raw + clock-samples.json | fixture: inclusive deadlines100/5000, late5000.1; реальные page samples и clock raw |
| raw/slot-accounting | stage3/offline-tests.txt; новый timer raw | fixture: contradictions/late/loss; реальный полный учёт коротких slots/events/server counters |
| raw/hash-integrity | stage3/offline-tests.txt; новый timer SHA256SUMS и validate_raw | все реальные SHA; fixture contradictions после rehash не скрываются |
| raw/log-completeness | stage3/offline-tests.txt; новый timer completion/events/server-log | короткие реальные полные logs; fixture missing journal приводит к STOP |
| raw/resource-coverage | stage3/offline-tests.txt; новый timer resources.jsonl/resource-window.json | реальное покрытие трёх ролей; fixture missing interval/stopped sampler отвергаются |
| raw/replacement-recovery | stage3/offline-tests.txt | только fixture: normal replacement/shared lock/clock violation/missing journal STOP; реальной замены серии не заявляется |
| analysis/metrics-boundaries | stage3/offline-tests.txt | StatisticalTests.test_metrics_deadlines_penalty_and_diagnostics:100/5000/5000.1; p95 1139/1140; null |
| analysis/full-n-sign | stage3/offline-tests.txt | sign references с нулями, полный n; exact enumeration n≤10 и ties n≤6 |
| analysis/holm4 | stage3/offline-tests.txt | [.01,.04,.03,.002]→[.03,.06,.06,.008]; ties [.01]*4→[.04]*4 |
| analysis/rank-intervals | stage3/offline-tests.txt | n20 rank[6,15]/[5,16], n5 infinite; exact binomial coverage |
| analysis/paired-bootstrap | stage3/offline-tests.txt | PCG64 seed20261108,10000 resamples; paired indices; block known answer[0,100] |
| analysis/null-family | stage3/null-family-current-context.txt; docs/readiness/stage3-null-fixture.py | новая synthetic fixture: все4 profiles, null→p1 placeholder/unavailable/fullness failed; WT-D null; mixed release rejected |
| analysis/offline-reference | stage3/offline-tests.txt; src/analysis/fixtures/references.json | все prespecified sign/Holm/bootstrap references |

Дополнительная обязательная проверка: WT-D exactFrames=3 в новом smoke/browser.txt; supported=false не закрывает этап.

## Timer и публикация

После успешной предметной проверки smoke: SERIES_TLS_DIR=/Users/dobrov/Desktop/Code/ITMO/benchmark/build/series-tls-stage2._n__udb0; caffeinate -ims sh docker/collect-diagnostic.sh timer. Исторически около67с, два коротких D3 run, подготовка/стабилизация до30с на run; с учётом фактического smoke повторно оценить предел5мин. Не запускать generator. Реальные context до/после обязаны совпадать; при конфликте сохранить STOP, ENV вручную не чинить.

Timer: 100001 performance.now samples,100000 delta, finite/monotonic, positive step≤0.1мс и nearest-rank p99≤0.1мс. Проверить обе D3 raw папки полностью через diagnostic_raw/validate_raw, SHA256SUMS, ledger complete, сертификат и sources. Штатный diagnostic_input и experiments.py timer создают report. Только его точный environment.path/SHA используется для остальных пяти gates.

Затем штатный experiments.py import-checks --kind real для пяти новых inputs; глубокая повторная валидация каждого отчёта через admission в make verify. REPORT_MAP отображает gate→путь report; make verify ARGS="--kind real --input REPORT_MAP --environment ENV --output NEW_VERIFY". Критерий: первые6 passed, calibration/generator/aa/monitoring not_run, exit2 и final=false. Freeze не создавать.

## Команды и результаты до сети

- sh docker/check-release.sh HEAD:0; sh docker/release-state.sh:0,134 files.
- shasum -a256 -c sidecar:0, archive 1202140160bytes, SHA05a30d9c5e341462c167a548a5942bc377e5c48de2aee0badb5db3301203a11e; дополнительная независимая hashlib сверка:0.
- docker image inspect/info/network inspect/ps; df -h (host/VM); pmset -g batt; openssl x509 -dates -fingerprint -sha256: сохранены environment-preflight.json. 2vCPU/4109484032bytes, native arm64, host118GiB/VM37G свободно; лабораторные подсети свободны. series.py hold с EOF: locked,0, освобождён. Чужой ai-grepa-qdrant-1 сохранён.
- Docker analyzer без сети, unittest -v: StatisticalTests (5), MeasurementTests.test_r1_contradictions_after_rehash/test_r1_valid_loss_late_disconnect/test_r2_sampler_stops_and_missing_interval/test_r3_series_context_and_after_readback/test_r5_evidence_and_normal_replacement/test_r6_recovery_and_shared_lock и RecoveryTests.test_complete_clock_violation_keeps_replacement_route/test_missing_journal_and_expiry_take_actual_stop_cleanup. 13tests,1.960s,OK. Журнал offline-tests.txt.
- Отдельный штатный SeriesTests.test_null_profiles_and_mixed_release_are_not_silently_removed:1test,1.007s,ERROR protocol/config hash. Причина: make_fixture наследует protocol_sha256 старого raw template. Исторический raw и исполняемый релиз не изменялись. Отказ сохранён null-family-test.txt. Первый отдельный fixture wrapper задавал только текущий protocol_sha256; он остановился на environment changed: context (1.477s), журнал null-family-current-fixture.txt. Окончательный docs/readiness/stage3-null-fixture.py обновляет protocol_sha256 и пересчитывает context_snapshot только новой временной явно synthetic fixture. Тот же штатный тест:1test,11.182s,OK, журнал null-family-current-context.txt. Исторический ENV не менялся; synthetic context не применяется к real reports.

## Пользовательский запуск smoke

Оценка2–5мин плюс setup; превышение5мин исключить нельзя. Запускает пользователь, весь smoke целиком. Подключить AC, оставить крышку открытой. Последняя проверка питания в16:40UTC показала Battery Power,100%; раннее AC наблюдение уже не актуально. TLS до2026-11-26T16:22:37Z, pin fc2a5f4d7bc0fce861baee9207c82ff86bf502fda419cf45c73e3559d1a56d18; при задержке пересчитать восьмидневный резерв.

```sh
cd /Users/dobrov/Desktop/Code/ITMO/benchmark
python3 docs/readiness/stage3-smoke.py
```

Этот отдельный упаковщик вне executable source inventory вызывает ровно caffeinate -ims sh docker/smoke.sh с постоянным SERIES_TLS_DIR; сохраняет execution.json (команда/HEAD/helper SHA/время/exit/leaf before-after), smoke.txt и SHA256SUMS в новом stage3/smoke-run-UTC. Штатный smoke сохраняет результаты в results/verify/path/wswt-smoke.XXXXXXXX; путь попадёт в execution.json. Подготовка без сети проверяет чистый HEAD/release-state, AC, pin,8суток leaf и свободный lock. Не повторять автоматически при отказе. Упаковщик не публикует predicates: exit0 требует дальнейшей проверки десяти TLS,девяти path,WT-D и cleanup.json. После результата продолжить timer и публикацию. Логическая фиксация подготовки не меняет134 release hashes; после коммита обновить release-state.

Клиентские тесты: извлечён /page из неизменённого server image командой docker run --rm --network none --entrypoint tar wswt-bench-server:dev -C /page -cf - .; текущий src/client/test.mjs скопирован в отдельный build/stage3-client. Выполнен docker run --rm --network none --entrypoint node -v "$PWD/build/stage3-client:/fixture:ro" wswt-bench-browser:dev --test /fixture/test.mjs. 9tests,9passed,151.952084ms. Только injected clocks/synthetic transport; журнал client-framing-tests.txt. В18:27:43UTC (21:27:43МСК) повторно подтверждены AC Power,100%,charged.
