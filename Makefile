.PHONY: build smoke cleanup archive
build:
	sh docker/commands/build.sh

smoke:
	sh docker/commands/smoke.sh

archive:
	sh docker/commands/archive.sh

cleanup:
	sh docker/commands/cleanup.sh "$(RUN_DIR)"

.PHONY: docker-test
docker-test:
	docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONPATH=src/analysis:docker/diagnostics -v "$(CURDIR):/bench" -w /bench wswt-bench-analyzer:dev python -B -m unittest discover -s docker/tests -p '*_test.py' -v

.PHONY: measurement-smoke
measurement-smoke:
	sh docker/commands/measurement-smoke.sh

.PHONY: measure
measure:
	sh docker/commands/measure.sh "$(SERIES_DIR)" "$(RUN_INDEX)"

.PHONY: analyze analysis-test
analyze:
	sh docker/commands/analyze.sh "$(SERIES)" $(ARGS)

.PHONY: exploratory-prepare
exploratory-prepare:
	docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 -e BENCH_RELEASE_COMMIT="$$(git rev-parse HEAD)" -v "$(CURDIR):/bench" -v "$(CURDIR):$(CURDIR)" -w /bench wswt-bench-analyzer:dev python -B -m admission.exploratory prepare "$(SERIES_DIR)" --environment "$(ENVIRONMENT)" --tls "$(SERIES_TLS_DIR)"

analysis-test:
	docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 -e MPLCONFIGDIR=/tmp/matplotlib -e PYTHONPATH=src/analysis -v "$(CURDIR):/bench" -w /bench wswt-bench-analyzer:dev python -m unittest discover -s src/analysis/reporting -t src/analysis -p 'test_analysis*.py' -v

.PHONY: calibrate generator timer aa monitoring pilot power verify freeze experiment acceptance-test
calibrate generator timer aa monitoring pilot power verify freeze:
	sh docker/commands/acceptance.sh $@ $(ARGS)

experiment:
	sh docker/commands/experiment.sh "$(SERIES_DIR)" "$(ALLOW_REAL_EXPERIMENTS)"

acceptance-test:
	docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONPATH=src/analysis -v "$(CURDIR):/bench" -w /bench wswt-bench-analyzer:dev python -B -m unittest admission.test_acceptance -v

.PHONY: controller-test
controller-test:
	docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONPATH=src/analysis -v "$(CURDIR):/bench" -w /bench wswt-bench-analyzer:dev python -B -m unittest execution.test_controller -v
