set -eu
: "${SERIES_TLS_DIR:?set to the admitted certificate directory}"
test -f "$SERIES_TLS_DIR/server/good/cert.pem"
export BENCH_TLS_DIR="$SERIES_TLS_DIR"
mkdir -p results/verify/diagnostic
run_dir=$(mktemp -d results/verify/diagnostic/calibration.XXXXXXXX)
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
    docker run -d --rm --name "$name" --cap-drop ALL --network "container:$(compose ps -q "$role")" -v "$PWD/docker/calibration_probe.py:/probe.py:ro" wswt-bench-analyzer:dev python -B /probe.py serve >/dev/null
    for attempt in 1 2 3 4 5; do [ "$(docker logs "$name")" != ready ] || break; sleep 1; done
    test "$(docker logs "$name")" = ready
done
seed=20261108
profile() {
    seed=$((seed + 2))
    compose exec -T router sh /usr/local/bin/network profile "$1" "$seed" "$((seed+1))" > "$dir/profile.txt"
}
qdisc() { compose exec -T router tc -s -j qdisc show > "$dir/qdisc-$1.json"; }
for collection in baseline-before r20p0-before r20p1-before r80p0-before r80p1-before r20p0-latency r20p1-latency r80p0-latency r80p1-latency r20p0-after r20p1-after r80p0-after r80p1-after baseline-after; do
    dir="$run_dir/$collection"
    mkdir "$dir"
    profile "${collection%-*}"
    qdisc before
    for role in server browser; do
        compose exec -d router sh -c 'role=$1; echo $$ > "/tmp/$role.pid"; exec tcpdump -Q in -n -U -s 96 -i "to_$role" -w "/tmp/$role.pcap" 2>"/tmp/$role.log"' sh "$role"
        compose exec -T router timeout 5 sh -c 'until grep -q "listening on" "/tmp/$1.log"; do sleep .05; done' sh "$role"
    done
    docker exec "$project-probe-browser" python -B /probe.py echo 172.28.20.10 "$(basename "$run_dir")/$collection" > "$dir/probe.json"
    for role in server browser; do
        compose exec -T router sh -c 'pid=$(cat "/tmp/$1.pid"); kill -INT "$pid"; timeout 5 sh -c "while kill -0 $pid 2>/dev/null; do sleep .05; done"' sh "$role"
        compose cp "router:/tmp/$role.pcap" "$dir/$role.pcap"
        compose exec -T router cat "/tmp/$role.log" > "$dir/$role.log"
        grep -x '0 packets dropped by kernel' "$dir/$role.log" >/dev/null
        compose exec -T router rm "/tmp/$role.log"
    done
    qdisc after
done
for loss in 0 1; do
    for direction in forward reverse; do
        dir="$run_dir/saturation-$loss-$direction"
        mkdir "$dir"
        profile "r20p$loss"
        src=browser; dst=server; ip=172.28.20.10
        if [ "$direction" = reverse ]; then src=server; dst=browser; ip=172.28.10.10; fi
        docker exec "$project-probe-$src" python -B /probe.py saturate "$ip" "$(basename "$run_dir")/$(basename "$dir")" > "$dir/probe.json" &
        sender=$!
        sleep 5
        compose exec -T router sh -eu -c '
          sample() {
            cut -d" " -f1 /proc/uptime
            cat "/sys/class/net/to_$1/statistics/rx_bytes"
            tc -s -j qdisc show | jq -ce --arg dev "to_$2" ".[]|select(.kind==\"netem\" and .dev==\$dev)"
          }
          sample "$1" "$2"; sleep 61; sample "$1" "$2"
        ' sh "$src" "$dst" > "$dir/window.txt"
        wait "$sender"
        sleep 2
        qdisc stable
    done
done
context after
analyze docker/calibration_report.py seal "$run_dir"
echo "$run_dir"
