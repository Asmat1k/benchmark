set -eu
series_dir=$1
index=$2
case "$series_dir" in results/verify/measurement/*|results/verify/diagnostic/*|results/verify/raw/*|results/pilot/*|results/main/*) ;; *) exit 2 ;; esac
case "$series_dir" in *..*|*[!A-Za-z0-9_./-]*) exit 2 ;; esac
case "$index" in ''|*[!0-9]*) exit 2 ;; esac
test -f "$series_dir/schedule.json"
mkdir -p build
work=$(mktemp -d "${TMPDIR:-/tmp}/wswt-measure.XXXXXXXX")
stage=prepare
prepared=0
project="wswt-d3-$(basename "$work" | tr '[:upper:].' '[:lower:]-')"
run_dir="$series_dir/$project.partial"
compose() { docker compose -p "$project" "$@"; }
analyze() {
    if [ -n "${BENCH_CONTROLLER_RESPONSE:-}" ] && [ "$1" = src/analysis/record.py ]; then
        . docker/controller-client.sh
        controller_request "{\"action\":\"$2\",\"index\":$4,\"partial\":\"$5\"}"
        return $?
    fi
    docker run --rm --network none -v "$PWD:/bench" -w /bench wswt-bench-analyzer:dev python -B "$@"
}
. docker/measurement-cleanup.sh
trap cleanup EXIT
trap 'exit 130' TERM INT
mkfifo "$work/lock-input"
docker run --rm -i --network none -v "$PWD:/bench" -w /bench wswt-bench-analyzer:dev python -B src/analysis/series.py hold < "$work/lock-input" > "$work/lock-status" &
lock_pid=$!
exec 9> "$work/lock-input"
for attempt in 1 2 3 4 5 6 7 8 9 10; do
    if [ -s "$work/lock-status" ]; then break; fi
    sleep 1
done
test "$(cat "$work/lock-status")" = locked || { echo "Measurement lock held" >&2; exit 2; }
BENCH_TLS_DIR=${SERIES_TLS_DIR:-$work}
export BENCH_TLS_DIR
mkdir "$run_dir"
selection=$(analyze src/analysis/record.py prepare "$series_dir" "$index" "$run_dir")
set -- $selection
profile=$1; forward=$2; reverse=$3; run_id=$4
prepared=1
test ! -e "$series_dir/raw/$run_id"
run_timeout=$5
if [ "$run_timeout" = 90 ]; then test -n "${SERIES_TLS_DIR:-}"; fi
if [ -z "${SERIES_TLS_DIR:-}" ]; then
    docker run --rm --network none -v "$work:/out" --entrypoint testcert wswt-bench-server:dev /out
fi
date -u +%Y-%m-%dT%H:%M:%SZ > "$run_dir/started"
git rev-parse HEAD > "$run_dir/commit"
git status --porcelain -- Makefile compose.yaml src docker docs/schemas docs/protocol.md configs/plan.json configs/profiles.json configs/thresholds.json > "$run_dir/dirty"
cp "$BENCH_TLS_DIR/server/good/cert.pem" "$run_dir/leaf.pem"
uname -a >"$run_dir/host.txt"
docker info --format '{"kernel":"{{.KernelVersion}}","platform":"{{.Architecture}}","engine":"{{.ServerVersion}}","cpus":{{.NCPU}},"mem":{{.MemTotal}}}' > "$run_dir/vm.json"
stage=network
if [ -n "${BENCH_CONTROLLER_RESPONSE:-}" ]; then
    sh docker/check-release.sh "${BENCH_CONTROLLER_COMMIT:-}"
fi
compose up -d --no-build router server browser
. docker/links.sh
setup_links
compose exec -T router sh /usr/local/bin/network profile "$profile" "$forward" "$reverse" >"$run_dir/profile.txt"
context() {
uname -a > "$run_dir/host.txt"
docker info --format '{"kernel":"{{.KernelVersion}}","platform":"{{.Architecture}}","engine":"{{.ServerVersion}}","cpus":{{.NCPU}},"mem":{{.MemTotal}}}' > "$run_dir/vm.json"
docker inspect --format '{{json .HostConfig.NanoCpus}} {{.HostConfig.Memory}} {{.HostConfig.ShmSize}}' $(compose ps -q) > "$run_dir/limits.txt"
docker inspect --format '{{json .Name}}' $(compose ps -q) > "$run_dir/service-names.txt"
docker inspect --format '{"id":"{{.Image}}","role":{{json .Name}},"cpu":{{.HostConfig.NanoCpus}},"memory":{{.HostConfig.Memory}},"shm":{{.HostConfig.ShmSize}}}' $(compose ps -q) | awk 'BEGIN {print "["} NR>1 {print ","} {print} END{print "]"}' > "$run_dir/limits.json"
cp "$run_dir/limits.json" "$run_dir/images.json"
compose exec -T server cat /server-build.txt > "$run_dir/server-build.txt"
stage=context
analyze src/analysis/record.py context "$series_dir" "$index" "$run_dir"
}
context
capture() {
    compose exec -T router cat /proc/sys/net/ipv4/ip_forward > "$run_dir/forward-$1"
    compose exec -T router tc -s -j qdisc show > "$run_dir/qdisc-$1.json"
    compose exec -T router sh -c 'for iface in to_browser to_server; do ethtool -k "$iface"; ip -d link show "$iface"; done' > "$run_dir/router-links-$1.txt"
    for role in browser server; do
        case "$role" in browser) peer=20 ;; server) peer=10 ;; esac
        docker run --rm --entrypoint sh --network "container:$(compose ps -q "$role")" wswt-bench-router:dev -c "ip route get 172.28.$peer.10" > "$run_dir/$role-route-$1.txt"
        docker run --rm --entrypoint sh --network "container:$(compose ps -q "$role")" wswt-bench-router:dev -c 'ethtool -k bench0; ip -d link show bench0' > "$run_dir/$role-settings-$1.txt"
    done
}
capture before
for role in browser server router; do
    compose cp docker/sample.sh "$role:/tmp/sample.sh"
    compose cp docker/check-sample.sh "$role:/tmp/check-sample.sh"
    compose exec -d -e ROLE="$role" -e RUN_ID="$run_id" "$role" sh -c 'echo $$ >/tmp/sampler.pid; exec sh /tmp/sample.sh >/tmp/resources.jsonl 2>/tmp/resources-error.txt'
done
compose cp "$run_dir/run.json" browser:/tmp/run.json
sleep 3
for role in browser server router; do
    compose exec -T "$role" sh /tmp/check-sample.sh fresh >/dev/null
    compose exec -T "$role" cat /tmp/resources.jsonl > "$run_dir/$role-baseline.jsonl"
done
if [ -f "$run_dir/collect-backlog" ]; then
    compose cp docker/sample-backlog.sh router:/tmp/sample-backlog.sh
    compose exec -d router sh -c 'exec sh /tmp/sample-backlog.sh >/tmp/backlog.jsonl'
    sleep 1
fi
compose exec -T router awk '{printf "%.0f\n", $1*1000000}' /proc/uptime > "$run_dir/resource-start"
monitoring=$(cat "$run_dir/monitoring-mode")
if [ "$monitoring" = off ]; then
    cp "$run_dir/resource-start" "$run_dir/unobserved-start"
    for role in browser server router; do
        compose exec -T "$role" sh -c 'kill $(cat /tmp/sampler.pid); cat /sys/fs/cgroup/memory.events' > "$run_dir/$role-oom-before.txt"
    done
fi
stage=browser
timer=no
if [ -f "$run_dir/collect-timer" ]; then timer=yes; fi
compose exec -T -e BENCH_TIMER="$timer" -e BENCH_TIMEOUT="$run_timeout" browser sh /usr/local/bin/bench-browser measure
if [ "$timer" = yes ]; then compose cp browser:/tmp/clock-samples.json "$run_dir/clock-samples.json"; fi
compose cp browser:/tmp/page.json "$run_dir/page.json"
compose cp browser:/tmp/security.json "$run_dir/security.json"
if [ "$monitoring" = off ]; then
    compose exec -T router awk '{printf "%.0f\n", $1*1000000}' /proc/uptime > "$run_dir/unobserved-end"
    printf '{"monitoring":"off","unobserved_start_usec":%s,"unobserved_end_usec":%s,"resource_metrics_available":false}\n' "$(cat "$run_dir/unobserved-start")" "$(cat "$run_dir/unobserved-end")" > "$run_dir/monitoring-window.json"
    for role in browser server router; do
        compose exec -T "$role" cat /sys/fs/cgroup/memory.events > "$run_dir/$role-oom-after.txt"
        cmp "$run_dir/$role-oom-before.txt" "$run_dir/$role-oom-after.txt"
        compose exec -d -e ROLE="$role" -e RUN_ID="$run_id" "$role" sh -c 'echo $$ >/tmp/sampler.pid; exec sh /tmp/sample.sh >/tmp/resources.jsonl 2>/tmp/resources-error.txt'
    done
    sleep 2
    compose exec -T router awk '{printf "%.0f\n", $1*1000000}' /proc/uptime > "$run_dir/resource-start"
fi
capture after
compose exec -T server cat /certs/good/cert.pem > "$run_dir/leaf.pem"
context
compose logs --no-color server > "$run_dir/server-log.txt"
sleep 5
compose exec -T server sh -c 'kill -USR1 $(cat /proc/1/task/1/children); timeout 2 sh -c "until test -f /tmp/counters.json; do sleep .05; done"; cat /tmp/counters.json' > "$run_dir/counters.json"
stage=stabilization
deadline=$(($(date +%s) + 30))
stable=0
while [ "$(date +%s)" -lt "$deadline" ]; do
    stable=1
    compose exec -T router sh -c 'for i in 0 1 2 3 4 5 6 7 8 9 10; do
      tc -s -j qdisc show | jq -e "[.[] | select(.kind==\"netem\")] | length==2 and all(.[]; .backlog==0 and .qlen==0)" >/dev/null || exit 1
      [ "$i" = 10 ] || sleep .1
    done' || stable=0
    sleep 2
    for role in browser server router; do
        compose exec -T "$role" sh /tmp/check-sample.sh fresh > "$run_dir/$role-idle.jsonl" || stable=0
        awk -F '[:,]' '{
          for (i=1;i<NF;i++) {
            if ($i=="\"cpu_usage_usec\"") cpu=$(i+1)
            if ($i=="\"interval_usec\"") interval=$(i+1)
          }
          if (interval<=0) exit 1
          pct=int(100*cpu/interval+0.999999)
          if (FILENAME==ARGV[1]) {if(pct>peak)peak=pct} else if (pct>peak) exit 1
        }' "$run_dir/$role-baseline.jsonl" "$run_dir/$role-idle.jsonl" || stable=0
    done
    [ "$(date +%s)" -le "$deadline" ] || stable=0
    test "$stable" != 1 || break
done
test "$stable" = 1
compose exec -T router tc -s -j qdisc show > "$run_dir/qdisc-stable.json"
printf '{"stable":true,"empty_queue_window_ms":1000,"cpu_baseline_comparison":"per_role_ceil_percent","wait_limit_s":30}\n' > "$run_dir/stabilization.json"
compose exec -T router awk '{printf "%.0f\n", $1*1000000}' /proc/uptime > "$run_dir/resource-end"
resource_end=$(cat "$run_dir/resource-end")
for role in browser server router; do
    compose exec -T "$role" sh /tmp/check-sample.sh "$resource_end" >/dev/null
    compose exec -T "$role" cat /tmp/resources.jsonl >> "$run_dir/resources.jsonl"
done
printf '{"start_usec":%s,"end_usec":%s}\n' "$(cat "$run_dir/resource-start")" "$resource_end" > "$run_dir/resource-window.json"
if [ -f "$run_dir/collect-backlog" ]; then
    sleep 1
    compose exec -T router cat /tmp/backlog.jsonl > "$run_dir/backlog.jsonl"
fi
compose down --timeout 2
stage=publication
analyze src/analysis/record.py complete "$series_dir" "$index" "$run_dir"
