.PHONY: build smoke cleanup archive
# Собирает четыре закреплённых образа и проверяет исходники TypeScript и Go.
build:
	sh docker/commands/build.sh

# Проверяет TLS, совместимость транспортов и сетевой путь Docker.
smoke:
	sh docker/commands/smoke.sh

# Архивирует четыре образа Docker и сохраняет контрольную сумму SHA-256.
archive:
	sh docker/commands/archive.sh

# Удаляет проверочный проект из RUN_DIR и проверяет очистку.
cleanup:
	sh docker/commands/cleanup.sh "$(RUN_DIR)"

.PHONY: docker-test
# Запускает тесты диагностических инструментов Docker без измерительной сети.
docker-test:
	docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONPATH=src/analysis:docker/diagnostics -v "$(CURDIR):/bench" -w /bench wswt-bench-analyzer:dev python -B -m unittest discover -s docker/tests -p '*_test.py' -v

.PHONY: measurement-smoke
# Выполняет короткие измерения WS и WT-S и проверяет результаты.
measurement-smoke:
	sh docker/commands/measurement-smoke.sh

.PHONY: measure
# Выполняет один запуск из расписания по SERIES_DIR и RUN_INDEX.
measure:
	sh docker/commands/measure.sh "$(SERIES_DIR)" "$(RUN_INDEX)"

.PHONY: analyze analysis-test
# Создаёт отчёты, таблицы и графики для SERIES с дополнительными параметрами ARGS.
analyze:
	sh docker/commands/analyze.sh "$(SERIES)" $(ARGS)

.PHONY: compare comparison-test
# Дополняет сохранённый отчёт сравнительными графиками в новом каталоге без перезаписи результатов.
compare:
	sh scripts/analyze-comparisons.sh "$(SERIES)"

# Проверяет сравнительные графики, состав пар и сохранность исходного отчёта.
comparison-test:
	docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 -e MPLCONFIGDIR=/tmp/matplotlib -e PYTHONPATH=src/analysis -v "$(CURDIR):/bench" -w /bench wswt-bench-analyzer:dev python -B -m unittest reporting.test_comparisons -v

.PHONY: exploratory-prepare
# Готовит новую исследовательскую серию с окружением ENVIRONMENT и сертификатами SERIES_TLS_DIR.
exploratory-prepare:
	docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 -e BENCH_RELEASE_COMMIT="$$(git rev-parse HEAD)" -v "$(CURDIR):/bench" -v "$(CURDIR):$(CURDIR)" -w /bench wswt-bench-analyzer:dev python -B -m admission.exploratory prepare "$(SERIES_DIR)" --environment "$(ENVIRONMENT)" --tls "$(SERIES_TLS_DIR)"

# Запускает регрессионные тесты анализа на тестовых данных.
analysis-test:
	docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 -e MPLCONFIGDIR=/tmp/matplotlib -e PYTHONPATH=src/analysis -v "$(CURDIR):/bench" -w /bench wswt-bench-analyzer:dev python -m unittest discover -s src/analysis/reporting -t src/analysis -p 'test_analysis*.py' -v

.PHONY: calibrate generator timer aa monitoring pilot power verify freeze experiment acceptance-test
# calibrate: Измеряет и оценивает калибровку сети.
# generator: Проверяет генератор нагрузки на соответствие требованиям допуска.
# timer: Проверяет часы браузера на соответствие требованиям допуска.
# aa: Выполняет контрольный этап A/A.
# monitoring: Оценивает контрольный этап мониторинга.
# pilot: Выполняет пилотную серию измерений.
# power: Оценивает статистическую мощность по результатам пилотной серии.
# verify: Проверяет свидетельства для строгого допуска.
# freeze: Фиксирует привязки строгого эксперимента перед основной серией.
calibrate generator timer aa monitoring pilot power verify freeze:
	sh docker/commands/acceptance.sh $@ $(ARGS)

# Запускает или продолжает SERIES_DIR при явном ALLOW_REAL_EXPERIMENTS=yes.
experiment:
	sh docker/commands/experiment.sh "$(SERIES_DIR)" "$(ALLOW_REAL_EXPERIMENTS)"

# Запускает тесты допуска и приёмки.
acceptance-test:
	docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONPATH=src/analysis -v "$(CURDIR):/bench" -w /bench wswt-bench-analyzer:dev python -B -m unittest admission.test_acceptance -v

.PHONY: controller-test
# Запускает тесты контроллера выполнения.
controller-test:
	docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONPATH=src/analysis -v "$(CURDIR):/bench" -w /bench wswt-bench-analyzer:dev python -B -m unittest execution.test_controller -v

.PHONY: python-test
# Собирает тестовый образ и запускает весь автономный набор тестов Python.
python-test:
	docker build -f docker/images/Dockerfile.tests -t wswt-bench-python-tests:dev .
	docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 -e MPLCONFIGDIR=/tmp/matplotlib -e PYTHONPATH=src/analysis -v "$(CURDIR):/bench" -w /bench wswt-bench-python-tests:dev python -B -m unittest discover -s src/analysis -p 'test*.py' -v
