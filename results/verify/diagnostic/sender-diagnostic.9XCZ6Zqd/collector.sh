set -eu
: "${SERIES_TLS_DIR:?set to the admitted certificate directory}"
test -f "$SERIES_TLS_DIR/server/good/cert.pem"
export BENCH_TLS_DIR="$SERIES_TLS_DIR"
mkdir -p results/verify/diagnostic
run_dir=$(mktemp -d results/verify/diagnostic/sender-diagnostic.XXXXXXXX)
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
    compose down --timeout 2 || code=1
    exec 9>&-
    if [ -n "${lock_pid:-}" ]; then wait "$lock_pid" || code=1; fi
    rm -rf "$work"
    date -u +%FT%TZ > "$run_dir/ended"
    echo "$code" > "$run_dir/exit"
    echo "$run_dir"
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
exec 2>"$run_dir/commands.log"
set -x
date -u +%FT%TZ > "$run_dir/started"
docker info --format '{{json .}}' > "$run_dir/docker-info.json"
docker ps --no-trunc > "$run_dir/containers-before.txt"
docker stats --no-stream --format '{{json .}}' > "$run_dir/stats-before.jsonl"
uname -a > "$run_dir/host.txt"
vm_stat > "$run_dir/host-memory-before.txt"
sysctl hw.ncpu hw.memsize vm.loadavg > "$run_dir/host-resources.txt"
docker run --rm --network none -v "$PWD/docker:/diagnostic:ro" wswt-bench-analyzer:dev python -B /diagnostic/sender_diagnostic_resources.py 5 > "$run_dir/idle-resources.jsonl"
git rev-parse HEAD > "$run_dir/commit"
compose up -d --no-build router browser server
. docker/links.sh
setup_links
. docker/calibration-neighbors.sh
for role in server browser; do
    name="$project-probe-$role"
    docker run -d --rm --name "$name" --cap-drop ALL --network "container:$(compose ps -q "$role")" -v "$PWD/docker:/diagnostic:ro" wswt-bench-analyzer:dev python -B /diagnostic/calibration_probe.py serve >/dev/null
    for attempt in 1 2 3 4 5; do [ "$(docker logs "$name")" != ready ] || break; sleep 1; done
    test "$(docker logs "$name")" = ready
done
docker inspect $(compose ps -q) "$project-probe-browser" "$project-probe-server" > "$run_dir/inspect.json"
seed=20261113
for collection in baseline-before r80p0-response baseline-repeat; do
    dir="$run_dir/$collection"
    mkdir "$dir"
    seed=$((seed + 2))
    profile=baseline
    if [ "$collection" = r80p0-response ]; then profile=r80p0; fi
    compose exec -T router sh /usr/local/bin/network profile "$profile" "$seed" "$((seed+1))" > "$dir/profile.txt"
    compose exec -T router tc -s -j qdisc show > "$dir/qdisc-before.json"
    for role in server browser; do
        compose exec -d router sh -c 'role=$1; echo $$ > "/tmp/$role.pid"; exec tcpdump -Q in -n -U -s 96 -i "to_$role" -w "/tmp/$role.pcap" 2>"/tmp/$role.log"' sh "$role"
        compose exec -T router timeout 5 sh -c 'until grep -q "listening on" "/tmp/$1.log"; do sleep .05; done' sh "$role"
        docker exec "$project-probe-$role" python -B /diagnostic/sender_diagnostic_resources.py 18 > "$dir/$role-resources.jsonl" &
        if [ "$role" = browser ]; then browser_sampler=$!; else server_sampler=$!; fi
    done
    compose exec -T router sh -c 'for n in $(seq 1 18); do cut -d" " -f1 /proc/uptime; tc -s -j qdisc show; cat /sys/fs/cgroup/cpu.stat /sys/fs/cgroup/memory.current /sys/fs/cgroup/memory.events; sleep 1; done' > "$dir/router-resources.txt" &
    router_sampler=$!
    docker exec "$project-probe-browser" python -B /diagnostic/sender_diagnostic_probe.py 172.28.20.10 "$(basename "$run_dir")/$collection" > "$dir/probe.json"
    wait "$browser_sampler" "$server_sampler" "$router_sampler"
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
