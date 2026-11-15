#!/bin/sh
set -eu

cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)"
if [ ! -f build/latest-experiment ]; then
  echo 'No prepared series. Run ./scripts/prepare-experiment.sh first.' >&2
  exit 2
fi
series=$(cat build/latest-experiment)
case "$series" in
  results/main/final-*) ;;
  *) echo 'Invalid prepared series path.' >&2; exit 2 ;;
esac
case "$series" in
  *..*|*[!A-Za-z0-9_./-]*) exit 2 ;;
esac
test -f "$series/admission.json"
SERIES_TLS_DIR="$PWD/build/series-tls/$(basename "$series")"
export SERIES_TLS_DIR
test -f "$SERIES_TLS_DIR/server/good/cert.pem"

set -- make experiment SERIES_DIR="$series" ALLOW_REAL_EXPERIMENTS=yes
if [ "$(uname -s)" = Darwin ]; then
  set -- caffeinate -ims "$@"
fi
nohup "$@" >> "$series/overnight.log" 2>&1 < /dev/null &
printf 'Started PID: %s\nSeries: %s\nLog: %s/overnight.log\n' "$!" "$series" "$series"
