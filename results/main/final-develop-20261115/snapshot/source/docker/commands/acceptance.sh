set -eu
sh docker/lib/release-state.sh
docker run --rm --network none -e PYTHONDONTWRITEBYTECODE=1 -v "$PWD:/bench" -w /bench wswt-bench-analyzer:dev python -B src/analysis/experiments.py "$@"
