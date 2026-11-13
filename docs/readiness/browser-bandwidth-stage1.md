# Отдельное наблюдение браузерной полосы до calibration publication

Подготовлено на этапе1; реальный сбор не выполнен. Это диагностика доли полосы, не generator gate. Используются существующие `schedule.py`/`docker/measure.sh`, настоящий браузер и стандартные raw. Менять браузерный генератор, Docker resources или sample-backlog не требуется.

Фиксированный объём: один baseline loss0 прогон WS и один WT-S в заранее полученном порядке schedule, 256 байт, 20 Гц,200 warmup +1200 measurement slots. Это70с подачи на режим,60с измерительной части; штатный horizon/drain/стабилизация сохраняются. WT-D исключён из основного сравнения; при решении включить его этот диагностический контракт нужно явно дополнить до сбора. Резервные100 Гц сюда не входят: они проверяются последующим generator gate.

Первичные счётчики уже сохраняет measure: `qdisc-before.json` до браузерного вызова и `qdisc-stable.json` после полного дренирования. Для обоих netem egress берутся cumulative bytes/packets/drops, handle/options, backlog/qlen. Уровень bytes совпадает с calibration saturation: dequeued skb, включая Ethernet header, без FCS/preamble/IFG. Включены WS TCP ACK/TLS/HTTP, QUIC/WebTransport управляющие пакеты, повторы и любой фон на линке. Фон не вычитается. Это измеренные счётчики, не частота×payload.

Для каждого режима m и направления d:

`B[m,d] = bytes_stable[d] - bytes_before[d]`

`R_upper[m,d] = 8 * B[m,d] / 60 / 1e6` Мбит/с.

Числитель включает также setup/warmup/drain, а знаменатель только60с измерения. Поэтому получаем консервативную верхнюю оценку средней доли основной нагрузки, а не точечную оценку установившейся скорости. Полное60-секундное окно содержится в счётчиках; никакой байт измерительного окна не исключён. Эта оценка заведомо не меньше среднего за само окно, но не ограничивает мгновенный пик/короткие пачки. Раннее завершение, пропуски scheduler или неполные echo не разрешают публиковать заниженную полосу: адаптер отвергает такой диагностический прогон.

`C[d] = min(saturation_forwarded_bytes *8 / duration_s /1e6)` по двум saturation loss0/.01 соответствующего направления.

`main_bandwidth_fraction = max_m,d(R_upper[m,d] / C[d])`.

Два независимых10-Мбит/с направления не суммируются. Обе скорости capacity должны пройти9–11; четыре режима saturation должны присутствовать. Решение строго `<0.1`; ровно0.1 отвергается. Обе граничные очереди пусты, delta drops0, delta bytes/packets положительна, qdisc options/handle неизменны. Это baseline-верхняя оценка, а не доказательство полосы/ресурсного запаса на lossy профилях; последующие generator/A/A/monitoring/pilot gates остаются обязательными.

## Команды для следующего этапа, не для запуска сейчас

После методического решения по RTT, окончательной фиксации исходников/configs и базовых build/TLS/path/raw/analysis/timer checks, на свободном стенде с действительным `SERIES_TLS_DIR`:

```sh
: "${SERIES_TLS_DIR:?set to the admitted certificate directory}"
BW_RUN=$(mktemp -d results/verify/diagnostic/browser-bandwidth.XXXXXXXX)
docker run --rm --network none -v "$PWD:/bench" -w /bench wswt-bench-analyzer:dev python -B src/analysis/schedule.py diagnostic "$BW_RUN" --blocks 1 --sessions 1 --baseline --generator-hz 20
sh docker/measure.sh "$BW_RUN" 0
sh docker/measure.sh "$BW_RUN" 1
printf '%s\n' "$BW_RUN"
```

`--generator-hz20` включает существующие raw/backlog/source записи, но эта команда не вызывает `collect-diagnostic.sh generator`, `make generator` или admission с требованием принятой calibration. Два запуска — один фиксированный сбор, не обход ограничения5 минут. Ожидается около3–5 минут плюс переменный Docker setup/стабилизация, консервативно резервировать до8 минут; выполняет пользователь. Точная длительность стенда пока не наблюдалась. При ошибке сохранить partial/STOP/quarantine; не повторять до первого успеха.

Выход: `$BW_RUN/{schedule,ledger,context}.json`, два `$BW_RUN/raw/b0-a0-m*/` с обычными slots/warmup/resources/backlog, qdisc-before/stable, контекстом, source inventory, manifest/SHA256SUMS. Сбор можно выполнить до полной UDP calibration, но численный знаменатель получают из её saturation в той же среде и с тем же source inventory. Нельзя менять код/configs между ними и затем применять старые hashes.

После завершения нового calibration raw в `$CAL_RUN`, **до package/publication**, выполнить короткий offline расчёт:

```sh
: "${BW_RUN:?set to the completed bandwidth directory}"
: "${CAL_RUN:?set to the newly completed calibration directory}"
docker run --rm --network none -v "$PWD:/bench" -w /bench wswt-bench-analyzer:dev python -B docker/browser_bandwidth.py "$BW_RUN" "$CAL_RUN" "$CAL_RUN/browser-bandwidth.json"
```

Адаптер использует `calibration_report.rate`, сверяет calibration seal, source inventories до/после/текущие, контексты, точное diagnostic расписание и complete ledger. Для каждого браузерного raw вызывает существующий полный валидатор hashes/schema/config/ID/clock и `diagnostic_raw`. Выход создаётся эксклюзивно: `browser-bandwidth.json` содержит исходные snapshots, directional capacity/rates/ratios, верхнюю долю, ограничения и ссылки path/SHA256 на первичные файлы. Это занимает секунды, сеть отключена. Повторная обработка требует нового имени файла, старое не перезаписывать.

Успех расчёта: exit0/status passed и `main_bandwidth_fraction<.1`; плюс независимый просмотр offloads/MTU/route/background/достоверности счётчиков. Exit1 означает достаточное консервативное свидетельство не получено; нельзя менять знаменатель/вычитать прогрев до удобного ответа. Ошибки инвариантов блокируют вывод.

В trace_review новой calibration перенести наблюдённую верхнюю долю, указав в rationale путь/SHA256 `browser-bandwidth.json`, оба направления, уровень bytes и консервативность. Файл располагается в новом calibration каталоге до package, чтобы существующий packager включил его в evidence. Исходный captured.json не перезаписывать: дополнительный derived документ не изменяет sealed raw. Все связанные браузерные raw сохраняются по исходным путям.

Порядок без круговой зависимости: qualification → отдельная браузерная bandwidth-диагностика → UDP calibration raw по принятому дизайну → bandwidth offline расчёт/review → calibration package/report passed → формальный generator20/100 → A/A → monitoring → pilot. До принятия RTT-методики переход к calibration запрещён. При принятии нового многосессионного дизайна bandwidth-доказательство привязывают к его финальному контракту, не выдают текущий single-directory package за поддержку40 сессий.
