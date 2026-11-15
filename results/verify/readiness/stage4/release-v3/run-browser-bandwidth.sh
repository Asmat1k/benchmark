set -u
cd /Users/dobrov/Desktop/Code/ITMO/benchmark || exit 2
export SERIES_TLS_DIR=/Users/dobrov/Desktop/Code/ITMO/benchmark/build/series-tls-stage2._n__udb0
BW_RUN=results/verify/diagnostic/browser-bandwidth.oc6op_bb
export BW_RUN
test ! -e "$BW_RUN/context.json" && test ! -e "$BW_RUN/collection-started" || { echo 'This fixed collection already started; do not repeat it.' >&2; exit 2; }
execution=$(mktemp -d results/verify/readiness/stage4/release-v3/bandwidth-execution.XXXXXXXX) || exit 2
printf 'Execution: %s\nBW_RUN: %s\n' "$execution" "$BW_RUN"
date -u +%FT%TZ > "$execution/started"
cp results/verify/readiness/stage4/release-v3/bandwidth-plan.json "$execution/plan.json"
identity() {
    python3 -B - <<'PY'
import hashlib,json,subprocess
from pathlib import Path
base=Path('results/verify/readiness/stage4/release-v3')
files=list(json.loads((base/'source-inventory.json').read_text()))+['results/verify/diagnostic/timer-timer.2ST8NYBU/context.json','build/series-tls-stage2._n__udb0/server/good/cert.pem','build/release-state.json']
images=json.loads(subprocess.check_output(['docker','image','inspect','wswt-bench-server:dev','wswt-bench-browser:dev','wswt-bench-router:dev','wswt-bench-analyzer:dev'],text=True))
print(json.dumps(dict(files={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in files},images=[i['Id'] for i in images]),sort_keys=True))
PY
}
finish() {
    code=$?
    trap - EXIT
    identity > "$execution/identity-after.json" || code=2
    if test -f "$execution/identity-before.json"; then
        cmp "$execution/identity-before.json" "$execution/identity-after.json" > "$execution/identity-comparison.log" 2>&1 || code=2
    fi
    if test "$code" != 0 && test ! -e "$BW_RUN/STOP"; then
        printf 'Browser bandwidth collection failed, exit %s; preserve partial data; no retry. Execution %s\n' "$code" "$execution" > "$BW_RUN/STOP"
    fi
    date -u +%FT%TZ > "$execution/ended"
    printf '%s\n' "$code" > "$execution/exit"
    printf 'Execution: %s\nBW_RUN: %s\nExit: %s\n' "$execution" "$BW_RUN" "$code"
    exit "$code"
}
trap finish EXIT
trap 'exit 130' INT TERM
(
    set -e
    sh docker/check-release.sh 3605994e8359a70443621517e11dd2383a726f48
    python3 -B - <<'PY'
import hashlib,json,os,subprocess
from pathlib import Path
base=Path('results/verify/readiness/stage4/release-v3');run=Path(os.environ['BW_RUN'])
inventory=json.loads((base/'source-inventory.json').read_text());assert len(inventory)==134 and all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in inventory.items())
plan=json.loads((base/'bandwidth-plan.json').read_text());assert hashlib.sha256((run/'schedule.json').read_bytes()).hexdigest()==plan['schedule_sha256']
assert json.loads((base/'qualification-Mbdvg8v6-review.json').read_text())['status']=='passed'
images=json.loads(subprocess.check_output(['docker','image','inspect','wswt-bench-server:dev','wswt-bench-browser:dev','wswt-bench-router:dev','wswt-bench-analyzer:dev'],text=True))
expected=json.loads(Path('results/verify/readiness/stage2-preflight/release-evidence.json').read_text());assert [i['Id'] for i in images]==[i['image_id'] for i in expected]
PY
    identity > "$execution/identity-before.json"
    date -u +%FT%TZ > "$BW_RUN/collection-started"
    for index in 0 1 2; do
        date -u +%FT%TZ > "$execution/index-$index.started"
        sh docker/check-release.sh 3605994e8359a70443621517e11dd2383a726f48
        sh docker/measure.sh "$BW_RUN" "$index"
        date -u +%FT%TZ > "$execution/index-$index.ended"
        cmp "$BW_RUN/context.json" results/verify/diagnostic/timer-timer.2ST8NYBU/context.json
    done
) > "$execution/stdout.log" 2> "$execution/stderr.log"
code=$?
exit "$code"
