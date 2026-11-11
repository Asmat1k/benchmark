.PHONY: build smoke cleanup archive
build:
	sh docker/build.sh

smoke:
	sh docker/smoke.sh

archive:
	sh docker/archive.sh

cleanup:
	sh docker/cleanup.sh "$(RUN_DIR)"

.PHONY: measurement-smoke
measurement-smoke:
	sh docker/measurement-smoke.sh

.PHONY: measure
measure:
	sh docker/measure.sh "$(SERIES_DIR)" "$(RUN_INDEX)"

.PHONY: analyze analysis-test
analyze:
	sh docker/analyze.sh "$(SERIES)"

analysis-test:
	docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 -e MPLCONFIGDIR=/tmp/matplotlib -v "$(CURDIR):/bench" -w /bench wswt-bench-analyzer:dev python -m unittest discover -s src/analysis -p 'test_analysis*.py' -v
