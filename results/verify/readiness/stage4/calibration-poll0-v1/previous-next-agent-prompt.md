## Обновление после целевой трассы 14 ноября2026

Прежде прежней передачи ниже прочитай `docs/readiness/stage4-transition-trace.md` и `results/verify/readiness/stage4/transition-trace-v1/independent-findings.md`. Следующий описанный ниже короткий опыт УЖЕ ВЫПОЛНЕН ровно один раз, повторять его нельзя. Selftest1.170с/exit0; r80p1 trace119.157с/exit0, raw `results/verify/diagnostic/transition-trace.jNq2hqdS`,75sealedfiles,zero losses. Старый многосекундный переход не повторился: **inconclusive**, не fixed. Sender/process clear этого инструментированного опыта не заменяют исторический suspect/gates.

Новая локализация отдельных выбросов: ID2035 postxmit→serverreceived5.569мс, runnablewait5.550мс; ID8504 forward queue→xmit61.969мс, одновременно reversebulk3 с~61.674мс residence и senderlag22.052мс. Поддерживает общий delayedservice episode, но filteredtrace silence не доказывает остановку VM/host. Netemwatchdog/hostvcpu механизм не разделён. Sourceкод/thresholds/образы/ENV/TLS не изменены; poll0 сохранён. Нужен НОВЫЙ обоснованный план дальнейшей локализации до любой сети, а не повтор прежнего опыта/полная calibration. Команды>5мин запускает пользователь. Никакой новой mandatory macOStrace. Полный протокол/ограничения/отрицательные offlineпопытки/SHA/cleanup в новом отчёте. Этап4 не завершён.

---

Работай в `/Users/dobrov/Desktop/Code/ITMO/benchmark`, соблюдай AGENTS.md. Продолжи незавершённый этап 4. **Первый шаг — локализовать оставшийся скачок RTT в профиле r80p1, а не повторять полную калибровку.** Не останавливайся на обещании исследования: прочитай актуальные свидетельства, подготовь предметный ограниченный диагностический план и начни разрешённые короткие проверки.

## Правила пользователя

- Любую команду с ожидаемым или возможным временем более 5 минут запускает пользователь, включая offline-расчёты, глубокий verify и архивирование. При неизвестной длительности оцени её по коду/данным/журналам; если уверенности нет — передай запуск пользователю. Не обходи ограничение фоном, сабагентами или дроблением одного долгого опыта.
- Передавай одну следующую долгую команду за раз: рабочий каталог, назначение, время, уникальные stdout/stderr/exit, выходы и критерии успеха. После передачи жди результата. Пользователь сейчас готов запускать 30-минутные проверки, но хочет сначала убедиться на малых, что исправление работает. Полностью успешных малых проверок пока нет.
- Короткие обоснованно ограниченные проверки выполняй самостоятельно. Предпочитай малозатратное рабочее решение, а не сложный рефакторинг. Уже использовали фиксированные диагностические опыты по 214–226 секунд с общим пределом 270 с + 10 с очистки. Это самостоятельные исследования разных гипотез, не части полной калибровки.
- Пользователь явно попросил сабагентов для потенциально тяжёлых исследований/этапов. Делегируй независимый read-only анализ, но не создавай тяжёлой параллельной нагрузки во время измерений.
- Сетевые измерения оборачивай в `caffeinate -ims`. Перед ними проверяй AC, свободное место, измерительные сети/lock, исходники, образы, ENV/TLS и отсутствие собственных незавершённых проектов. Пользователь подтвердил свободный Mac/AC/open lid для последнего четырёхминутного опыта; перед новым измерением проверь актуальное состояние. Не останавливай чужой qdrant автоматически.
- Failed/inconclusive останавливает переход к зависимым этапам. Нельзя повторять неизменённый план до удачного результата, добирать данные, выбирать лучший прогон, исключать хвосты или менять пороги/блоки по наблюдённым результатам. Техническое исправление и новый опыт требуют заранее записанного обоснования и проверки применимости допусков.
- Raw/seals/исторические reports не редактировать. Derived/review хранить отдельно. Не ставить true автоматически по отсутствию флага, не выдумывать независимого рецензента. Обязательную macOS trace не вводить; Linux trace допустима как целевая диагностика.
- A/A, monitoring, pilot/power, freeze и main в этом чате не запускать. Main в будущем ограничен 15 часами.

## Актуальное состояние кода и файлов

Проверено при передаче:

- HEAD `d4cf0f82f330af1cd188febfa5f3757a5cf37799` — документальный коммит полного отчёта.
- Код исправления: `12ba5e5e5740c2f0acf61e6bd4849026ef136c26`.
- Предыдущие изменения: `3605994e8359a70443621517e11dd2383a726f48` — cap ожидания 1 мс; `494e1a99bf9c92bd2a26af7dce6a8752af23d448` — исправление порядка baseline/capture-observer.
- Исполняемые исходники чистые. В workspace много **untracked** важных docs/results этого чата. Не удаляй их, не делай git clean/reset и не считай мусором.
- `build/release-state.json` обновлён на текущий HEAD. Актуальный inventory 134 файлов: `results/verify/readiness/stage4/deep-review-v1/source-inventory-new.json`. При старте снова проверь фактические HEAD/cleanliness/hashes.
- В `docker/calibration_probe.py` теперь `MAX_ECHO_WAIT_NS=0`: UDP echo не блокируется в select во время планирования отправок. Сетка 100 Гц, все ID, 256 bytes, tag, минимальный интервал фактических отправок 2,5 мс, actual RTT и финальный drain 2 с сохранены. Saturation продолжает использовать прежнее положительное ожидание. Браузерный генератор не менялся.
- В `docker/calibration_probe_test.py` fake clock продвигается при timeout0, чтобы тест не зависал. 11 sender/bandwidth/regression tests прошли за 7,352 с.
- В `docker/measure.sh` исправлен конкретный дефект: backlog observer теперь запускается **до** resource samplers/baseline. Ранее baseline router CPU снимался без observer, idle — с ним, что давало ложное несопоставимое сравнение. Пороги/правила не ослаблены; регрессионный shell-mock воспроизвёл ошибку до исправления и прошёл после.
- `--immediate-mode` и CPU affinity **не внедрены**: контролируемые опыты не подтвердили их пользу.

## Сначала прочитай

1. `docs/readiness/stage4-deep-investigation.md` — основной читабельный отчёт: причины, изменения, результаты, отрицательные гипотезы, ограничения.
2. `results/verify/readiness/stage4/deep-review-v1/summary.json` и `SHA256SUMS.json` — машинная сводка, пути, времена, SHA материалов.
3. `results/verify/readiness/stage4/deep-review-v1/dependence/profile-validation-breakdown/README.md`, `analysis.json`, `transition-1second.json` — **непосредственно оставшийся скачок**.
4. `results/verify/readiness/stage4/deep-review-v1/pauses/report.md` и `dependence/README.md` — разбор старых пауз/зависимости.
5. `dependence/wake-abba-analysis/README.md` и `dependence/affinity-abba-analysis/README.md` в том же deep-review-v1.
6. Для контракта этапа: `docs/readiness/stage3-handoff.md`, `stage2-handoff.md`, `stage4-handoff.md`, `calibration-blocks-stage2.md`, `browser-bandwidth-stage1.md` **с уточнением о трёх режимах**, `sender-quality-v2.md`, `docker/calibration.md`, `docs/verification.md`, `docs/experiments.md`.
7. Актуальный код `docker/calibration_probe.py`, `docker/calibration.sh`, `docker/sender-diagnostic.sh`, `docker/measure.sh`, `docker/calibration_report.py`, `src/analysis/calibration_blocks.py`, `acceptance.py`, соответствующих validators/collectors. Не повторяй полный аудит проекта.

## Фиксированная среда и методика

- WS, WT-S и WT-D включены; Docker 2 vCPU / 4109484032 bytes, native linux/arm64. Численные thresholds сохранены, preliminary=false. 40-дневный вариант исключён.
- Исходный фактический ENV: `results/verify/diagnostic/timer-timer.2ST8NYBU/context.json`, SHA256 `231ae4819874cf877f8e2234b4331171309906cb4c259b847c7ff8fc403039da`. Последующие реальные contexts побайтно совпадали, поэтому использовали эту единую path/SHA identity.
- TLS: `/Users/dobrov/Desktop/Code/ITMO/benchmark/build/series-tls-stage2._n__udb0`.
- Leaf DER SHA256/good pin `fc2a5f4d7bc0fce861baee9207c82ff86bf502fda419cf45c73e3559d1a56d18`, PEM SHA256 `ff69b4145dbd13f610506b4c5324ed515b5d58dd5556c81ff087cf845a0933b9`.
- notAfter `2026-11-26T16:22:37Z` (26 ноября 19:22:37 МСК). Проверяй текущую дату/identity/резерв всей последовательности; ориентир 6 дней + 2 дня резерва, не гарантия календаря. Старый `series-tls.PMYktiWa` не использовать.
- Точные образы:
  - server `sha256:c2c60585a64d04e8dd7dd6a674625c0aec44cdc385561c8864dab734fbf19c44`;
  - browser `sha256:356b2e1af8773aaf688f3c4e03bbfa73b2c835d88be0a76278030cf55d1c1641`;
  - router `sha256:d78a80d31724881c1adaa57005fae37f4f23e0013945dac759d7ee1f76b6b74d`;
  - analyzer `sha256:9e263785dc135db52a216bc358c38218cf3d98f178a9981a365ca79cda7cbd62`.
- Cached rebuild v3 создал другие IDs; сравнение показало одинаковые Config/RootFS трёх образов и только pycache-различие analyzer. Восстановлены исходные точные образы. Новые sender/collector файлы монтируются с host, не встроены в эти образы. Не запускай build без причины: это может снова изменить IDs/ENV. История/сравнения в `results/verify/readiness/stage4/release-v3/`.
- Чужой `ai-grepa-qdrant-1` работал unhealthy, его причинная роль не доказана, он не останавливался. Последние проверки: AC100%, host около118 GiB свободно; измерительные контейнеры/сети удалены, lock получен/освобождён. Проверяй заново.
- Sender v2: late (lag≥10 мс) ≤1%, max lag≤50 мс, ≤4 отправок в любом полуоткрытом окне 10 мс. ID/grid/tag/finite/monotonic invariants обязательны. Не переносить эти правила на browser slots.
- Полная calibration: один заранее фиксированный сбор 14×10000 UDP echo (256 bytes,100 Hz) +4 saturation (loss0/1%×forward/reverse), около30–35 минут. Профили r20/r80 =10/40 мс **на направление**, loss0/1% **на направление**, rate10 Mbit/s, limit1000, jitter/correlation0. Saturation payload1200, interval800µs,90000 sends≈72с, центральное окно61с.
- Метод `circular-block-medians-v1`: 100/200/500 слотов (1/2/5с),20000 replicates; фиксированные PCG64 seeds по SHA строки `20261113:LABEL:BLOCK`; latency alpha=.04/6, loss alpha=.01/8, inverted_cdf, envelope всех трёх длин. Разность профиля с обоими baseline должна целиком лежать в target±2мс. Объём/длины/пороги не подбирать по результату.
- Process diagnostics: RTT/survival ACF lag500/1000/2000, граница abs(rho)>3.5/sqrt(n−lag);20 последовательных окон, fitted drift>2мс/пустое окно также дают suspect. Медианное заполнение missing RTT только для диагностики, не bootstrap. Флаг — отбраковочная эвристика, не точная физическая причина и не доказательство конкретной стохастической долгой памяти. Его нельзя игнорировать по текущему контракту.

## История этапа 4 и применимость gates

Этап 3 имел реальные build/tls/path/timer/raw/analysis passed. Исторический пакет `results/verify/readiness/stage3/` не менялся. V3/V4 выпустили новые шесть early reports после исправлений и повторных коротких smoke/timer. Последний до poll0 пакет: `results/verify/readiness/stage4/release-v4/REPORT_MAP.json`, `verify-pre-bandwidth.json`:6passed, calibration/generator/aa/monitoringnot_run, final=false/exit2.

**Эти пакеты относятся к прежним source hashes. После poll0 новые ранние gates не публиковались и старые не перепривязывались.** Обновлённый release-state не делает их автоматически актуальными. Перед дальнейшей официальной приёмкой нужен новый применимый source-bound пакет. Новые диагностические опыты не являются qualification/calibration/generator gates.

Хронология:

1. `sender-diagnostic.E243q4gg`: cap старого sender, qualification остановилась на q1, maxlag57,235мс>50; failed сохранён.
2. Исправление cap1мс (`3605994`), повторные early gates. `sender-diagnostic.Mbdvg8v6`:3×10000 qualification passed; late .19/.22/.07%, maxlag32.68/27.95/20.55мс,burst4/4/3,79seals. Это историческое наблюдение старого cap1мс; после poll0 его нельзя выдавать за qualification нового sender.
3. `browser-bandwidth.oc6op_bb`: первый WT-S вернул все1400echo, но STOP/stabilization — несопоставимый router CPU baseline. Raw в quarantine, не редактировался.
4. Исправление порядка observer (`494e1a9`), V4early reports. `browser-bandwidth-v4.9r51339s`:WS→WT-D→WT-S, все200warmup/1200measurement complete, raw/ENV/source/counters accepted.
5. Полная `calibration.lShojabe`,29мин22с,exit0,146sealedfiles/46.1MB. Первичная приёмка failed:
   - `r20p0-after` maxlag129.224986мс (ID5928);
   - `r20p1-after` maxlag53.692504мс (ID891);
   - остальные12senderpassed; ACF flags baseline-before/r20p0-latency.
   - ID/tag/pcap/seed/readback/directional drops/denominators согласованы; capture drops0. Loss0получили10000echo.
   -4capacity9.99949–10.00128Mbit/s. Штатный `browser_bandwidth.py` далpassed,maxfraction=.008380037347=0.838%<10%,все3мода/2направления,из фактическихbyte counters.
   - Полный bootstrap/официальная публикация calibration report НЕ выполнялись: обязательные первичные условия ужеfailed. Нельзя объявлять научный reportpassed; generator не запускался.
   - Reviews/BW/STOP/SHA: `release-v4/calibration-lShojabe-raw-review.json`, `browser-bandwidth-lShojabe.json`, `STOP-calibration-lShojabe.json`, `calibration-lShojabe-SHA256SUMS`.

Старые паузы сопровождались общей тишиной ingress в обоих направлениях (110.493/62.095мс), уже отправленные echo задерживались до browser receive. Нельзя объяснять их только sender GC или считать `send_i−receive_(i−1)` чистым временем обработки: несколько echo outstanding.

## Завершённое глубокое исследование

Каталог `results/verify/readiness/stage4/deep-review-v1/`, все планы/скрипты/сырьё/execution/stdout/stderr/exit/SHA сохранены. Были задействованы сабагенты `pause_review`, `dependence_review`, `fix_research`; новые агенты должны читать их отчёты, а не предполагать доступность старых сессий.

1. Capture ABBA `capture-abba.MaDtfSFh`,4×5000,223с,62seals. Проверяли buffered→immediate→immediate→buffered. Tcpdump4.99.3/libpcap1.10.3, default timeout1000мс; -U не отключает kernel delivery batching. Но `--immediate-mode` не убрал фазовую структуру и увеличилCPU; не внедрён.
2. Wait/poll0 ABBA `wake-abba.uMz2xu7i`,4×5000,223с,70seals. A=select≤1мс,B=poll0:
   - p99lag .859/.0175/.0172/.886мс;
   - p99RTT1.785/.803/.786/1.567мс;
   - senderCPU2.24/95.53/95.46/2.20% одногоядра;
   - rankrho1000 .1177/.0288/−.0004/.1771;
   - фазовая повторяемость .774/−.119/−.108/.778.
   Улучшились и router-span, и residual RTT; эффект обратим. Это поддерживает poll0, но не разделяет CPUresidency/idle/kernel service и не доказывает устранение редкого129мс события. Цена≈одно vCPU. Применён минимальный poll0код,11testsOK.
3. Проверка применённого кода `profile-validation.73PKohD7`,2×10000,214с,44seals:
   - r20p0-check:senderpassed,maxlag9.790мс,p99lag.008751мс,medianRTT20.667мс,processclear;
   - r80p1-check:senderpassed,maxlag3.208мс,p99lag.007875мс,medianRTT80.586мс,**processsuspect**. Это оставшаяся проблема.
4. Affinity ABBA `affinity-abba.lK9trsns`,4×5000 r80p1,226с,82seals. A=обаhelper0-1,B=sender0/server1; реальные masks проверены. Все4sender/processclear, включая контроли; прежний переход не повторился. p99RTTA1/B1/B2/A2=82.658/82.390/82.246/81.695мс, maxlagB35.18/33.69хужеA14.76/8.22. По заранее заданному критерию inconclusive для affinity; **pinning не внедрён**. При общих seeds совпадают lossID — это не независимые реализации.

Исследовательские rank/winsor/cross-fit преобразования не использованы для допуска/raw correction. Исторические RTT имеют повторяемую фазовую структуру, не только выбросы. Новые baseline ABBA имели15Гц и гармоники; это posthoc и иной спектр, чем старая calibration. Не объявляй15Гц доказанной причиной129мс. Короткие успешные N5000 нельзя подставлять вместо N10000/14+4.

## Что именно осталось локализовать

Raw: `results/verify/diagnostic/profile-validation.73PKohD7/r80p1-check/`.

- На42–48с median router-span (forward ingress→reply ingress) вырос примерно40.294→43.04–43.29мс, затем вернулся.
- В окнах40–45/45–50с medianRTT82.269/83.279мс против80.666до и80.542после.
- ResidualRTT при этом НЕ вырос:40.372→40.247мс и сохранился ниже.
- Senderlag внутри42–48с≤.017мс, receive перестановок0. Потери не образуют очевидного провала:491/493survivors из500 в проблемных5-секундных окнах. Формальные directional интервалы включают1%.
- RTTrho500/1000/2000=.21403/−.05866/−.06668; router-span=.23280/−.07360/−.07913.
- Это реальный переход первого полупути — forwardnetem/serverecho/guest service; не senderdeadline и не очередьclientreceive. Нет данных, позволяющих точно выбрать один компонент.
- RoutercgroupCPU всего26.793мс/102с,throttle0; это не измерение host/softirq и не исключает краткие задержки VM. НепрерывныхCPU/qdisc/scheduler records нет — samplers не работали во избежание observerload.
- Pcap epoch против sender monotonic имеет ступеньки до≈1.7мс/100с. Нельзя наивно склеивать часы и приписывать им наносекундную точность. Сам внутрипакетный pcapspan независимо подтверждает переход.

## Твой следующий шаг — приступить к локализации

1. Сначала короткий read-only разбор указанного перехода и существующих скриптов. Зафиксируй проверяемые гипотезы: задержанный dequeue/обслуживание netem; поздний wakeup/исполнение echo-server; общая задержка guest/vCPU. Подтверждения только sender уже недостаточно.
2. Подготовь **один заранее заданный короткий целевой опыт r80p1** (ориентир10000echo≈102с+setup, общий бюджет2–4мин/жёсткийпредел<5мин), а не ещё один неизменённый ABBA до удачи. Сохрани текущийpoll0, payload/rate/spacing/seeds/режимloss, дваpcap и всеID. Новых численных допусков/коррекции данных нет.
3. Добавь ровно недостающую наблюдаемость: Linux scheduler/syscall timestamps для **echo-server**, достаточные отметки приёма/отправки и ID, и события/счётчики, отделяющие forward qdisc от выполненияserver. Подтверди семантику точки capture относительно qdisc: нельзя молча считать `tcpdump -Q out` timestamp гарантированно «после netem» без проверки kernel placement.
4. Начни с короткого network-none selftest доступности/потерь/привязкиPID/часов, затем выполни разрешённую ограниченную диагностику. Если оценка может превысить5мин — подготовь одну команду пользователю и остановись в ожидании. Пользователь может запустить30минут, но только после честного представления результатов малых проверок.
5. Можно переиспользовать `docker/sender_scheduling_trace.py`, `sender_scheduling_probe.py`, `sender_scheduling_check.py` и `results/verify/readiness/sender-scheduling-LGEmSpOH/`, но **не запускать старую обёртку вслепую**:
   - старый tracer ищет один фиксированный sender path/TID и рассчитан на60с/1500slots;
   - тяжёлые per-call usage/rusage/schedstat Python wrappers сами создавали overhead;
   - poll0 делает очень много select(0): **не включай per-pselect6 tracing sender**, это может переполнить буфер и исказить опыт. Нужны целевые server recvfrom/sendto и scheduler/netem события, а не миллионы polling syscalls;
   - проверь hostTID/NSpid, trace_clock=mono, start/end marker brackets, pairs/coverage и dropped/overrun=0. Права LinuxVMtracer не означают обязательную macOStrace.
6. Не вводи самплер1Гц без оценки его влияния: периодическая наблюдательная нагрузка уже была проблемой. Предпочти ограниченные event-based records/буферы, запись после пробы. Если вводишь observer, явно раскрой его влияние и не выдавай его результат за неизменённую calibration.
7. Если скачок не воспроизвёлся, запиши **inconclusive**, не «исправлено»; не повторяй до успеха. Если удалось разделить причины, примени минимальную обоснованную правку, создай meaningful regression и короткую сходную проверку, документируй отрицательные результаты/CPUцену/потерю применимости gates.
8. Итог: что установлено, что исправлено, числа до/после, что осталось неизвестным, все команды/времена/exit/paths/SHA, чистота и cleanup. Не заявляй готовность к полной calibration, если малые process проверки всё ещё не прошли. Обнови читабельный основной отчёт/передачу; этап4пока остаётся незавершённым.

Цель этапа4 в будущем: новый применимый REPORT_MAP с build/tls/path/timer/raw/analysis/calibration/generatorpassed, aa/monitoringnot_run, final=false/expectedexit2. Текущая задача перед этим — причинная локализация оставшегося r80p1 transition.
