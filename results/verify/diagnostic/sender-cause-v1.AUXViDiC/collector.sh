set -eu
collections=baseline-scheduling
probe_script=sender_scheduling_probe.py
: "${SERIES_TLS_DIR:?set to the admitted certificate directory}"
test -f "$SERIES_TLS_DIR/server/good/cert.pem"
export BENCH_TLS_DIR="$SERIES_TLS_DIR"
mkdir -p results/verify/diagnostic
run_dir=$(mktemp -d results/verify/diagnostic/sender-cause-v1.XXXXXXXX)
project="wswt-$(basename "$run_dir" | tr '[:upper:].' '[:lower:]-')"
compose() { docker compose -p "$project" "$@"; }
work=$(mktemp -d)
analyze() { docker run --rm --network none -v "$PWD:/bench" -w /bench wswt-bench-analyzer:dev python -B "$@"; }
cleanup() {
    code=$?
    trap - EXIT
    if [ "$code" != 0 ] && [ -n "${dir:-}" ]; then
        for endpoint in server browser; do
            compose cp "router:/tmp/$endpoint.pcap" "$dir/$endpoint.interrupted.pcap" 2>/dev/null || true
            compose exec -T router cat "/tmp/$endpoint.log" > "$dir/$endpoint.interrupted.log" 2>/dev/null || true
        done
    fi
    for role in browser server; do
        name="$project-probe-$role"
        if docker container inspect "$name" >/dev/null 2>&1; then
            docker rm -f "$name" >/dev/null || code=1
        fi
    done
    if [ -n "${tracer:-}" ]; then
        touch "$dir/trace-stop"
        wait "$tracer" || code=1
        tracer=
    fi
    if [ -n "${trace_name:-}" ]; then docker rm -f "$trace_name" >/dev/null 2>&1 || true; fi
    compose down --timeout 2 || code=1
    for sampler in "${browser_sampler:-}" "${server_sampler:-}" "${router_sampler:-}"; do
        if [ -n "$sampler" ]; then wait "$sampler" || true; fi
    done
    exec 9>&-
    if [ -n "${lock_pid:-}" ]; then wait "$lock_pid" || code=1; fi
    rm -rf "$work"
    date -u +%FT%TZ > "$run_dir/ended"
    echo "$code" > "$run_dir/exit"
    echo "$run_dir"
    if command -v source_snapshot >/dev/null 2>&1; then source_snapshot after; fi
    set +x
    python3 - "$run_dir" <<'PYTHON'
import hashlib
import json
from pathlib import Path
import sys
run = Path(sys.argv[1])
rows = [dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        for p in sorted(run.rglob('*')) if p.is_file() and p.name != 'captured.json']
(run/'captured.json').write_text(json.dumps(rows,indent=2)+'\n')
PYTHON
    exit "$code"
}
trap cleanup EXIT
trap 'exit 130' INT TERM
mkfifo "$work/lock"
docker run --rm -i --network none -v "$PWD:/bench" -w /bench wswt-bench-analyzer:dev python -B src/analysis/series.py hold < "$work/lock" > "$work/status" &
lock_pid=$!
exec 9>"$work/lock"
for attempt in 1 2 3 4 5 6 7 8 9 10; do [ ! -s "$work/status" ] || break; sleep 1; done
test "$(cat "$work/status")" = locked
cp "$0" "$run_dir/collector.sh"
cp results/verify/readiness/stage4/cause-diagnostic-v1/plan.md "$run_dir/plan.md"
cp -R results/verify/readiness/stage4/cause-diagnostic-v1/tools "$run_dir/diagnostic-tools"
source_snapshot() {
    python3 - "$run_dir/sources-$1.json" <<'PYTHON'
import hashlib
import json
from pathlib import Path
import shutil
import sys
files = ['docker/calibration_probe.py', 'docker/sender_diagnostic_probe.py',
         'docker/sender_diagnostic_plain.py', 'docker/sender_diagnostic_resources.py',
         'docker/sender-diagnostic.sh', 'docker/sender-scheduling.sh',
         'docker/sender_scheduling_probe.py', 'docker/sender_scheduling_trace.py', 'docker/sender_scheduling_check.py', 'src/analysis/sender_quality.py', 'configs/thresholds.json', 'docker/links.sh', 'docker/calibration-neighbors.sh',
         'docker/network.sh', 'compose.yaml', 'configs/profiles.json']
if sys.argv[1].endswith('sources-before.json'):
    destination = Path(sys.argv[1]).parent / 'sources'
    for name in files:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(name, target)
Path(sys.argv[1]).write_text(json.dumps({p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in files},indent=2)+'\n')
PYTHON
}
source_snapshot before
exec 2>"$run_dir/commands.log"
set -x
date -u +%FT%TZ > "$run_dir/started"
docker info --format '{{json .}}' > "$run_dir/docker-info.json"
docker ps --no-trunc > "$run_dir/containers-before.txt"
docker stats --no-stream --format '{{json .}}' > "$run_dir/stats-before.jsonl"
uname -a > "$run_dir/host.txt"
vm_stat > "$run_dir/host-memory-before.txt"
sysctl hw.ncpu hw.memsize vm.loadavg > "$run_dir/host-resources.txt"
docker run --rm --network none -v "$PWD/results/verify/readiness/stage4/cause-diagnostic-v1/tools:/diagnostic:ro" wswt-bench-analyzer:dev python -B /diagnostic/sender_diagnostic_resources.py 5 > "$run_dir/idle-resources.jsonl"
git rev-parse HEAD > "$run_dir/commit"
compose up -d --no-build router browser server
. docker/links.sh
setup_links
. docker/calibration-neighbors.sh
for role in server browser; do
    name="$project-probe-$role"
    docker run -d --rm --name "$name" --cap-drop ALL --network "container:$(compose ps -q "$role")" -v "$PWD/results/verify/readiness/stage4/cause-diagnostic-v1/tools:/diagnostic:ro" wswt-bench-analyzer:dev python -B /diagnostic/calibration_probe.py serve >/dev/null
    for attempt in 1 2 3 4 5; do [ "$(docker logs "$name")" != ready ] || break; sleep 1; done
    test "$(docker logs "$name")" = ready
done
docker inspect $(compose ps -q) "$project-probe-browser" "$project-probe-server" > "$run_dir/inspect.json"
seed=20261113
for collection in $collections; do
    dir="$run_dir/$collection"
    mkdir "$dir"
    seed=$((seed + 2))
    profile=baseline
    compose exec -T router sh /usr/local/bin/network profile "$profile" "$seed" "$((seed+1))" > "$dir/profile.txt"
    compose exec -T router tc -s -j qdisc show > "$dir/qdisc-before.json"
    for role in server browser; do
        compose exec -d router sh -c 'role=$1; echo $$ > "/tmp/$role.pid"; exec tcpdump -Q in -n -U -s 96 -i "to_$role" -w "/tmp/$role.pcap" 2>"/tmp/$role.log"' sh "$role"
        compose exec -T router timeout 5 sh -c 'until grep -q "listening on" "/tmp/$1.log"; do sleep .05; done' sh "$role"
        docker exec "$project-probe-$role" python -B /diagnostic/sender_diagnostic_resources.py 180 /tmp/resources-ready /tmp/resources-stop > "$dir/$role-resources.jsonl" &
        if [ "$role" = browser ]; then browser_sampler=$!; else server_sampler=$!; fi
    done
    compose exec -T router sh -c 'for n in $(seq 1 180); do cut -d" " -f1 /proc/uptime; tc -s -j qdisc show; cat /sys/fs/cgroup/cpu.stat /sys/fs/cgroup/memory.current /sys/fs/cgroup/memory.events; echo snapshot-end; test ! -f /tmp/resources-stop || break; sleep 1; done' > "$dir/router-resources.txt" &
    router_sampler=$!
    for role in browser server; do
        compose exec -T "$role" ip route > "$dir/$role-route.txt" 2>/dev/null || docker run --rm --cap-drop ALL --network "container:$(compose ps -q "$role")" --entrypoint ip wswt-bench-router:dev route > "$dir/$role-route.txt"
    done
    for attempt in $(seq 1 100); do
        if docker exec "$project-probe-browser" test -f /tmp/resources-ready && docker exec "$project-probe-server" test -f /tmp/resources-ready && grep -q '^snapshot-end$' "$dir/router-resources.txt"; then break; fi
        sleep .1
    done
    docker exec "$project-probe-browser" test -f /tmp/resources-ready
    docker exec "$project-probe-server" test -f /tmp/resources-ready
    grep -q '^snapshot-end$' "$dir/router-resources.txt"
    token=$(basename "$run_dir")
    docker exec "$project-probe-browser" python -B "/diagnostic/$probe_script" 172.28.20.10 "$token" /tmp/sender-ready /tmp/sender-go > "$dir/probe.json" &
    sender=$!
    for attempt in $(seq 1 100); do
        docker exec "$project-probe-browser" test -f /tmp/sender-ready && break
        sleep .1
    done
    docker cp "$project-probe-browser:/tmp/sender-ready" "$dir/sender-ready.json"
    trace_name="$project-trace"
    docker run --rm --name "$trace_name" --network none --privileged --pid host -v "$PWD/results/verify/readiness/stage4/cause-diagnostic-v1/tools:/diagnostic:ro" -v "$PWD/$dir:/out" wswt-bench-analyzer:dev python -B /diagnostic/sender_scheduling_trace.py "$token" /out > "$dir/tracer.log" 2>&1 &
    tracer=$!
    for attempt in $(seq 1 100); do
        [ ! -f "$dir/trace-ready.json" ] || break
        kill -0 "$tracer"
        sleep .1
    done
    test -f "$dir/trace-ready.json"
    docker exec "$project-probe-browser" touch /tmp/sender-go
    wait "$sender"
    touch "$dir/trace-stop"
    wait "$tracer"
    tracer=
    trace_name=

    for role in browser server; do docker exec "$project-probe-$role" touch /tmp/resources-stop; done
    compose exec -T router touch /tmp/resources-stop
    wait "$browser_sampler"
    browser_sampler=
    wait "$server_sampler"
    server_sampler=
    wait "$router_sampler"
    router_sampler=

    for role in server browser; do
        compose exec -T router sh -c 'pid=$(cat "/tmp/$1.pid"); kill -INT "$pid"; timeout 5 sh -c "while kill -0 $pid 2>/dev/null; do sleep .05; done"' sh "$role"
        compose cp "router:/tmp/$role.pcap" "$dir/$role.pcap"
        compose exec -T router cat "/tmp/$role.log" > "$dir/$role.log"
        grep -x '0 packets dropped by kernel' "$dir/$role.log" >/dev/null
        compose exec -T router rm "/tmp/$role.log"
    done
    compose exec -T router tc -s -j qdisc show > "$dir/qdisc-after.json"
done
for role in browser server; do
    compose exec -T router ip -j neigh show dev "to_$role" > "$run_dir/router-$role-neighbors-after.json"
    docker run --rm --cap-drop ALL --network "container:$(compose ps -q "$role")" --entrypoint ip wswt-bench-router:dev -j neigh show dev bench0 > "$run_dir/$role-neighbors-after.json"
done
docker stats --no-stream --format '{{json .}}' > "$run_dir/stats-after.jsonl"
vm_stat > "$run_dir/host-memory-after.txt"
