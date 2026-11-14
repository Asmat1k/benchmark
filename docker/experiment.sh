set -eu
series_dir=$1
allow=$2
test "$allow" = yes || { echo 'Explicit ALLOW_REAL_EXPERIMENTS=yes required' >&2; exit 2; }
case "$series_dir" in results/verify/raw/*|results/pilot/*|results/main/*) ;; *) exit 2 ;; esac
case "$series_dir" in *..*|*[!A-Za-z0-9_./-]*) exit 2 ;; esac
test -n "${SERIES_TLS_DIR:-}" || { echo 'Persistent SERIES_TLS_DIR required' >&2; exit 2; }
sh docker/release-state.sh
controller_work=$(mktemp -d "${TMPDIR:-/tmp}/wswt-controller.XXXXXXXX")
mkfifo "$controller_work/input"
BENCH_CONTROLLER_RESPONSE="$controller_work/output"
export BENCH_CONTROLLER_RESPONSE
docker run --rm -i --network none -e PYTHONDONTWRITEBYTECODE=1 -v "$PWD:/bench" -v "$PWD:$PWD" -w /bench wswt-bench-analyzer:dev python -B src/analysis/controller.py "$series_dir" < "$controller_work/input" > "$BENCH_CONTROLLER_RESPONSE" &
BENCH_CONTROLLER_PID=$!
export BENCH_CONTROLLER_PID
exec 8> "$controller_work/input"
finish_controller() {
    code=$?
    trap - EXIT
    exec 8>&-
    wait "$BENCH_CONTROLLER_PID" || true
    rm -rf "$controller_work"
    exit "$code"
}
trap finish_controller EXIT
trap 'exit 130' INT TERM
while [ ! -s "$BENCH_CONTROLLER_RESPONSE" ]; do
    kill -0 "$BENCH_CONTROLLER_PID" 2>/dev/null || exit 2
    sleep 1
done
grep -q '"value": "ready"' "$BENCH_CONTROLLER_RESPONSE" || { cat "$BENCH_CONTROLLER_RESPONSE" >&2; exit 2; }
BENCH_CONTROLLER_COMMIT=$(sed -n '1s/.*"commit": "\([a-f0-9]*\)".*/\1/p' "$BENCH_CONTROLLER_RESPONSE")
test "${#BENCH_CONTROLLER_COMMIT}" = 40 || exit 2
export BENCH_CONTROLLER_COMMIT
. docker/controller-client.sh
while :; do
    index=$(controller_request '{"action":"next"}') || exit $?
    test "$index" != complete || exit 0
    case "$index" in ''|*[!0-9]*) exit 2 ;; esac
    code=0
    sh docker/measure.sh "$series_dir" "$index" || code=$?
    if [ "$code" = 3 ]; then exit 2; fi
    test "$code" = 0 || exit "$code"
done
