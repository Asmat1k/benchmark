#!/bin/sh
set -eu
test -n "${1:-}" || { echo 'Usage: make analyze SERIES=path/to/series' >&2; exit 2; }
test -d "$1" || { echo 'Series directory missing' >&2; exit 2; }
analysis_series_path=$(cd "$1" && pwd -P)
docker run --rm --network none --cpus 2 --memory 2g \
  -e PYTHONDONTWRITEBYTECODE=1 -e MPLCONFIGDIR=/tmp/matplotlib \
  -v "$PWD:/bench" -v "$analysis_series_path:/series" -w /bench wswt-bench-analyzer:dev \
  python src/analysis/analyze.py /series
