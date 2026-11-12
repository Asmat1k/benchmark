# Передача D5

Исходный main commit `06b6174319d26dce95f17fb8e4f94ececd06aa8c`. На входе только пользовательский untracked .agents/plan/, который не менялся. Исполнитель `/root/dev_wave_5_implementer_routed`, requested `gpt-6.1-sol`/`high`; фактически подтверждённые model/effort неизвестны. Ранее ошибочно назначенный исполнитель не менял репозиторий. Прочитаны исходное поручение, полный план, AGENTS.md, D0–D4 handoffs и независимая приёмка D4. Принятые научные пороги D0–D4 сохранены.

## Результат

- `src/analysis/acceptance.py`: timer/UDP calibration/rank intervals/binomial loss/rate/generator и независимые AA/monitoring schedules/equivalence/bootstrap, барьеры полноты и dependence diagnostics. Calibration и generator предоставлены как необходимые вычислительные модули приёмки реальных первичных наблюдений. Они не выполняют реальную диагностическую сборку UDP/traces автоматически и не подставляют netem-настройки вместо измерений.
- `power.py`: complete fixed n20/30/40/60 × shifts0/±5 ×10000 sign/Holm4 simulations; residuals, MC intervals, CI widths/coverage и явные sensitivity assumptions ties/dependence/rare failures.
- `admission.py` и `experiments.py`: evidence SHA, exit0/1/2, absent→not_run/deferred_by_user, отдельные synthetic/real reports, повтор расчёта gates из связанных входов, stage prerequisites, official pilot, final verify/freeze/main guards. Main повторяет полный freeze validator; clean Git source inventory, версии/config/environment/leaf DER/certificate period, fixed modes/n, AA tolerances, pilot/power/final verify и независимая reproduction обязательны.
- `docker/experiment.sh` и Make interfaces: host Make/Docker orchestration без новых host Python dependencies. Analyzer admission/расчёты выполняются до/после измерений без сети. D3 run_spec допускает реальные future phases только по admission; mutable queue/ledger перечитываются, exit3 replacement сохраняет возможность продолжения. Immutable original schedule допускает только доказанные append replacements через D3 audit/transaction.
- D3 monitoring расширен узко: один и тот же режим и два seeds внутри пары; on/off случайны заранее. Для off остаются baseline/контекст/стабилизация и pre/post cumulative OOM safeguards. Sampler окна выключен, monitoring-window честно фиксирует недоступность ресурсных метрик окна; нулевые ресурсы не подставляются. Обычные D3 raw проверки сохранены.
- `docs/experiments.md`, README и execution matrix описывают входы, реальные prerequisites, контроль происхождения, ограничения и точный порядок будущего этапа. Freeze schema расширена явными обязательными D5 provenance/rationale/certificate полями; полный документ проверяется без отбрасывания дополнительных полей.

## Проверки

[Evidence](../../results/verify/acceptance/development/) содержит host/locked тесты, D0 schema validation и D3 regressions. Host acceptance13/13 прошли. Locked acceptance13/13 прошли. Итоговый совместный locked suite32/32 (13 новых +19 D3 measurement/recovery) прошёл; окончательный targeted acceptance после добавления reproduction guard отражён в final-acceptance.txt. Изменения исходников во время одного раннего параллельного locked запуска корректно закрыли guard source mismatch; эта диагностическая попытка сохранена в tests-locked.txt до итогового повтора. Ранний D3 прогон18/19 выявил несовместимый тип ошибки при отсутствующем admission; исправлено на явный ValueError/admission, итоговые19/19 прошли.

Тесты проверяют численные границы, null и bootstrap, loss0 и reverse-ID denominator, random on/off и seed equality, full-n sign/Holm4 power, exit0/1/2, synthetic/stale/modified evidence refusal, full freeze constraints и прямые подмены, positive main с dependency-injected certificate/release, actual host shell со stub commands и deliberate replacement pause. Зависимости scientific gate коллектора и certificate/release явно подменяются только в изолированных тестах; реальные guards от этого не получают passed. D4 графики и старые raw не менялись и не пересоздавались.

Docker-тесты использовали --rm --network none. Реальный сетевой трафик не создавался; calibration/saturation/generator20/100/длительные AA/monitoring/official pilot/power на pilot/final verify/freeze/main не запускались. Действительный `configs/freeze.json` отсутствует. Контейнеры тестов завершены; чужой ai-grepa-qdrant-1 не трогался. Источники и evidence связывает checks.json/SHA256SUMS. Коммит не создавался; независимый reviewer решает приёмку, затем commit делает координатор.

## Вход D6

Независимо проверить сборку и установку зависимостей, offline tests, будущие guards и документацию; при необходимости короткий smoke в разрешённом бюджете. В D6 не запускать отложенную экспериментальную приёмку. Для следующего отдельного этапа последовательно выполнить реальные сборы/приёмку среды, timer/network/loss/rate/generator, AA, monitoring, official pilot и power; обосновать окончательные n/durations/tolerances и WT-D decision; при изменениях повторить затронутые gates, затем final verify/freeze и независимую experimental reproduction. После этого main требует отдельного разрешения. Полная инструкция и контракты входов — [experiments.md](../experiments.md).

Все экспериментальные строки матрицы остаются not_run/deferred_by_user. Разработка не подтверждает точность сети/часов, пропускную способность, устойчивость генератора, iid, эквивалентность, мощность или выигрыш транспорта. Остаточный эксплуатационный риск: повторная строгая валидация полного evidence перед каждым прогоном требует времени до начала измерений; её фактический overhead ещё не измерялся. Проверки checks, trace review и независимости units предполагают добросовестные первичные сборы и документированное экспертное решение, а не криптографическое удостоверение происхождения наблюдений.

## Исправления после первого независимого ревью

Первая рецензия вернула R1–R10. Ниже ответы исполнителя; закрытие определяет повторный независимый reviewer. Прежние журналы tests-host/tests-locked/final-locked описывают историю до этих исправлений и не являются доказательством новой версии. Финальные артефакты исправлений находятся в development/recheck/.

| Замечание | Исправление и проверка |
|---|---|
| R1 | JSON-native identity/shifts; comparison нормализован JSON roundtrip. Реальные файловые CLI synthetic calibration/AA/monitoring → сохранённый report → unmocked validate_gate проходят; изменение числа отклоняется. |
| R2 | Явные per-gate PRIMARY_IDS, collection/payload/observation/trace identity и hashes, exact evidence association и actual context. Synthetic ENV и нерелевантные development summaries больше не подходят real aggregate. Timer пересчитывается по100001 clock samples; generator — по slots/resource samples. |
| R3 | Git остаётся на хосте: git archive HEAD → краткий network-none analyzer → release-state snapshot. Контейнерный release() сверяет tree hashes без Git. Dirty ограничен исходными путями; generated results/foreign plan не влияют. Host boundary проверяется в отдельном временном Git-репозитории. |
| R4 | Pilot/power subject проверяется по ключу binding; их source pilot schedule должен совпасть. Inventory сравнивается по точному составу файлов и hashes. Полное покрытие выбранных режимов/профилей обязательно до pilot/main. |
| R5 | Точная выводимость всего current.runs; ledger metadata/statuses, queue и deterministic replacement insertions реконструируются из исходного schedule и transaction. Published membership и phase/path проверяются до executor. |
| R6 | Полный D4 validator расширен параметром дизайна с прежним comparison default; официальные reports проверяют admission, original plan, release, context, folder/run identity и synthetic markers. Явно synthetic fixture path изолирован от рабочего results и не допускается real executor/freeze. |
| R7 | Тот же полный D4 audit/replacement validator применяется к AA/monitoring. Расчёт и evidence используют active selected; quarantined originals сохраняются и проверяются в audit. Файловый тест выполняет CLI diagnose→replace и отчёты на полных320+320+40 synthetic raw. |
| R8 | Полные10000 sent IDs и100Hz timing, reply ID/RTT correspondence, forward/reverse ingress/drop/survivor relation по отдельно обозначенным collection. Generator проверяет100Hz grid фактических slots; отрицательные измерения и несогласованные resource summaries отвергаются. |
| R9 | Leaf/series_end должны покрывать минимум80с×оставшиеся runs; freeze учитывает все runs, продолжение — только оставшиеся active с заменами. Дополнительный startup overhead остаётся предметом будущего pilot budget. |
| R10 | Случайный порядок только внутри каждой из четырёх непрерывных сессий с балансом mode/profile. |

Исправления не выполняют реальные экспериментальные gates и не создают действительный freeze. Новые наборы явно искусственные; положительные calculations/verification fixtures используют kind=synthetic. Рабочие real guards не считают их успешной экспериментальной приёмкой. Global mocking validate_gate исключён из нового набора. Сетевой executor подменяется только в отдельной проверке deliberate pause; предметные CLI/report/audit paths исполняются штатно.

## Итог второй итерации исправлений, 12.11.2026

Дополнительные R2a/R5a/R7a/R8a/R9a/R11 из02-recheck.md реализованы. Publication сверяет CLI/input kind, ENV/source до записи; measured primary invariants исполняются при публикации. Ранний raw проверяется по identity, обязательным файлам, SHA, schema/completion1200; quarantine без child/proof не допускается. Парные наблюдения идут в хронологии selected, включая срединную замену. Генератор требует согласованные состояния/полные invocations и ресурсы на всё окно; реальные API failures остаются failed. notBefore сравнивается с текущим временем отдельно от минимального бюджета, тест использует фиксированное UTC.

R11 разделяет полный научный пересчёт при публикации/полном verify и immutable transitive evidence integrity при отдельном прогоне/context. Штатный next completion не ослаблен. Внутри completed_series убрано только двойное выполнение одной полной проверки в той же операции. Integrity receipt покрывает underlying primary observations и полный raw/audit/context/admission tree, а не только верхний report SHA.

Фактические результаты окончательного блока:

- targeted-final.txt:15 tests,14 passed и1 skip hostGit; Git boundary отдельно passed1/1 в git-boundary-final.txt (1.948с).
- d3-final.txt:19/19 D3 measurement/recovery regressions,11.408с. schemas-final.txt:14 schemas/configs/fixtures; shell syntax и diff check прошли.
- reuse-final.txt: новые full AA publication + immutable readback passed268.70с; monitoring passed509.16с суммарно, counter checks прошли. Использованы сохранённые320+320 raw после настоящих CLI diagnose→replace. Реального трафика не было.
- reuse-pilot-power.txt: AA/monitoring receipts повторно проверены без научного пересчёта; pilot passed77.96с, power10000 simulations passed114.24с, общий115.41с. Pilot40raw после настоящего replacement; pilot/power имеют раздельные immutable inputs.
- per-run-final.txt: реальные admit дважды, record.prepare следующей стороны и context дважды. Counters evaluate/rows/bootstrap/power =0. Wrong ENV, повреждённый raw SHA и swapped underlying primary observation отклонены. Для явно synthetic fixture wrapper меняет только ожидаемый kind; весь настоящий admission и guards исполняются, validate_gate не подменяется.
- chronology.txt: отдельный property fixture переносит replacement в середину той же mode/profile группы, ledger намеренно обращён; порядок пары соответствует manifest chronology. Только ранее валидированный selected tuple инъецирован в эту узкую проверку порядка. Полные real-path publication/audit tests выполнялись отдельно без такой подмены.

История прерванных попыток сохранена: replacements.txt не содержит результата после usage-limit/engine interruption и не считается passed; replacements-resumed.txt завершился0.09с на неправильной форме искусственного payload (values одновременно с document), helper исправлен без ослабления schema. replacements-final.txt прерван после установления многократной полной валидации; replacements-retained.txt содержит passed AA и подготовленный monitoring, затем остановку для исправлений R11. per-run.txt — отказ раннего driver из-за отсутствующего SYNTHETIC marker; corrected driver использует собственный правильно помеченный fixture. Старые до-ревью журналы описывают исторические состояния.

Дорогие явно synthetic raw сохранены локально в build/d5-r7-synthetic/fixture-9l51pfgl (в analyzer mount /bench/build/d5-r7-synthetic/fixture-9l51pfgl). Каталог игнорируется Git, позволяет reviewer повторять targeted проверки без генерации сотен raw. Копии drivers в development/recheck/ фиксируют команды повторения: запускать в закреплённом analyzer с root mount /bench; все containers --rm --network none. Новый полный make acceptance-test остаётся воспроизводимым, но может занять много минут; повтор неизменённого большого fixture после каждого исправления не нужен.

Действительный freeze не создан, экспериментальные gates остаются not_run/deferred_by_user. Код окончательно остановлен для независимого повторного ревью; коммит по-прежнему делает координатор после приёмки.

## Финальное исправление R11a

03-recheck.md подтвердил научные и прочие исправления, но выявил возможность подделки shallow receipt. Быстрый путь больше не принимает произвольный integrity: требуется память controller, созданная после глубокой проверки. Canonical graph выводится из typed первичных ссылок; nested integrity не определяет его состав. Initial/restart выполняет полный admission и для main deeply проверяет также внешний freeze, pilot/power и reproduction. Последующие вызовы сверяют anchor/source/context и фактические зависимости по проверенному графу в памяти, сохраняя отсутствие повторных научных вычислений.

Добавлены src/analysis/controller.py, docker/controller-client.sh и постоянный network-none analyzer controller в experiment.sh. Prepare/context/complete идут по stdin/stdout/FIFO в тот же процесс, authority не сохраняется на диск. Прямые next/record.prepare без controller отвергаются. CLI prepare делает initial=True full validation; failure не превращается в долговечный допуск. Никаких подписей, сети управления или Docker socket не добавлено.

`final-controller-suite.txt`:36 tests за65.167с,35 passed и1 hostGit skip. Включены прежние targeted acceptance и19 D3 regressions, без повторения полных640raw. `controller-final.txt`:2/2 за31.209с после усиления assertions: каждый timer/calibration/generator вычислен ровно один раз при initial и заново при restart, а repeated actual next/prepare/context не вызывают evaluate/rows/bootstrap/power. Shell FIFO/stdin/stdout test выполнен с настоящим controller process. Ранее успешный host boundary и14schemas сохранены в git-controller-final.txt/schemas-controller-final.txt; новые source hashes отражают окончательный набор.

Контрпример reviewer повторён без mocks по actual CLI: восемь real/passed обёрток над development checks, поддельный маленький integrity и правильный schedule. Next и record.prepare не выдают индекс/spec. После удаления SYNTHETIC marker сам controller boot глубоко отвергает те же данные, не отвечает ready. Positive control явно synthetic, вне рабочего results; намеренное удаление primary из receipt и изменение underlying observation отвергаются. Непроверенные real gates не создавались.

Исторические controller-first/second/third журналы сохраняют обнаруженные ошибки тестовой интеграции (import/helper и local json scope), которые исправлены до успешных suite. Полные scientific AA/monitoring и pilot/power не пересоздавались: их независимое подтверждение в03-recheck.md относится к неизменённым научным алгоритмам и сохранённым fixtures; R11a меняет только происхождение допуска/управление.

Последнее указание пользователя: после успешной D5 остановиться. D6 НЕ выполнялась; её вход выше — передача для следующей отдельной сессии. Source окончательно frozen для reviewer, commit выполняет координатор после независимого вердикта. Экспериментальные gates по-прежнему not_run/deferred_by_user; действительный freeze отсутствует.

## Узкое исправление R11b

04-controller-recheck.md независимо закрыл R11a и оставил одну проверку актуального host HEAD. Controller ready теперь содержит commit из уже принятого admission; experiment.sh передаёт его measurement worker. Непосредственно перед compose up controller-mode measure вызывает docker/check-release.sh: actual Git HEAD должен совпасть с принятым SHA, а Git status по исходным путям должен быть пустым, включая новые untracked исходники. Archive/deep повторно не выполняются. Условия D3 smoke без controller не менялись.

release-guard-measure-final.txt:2/2 host tests за6.993с. Во временном Git проверены actual helper и настоящий docker/measure.sh с подменённым network executor/controller transport: unchanged HEAD с generated results/foreign plan достигает stub network; docs-only новый commit, dirty tracked source и untracked source возвращают2 до network. В положительном actual-measure case stub намеренно возвращает99 после фиксации network-start marker; cleanup штатно отрабатывает. Реальная сеть не запускалась.

controller-release-final.txt:2/2 controller/FIFO/CLI regressions за30.715с после добавления commit в ready. Полные scientific fixtures не повторялись. Shell syntax и git diff --check проходят. Исходники и документация снова frozen для узкой независимой проверки R11b. Commit не создавался; D6 остаётся отдельной следующей сессией по последнему указанию пользователя.

## Последняя сверка initial release

По разрешённому узкому уточнению reviewer real initial admit теперь требует admission.release_commit==release() до ready. Основная main freeze сверка остаётся прежней; новых архивов/расчётов per-run нет. initial-release-final.txt:1/1 за0.129с, copied admission с подменённым SHA отвергнут до ready; только oracle доверенного release identity подменён фиксированным значением, полный admit/controller startup исполняются. Других source-изменений не вносилось. Хеши обновлены, код снова frozen для final verdict.
