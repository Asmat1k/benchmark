# Отдельная UDP-диагностика

Основной пользовательский путь описан в [корневом README](../../README.md). Новая UDP-калибровка не является условием исследовательского браузерного сбора.

Если этот диагностический сбор назначен отдельно, запустите из корня репозитория `SERIES_TLS_DIR=/absolute/path/to/tls sh docker/commands/calibration.sh`. Требуются свободные измерительные подсети и сертификат среды. Сбор создаёт отдельный каталог results/verify/diagnostic/calibration.* и удерживает measurement lock; чужие контейнеры не удаляются.

Текущая методика задаётся configs/plan.json (`observed-profile-check-v1`), численные критерии — configs/thresholds.json. Проверяются исходные ID, времена, pcap, настройки сети, потери по направлениям, ресурсы и полоса. Сборщик фиксирует план до сети и сохраняет исходники/контекст до и после. Успех оболочки означает окончание сбора, а не passed научной проверки.

Для публикации нужны отдельный review с collection_id, reviewer, rationale и trace_review и проверка первичных данных:

```sh
docker run --rm --network none -v "$PWD:/bench" -w /bench wswt-bench-analyzer:dev python -B docker/diagnostics/calibration_report.py package "$RUN" "$REVIEW" "$ENVIRONMENT"
make calibrate ARGS="--kind real --input $RUN/publication/input.json --output $RUN/calibration-report.json --environment $ENVIRONMENT"
```

Отказы сохраняются без изменения порогов, коррекции RTT или повторов ради passed. Подробные прежние разборы доступны в истории Git.
