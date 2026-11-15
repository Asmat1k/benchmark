# Анализатор по фичам

Реализация и её тесты находятся рядом:

| Каталог | Реализация и проверки |
|---|---|
| `admission/` | Приёмка, сбор свидетельств, ограниченный и исследовательский допуск |
| `calibration/` | Калибровка и качество UDP-отправителя |
| `execution/` | Расписание, контроллер, исполнение, публикация и замена |
| `measurement/` | Raw, метрики, ресурсы, стабилизация и диагностические входы |
| `reporting/` | Статистика, анализ, графики и синтетический генератор |
| `tests/` | Общие и интеграционные проверки без отдельного модуля фичи; fixtures |

Команды запуска сохраняются в Makefile. При ручном запуске Python из корня репозитория задайте `PYTHONPATH=src/analysis`; в analyzer это уже настроено. Модули импортируются по полному имени, например `measurement.raw` и `admission.admission`.

Все проверки обнаруживаются рекурсивно:

```sh
docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 -e MPLCONFIGDIR=/tmp/matplotlib -v "$PWD:/bench" -w /bench wswt-bench-analyzer:dev python -B -m unittest discover -s src/analysis -v
```

Можно запускать фичу: `python -m unittest discover -s src/analysis/execution -t src/analysis`, либо модуль: `python -m unittest execution.test_execution`. Полный старый набор содержит известные несовместимые fixtures; перенос не меняет критерии и исходы этих проверок.
