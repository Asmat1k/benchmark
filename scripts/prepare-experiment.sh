#!/bin/sh
set -eu

cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)"
unset SERIES_TLS_DIR

make build
make smoke
make measurement-smoke

series_id="final-$(date -u +%Y%m%dT%H%M%SZ)-$$"
check="results/verify/measurement/$series_id-check"
series="results/main/$series_id"
SERIES_TLS_DIR="$PWD/build/series-tls/$series_id"
export SERIES_TLS_DIR
mkdir -p "$SERIES_TLS_DIR"

docker run --rm --network none -v "$SERIES_TLS_DIR:/out" \
  --entrypoint testcert wswt-bench-server:dev /out
docker run --rm --network none -v "$PWD:/bench" -w /bench \
  wswt-bench-analyzer:dev python -B -m execution.schedule smoke "$check" \
  --blocks 1 --sessions 1 --baseline
make measure SERIES_DIR="$check" RUN_INDEX=0
make exploratory-prepare SERIES_DIR="$series" \
  ENVIRONMENT="$check/context.json" SERIES_TLS_DIR="$SERIES_TLS_DIR"

latest=$(mktemp build/latest-experiment.XXXXXXXX)
printf '%s\n' "$series" > "$latest"
mv "$latest" build/latest-experiment
printf 'Prepared: %s\nStart with: ./scripts/start-experiment.sh\n' "$series"
