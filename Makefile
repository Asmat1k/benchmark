.PHONY: build smoke
build:
	docker compose build

smoke:
	sh docker/smoke.sh
