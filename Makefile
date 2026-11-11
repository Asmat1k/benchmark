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
