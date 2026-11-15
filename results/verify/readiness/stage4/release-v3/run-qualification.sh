set -u
cd /Users/dobrov/Desktop/Code/ITMO/benchmark || exit 2
export SERIES_TLS_DIR=/Users/dobrov/Desktop/Code/ITMO/benchmark/build/series-tls-stage2._n__udb0
execution=$(mktemp -d results/verify/readiness/stage4/release-v3/qualification-execution.XXXXXXXX) || exit 2
printf 'Execution: %s\n' "$execution"
date -u +%FT%TZ > "$execution/started"
identity() {
    shasum -a 256 results/verify/diagnostic/timer-timer.2ST8NYBU/context.json "$SERIES_TLS_DIR/server/good/cert.pem" build/release-state.json docker/calibration_probe.py docker/calibration_probe_test.py results/verify/readiness/stage4/release-v3/source-inventory.json
}
finish() {
    code=$?
    trap - EXIT
    identity > "$execution/identity-after.sha256" || code=2
    if test -f "$execution/identity-before.sha256"; then
        cmp "$execution/identity-before.sha256" "$execution/identity-after.sha256" > "$execution/identity-comparison.log" 2>&1 || code=2
    fi
    date -u +%FT%TZ > "$execution/ended"
    printf '%s\n' "$code" > "$execution/exit"
    printf 'Execution: %s\nExit: %s\n' "$execution" "$code"
    tail -n 5 "$execution/stdout.log"
    exit "$code"
}
: > "$execution/stdout.log"
trap finish EXIT
trap 'exit 130' INT TERM
cp docs/readiness/stage4-qualification-v3-plan.md "$execution/plan.md"
identity > "$execution/identity-before.sha256" || exit 2
(
    set -e
    sh docker/check-release.sh 3605994e8359a70443621517e11dd2383a726f48
    python3 -B - <<'PY'
import hashlib,json
from pathlib import Path
inventory=json.loads(Path('results/verify/readiness/stage4/release-v3/source-inventory.json').read_text())
assert len(inventory)==134 and all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==s for p,s in inventory.items())
PY
    sh docker/sender-diagnostic.sh qualification
) > "$execution/stdout.log" 2> "$execution/stderr.log"
code=$?
exit "$code"
