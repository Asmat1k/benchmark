#!/bin/sh
set -eu

cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)"
series=${1:-$(cat build/latest-experiment)}
series=$(cd "$series" && pwd -P)
mkdir -p "$series/analysis-reports"
report="comparisons-$(date -u +%Y%m%dT%H%M%SZ)-$$"
docker run --rm --network none --cpus 2 --memory 2g \
  -e PYTHONDONTWRITEBYTECODE=1 -e MPLCONFIGDIR=/tmp/matplotlib \
  -v "$PWD:/bench:ro" -v "$series:/series:ro" \
  -v "$series/analysis-reports:/reports" -w /bench wswt-bench-analyzer:dev \
  python -B -m reporting.comparisons /series --output "/reports/$report"
printf 'Report: %s/analysis-reports/%s/report.md\n' "$series" "$report"
