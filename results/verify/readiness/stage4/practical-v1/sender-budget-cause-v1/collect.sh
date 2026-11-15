set -eu
: "${SERIES_TLS_DIR:?set to the admitted certificate directory}"
test -f "$SERIES_TLS_DIR/server/good/cert.pem"
export BENCH_TLS_DIR="$SERIES_TLS_DIR"
mkdir -p results/verify/diagnostic
run_dir=$(mktemp -d results/verify/diagnostic/sender-budget-cause.XXXXXXXX)
project="wswt-$(basename "$run_dir" | tr '[:upper:].' '[:lower:]-')"
compose() { docker compose -p "$project" "$@"; }
work=$(mktemp -d)
analyze() { docker run --rm --network none -v "$PWD:/bench" -w /bench wswt-bench-analyzer:dev python -B "$@"; }
cleanup() {
    code=$?
    trap - EXIT
    if [ "$code" != 0 ] && [ -n "${dir:-}" ]; then
        docker exec "$project-probe-browser" sh -c 'if test -f /tmp/diagnostic-probe.pid; then kill -TERM "$(cat /tmp/diagnostic-probe.pid)"; sleep 1; fi' > "$dir/partial-signal.log" 2>&1 || true
        docker cp "$project-probe-browser:/tmp/diagnostic-probe.partial.json" "$dir/probe.interrupted.json" 2>> "$dir/partial-signal.log" || true
    fi
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
    compose down --timeout 2 || code=1
    exec 9>&-
    if [ -n "${lock_pid:-}" ]; then wait "$lock_pid" || code=1; fi
    rm -rf "$work"
    date -u +%FT%TZ > "$run_dir/ended"
    echo "$code" > "$run_dir/exit"
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
date -u +%FT%TZ > "$run_dir/started"
git rev-parse HEAD > "$run_dir/commit"
cp results/verify/readiness/stage4/practical-v1/sender-budget-cause-v1/plan.md "$run_dir/diagnostic-plan.md"
cp results/verify/readiness/stage4/practical-v1/sender-budget-cause-v1/probe.py "$run_dir/diagnostic-probe.py"
cp "$0" "$run_dir/diagnostic-collector.sh"
shasum -a 256 "$run_dir/diagnostic-plan.md" "$run_dir/diagnostic-probe.py" "$run_dir/diagnostic-collector.sh" > "$run_dir/diagnostic-SHA256SUMS"
compose up -d --no-build router browser server
. docker/links.sh
setup_links
. docker/calibration-neighbors.sh
context() {
    uname -a > "$run_dir/host.txt"
    docker info --format '{"kernel":"{{.KernelVersion}}","platform":"{{.Architecture}}","engine":"{{.ServerVersion}}","cpus":{{.NCPU}},"mem":{{.MemTotal}}}' > "$run_dir/vm.json"
    docker inspect --format '{"id":"{{.Image}}","role":{{json .Name}},"cpu":{{.HostConfig.NanoCpus}},"memory":{{.HostConfig.Memory}},"shm":{{.HostConfig.ShmSize}}}' $(compose ps -q) | awk 'BEGIN{print "["} NR>1{print ","} {print} END{print "]"}' > "$run_dir/limits.json"
    compose exec -T server cat /certs/good/cert.pem > "$run_dir/leaf.pem"
    analyze docker/calibration_report.py context "$run_dir" "$1"
}
context before
for role in server browser; do
    name="$project-probe-$role"
    docker run -d --rm --name "$name" --cap-drop ALL --network "container:$(compose ps -q "$role")" -v "$PWD/docker/calibration_probe.py:/probe.py:ro" -v "$PWD/docker:/bench/docker:ro" -v "$PWD/results/verify/readiness/stage4/practical-v1/sender-budget-cause-v1/probe.py:/candidate.py:ro" -w /bench wswt-bench-analyzer:dev python -B /probe.py serve >/dev/null
    for attempt in 1 2 3 4 5; do [ "$(docker logs "$name")" != ready ] || break; sleep 1; done
    test "$(docker logs "$name")" = ready
done
docker exec "$project-probe-browser" sh -c 'if test -r /proc/sys/kernel/sched_schedstats; then printf "available\n"; cat /proc/sys/kernel/sched_schedstats; else printf "unavailable\n"; fi' > "$run_dir/sched-schedstats.txt"
seed=20261132
profile() {
    seed=$((seed + 2))
    compose exec -T router sh /usr/local/bin/network profile "$1" "$seed" "$((seed+1))" > "$dir/profile.txt"
}
qdisc() { compose exec -T router tc -s -j qdisc show > "$dir/qdisc-$1.json"; }
for collection in r80p1-after; do
    dir="$run_dir/$collection"
    mkdir "$dir"
    profile "${collection%-*}"
    qdisc before
    for role in server browser; do
        compose exec -d router sh -c 'role=$1; echo $$ > "/tmp/$role.pid"; exec tcpdump -Q in -n -U -s 96 -i "to_$role" -w "/tmp/$role.pcap" 2>"/tmp/$role.log"' sh "$role"
        compose exec -T router timeout 5 sh -c 'until grep -q "listening on" "/tmp/$1.log"; do sleep .05; done' sh "$role"
    done
    docker exec "$project-probe-browser" python -B /candidate.py 172.28.20.10 "$(basename "$run_dir")/$collection" > "$dir/probe.json"
    for role in server browser; do
        compose exec -T router sh -c 'pid=$(cat "/tmp/$1.pid"); kill -INT "$pid"; timeout 5 sh -c "while kill -0 $pid 2>/dev/null; do sleep .05; done"' sh "$role"
        compose cp "router:/tmp/$role.pcap" "$dir/$role.pcap"
        compose exec -T router cat "/tmp/$role.log" > "$dir/$role.log"
        grep -x '0 packets dropped by kernel' "$dir/$role.log" >/dev/null
        compose exec -T router rm "/tmp/$role.log"
    done
    qdisc after
done
context after
analyze docker/calibration_report.py seal "$run_dir"
echo "$run_dir"
