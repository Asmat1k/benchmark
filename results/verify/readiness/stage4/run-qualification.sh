set -u
cd /Users/dobrov/Desktop/Code/ITMO/benchmark || exit 2
export SERIES_TLS_DIR=/Users/dobrov/Desktop/Code/ITMO/benchmark/build/series-tls-stage2._n__udb0
execution=$(mktemp -d results/verify/readiness/stage4/qualification-execution.XXXXXXXX) || exit 2
printf 'Execution: %s\n' "$execution"
date -u +%FT%TZ > "$execution/started"
finish() {
    code=$?
    trap - EXIT
    date -u +%FT%TZ > "$execution/ended"
    printf '%s\n' "$code" > "$execution/exit"
    printf 'Execution: %s\nExit: %s\n' "$execution" "$code"
    tail -n 5 "$execution/stdout.log"
    exit "$code"
}
trap finish EXIT
trap 'exit 130' INT TERM
(
    set -e
    sh docker/check-release.sh 0fee7038dc2597f451f4e2c57381aa2d185dd5b4
    shasum -a 256 results/verify/diagnostic/timer-timer.2ST8NYBU/context.json "$SERIES_TLS_DIR/server/good/cert.pem" build/release-state.json > "$execution/identity-before.sha256"
    sh docker/sender-diagnostic.sh qualification
    shasum -a 256 results/verify/diagnostic/timer-timer.2ST8NYBU/context.json "$SERIES_TLS_DIR/server/good/cert.pem" build/release-state.json > "$execution/identity-after.sha256"
    cmp "$execution/identity-before.sha256" "$execution/identity-after.sha256"
) > "$execution/stdout.log" 2> "$execution/stderr.log"
code=$?
exit "$code"
