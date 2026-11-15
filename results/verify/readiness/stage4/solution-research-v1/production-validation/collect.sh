set -eu
base=results/verify/readiness/stage4/solution-research-v1/production-validation
python3 -B "$base/preflight.py" "$1"
export BENCH_TLS_DIR=/Users/dobrov/Desktop/Code/ITMO/benchmark/build/series-tls-stage2._n__udb0
run_dir=$(mktemp -d results/verify/diagnostic/affinity-validation.XXXXXXXX)
project="wswt-$(basename "$run_dir" | tr '[:upper:].' '[:lower:]-')"
compose() { docker compose -p "$project" "$@"; }
work=$(mktemp -d)
cleanup() {
 code=$?
 trap - EXIT
 for role in browser server; do docker rm -f "$project-probe-$role" >/dev/null 2>&1 || true; done
 compose down --timeout 2 || code=1
 exec 9>&-
 if [ -n "${lock_pid:-}" ]; then wait "$lock_pid" || true; fi
 rm -rf "$work"
 date -u +%FT%TZ > "$run_dir/ended"
 printf '%s\n' "$code" > "$run_dir/exit"
 python3 -B - "$run_dir" <<'PY'
import hashlib,json,sys
from pathlib import Path
run=Path(sys.argv[1]);files=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(run.rglob('*')) if p.is_file() and p.name!='captured.json']
(run/'captured.json').write_text(json.dumps(files,indent=2)+'\n')
PY
 printf 'RUN: %s\n' "$run_dir"
 exit "$code"
}
trap cleanup EXIT
trap 'exit 130' INT TERM
cp "$0" "$run_dir/collector.sh"
cp "$base/plan.md" "$run_dir/plan.md"
cp -R "$base/tools" "$run_dir/tools"
cp results/verify/readiness/stage4/solution-research-v1/production-validation/source-inventory.json "$run_dir/sources-before.json"
mkfifo "$work/lock"
docker run --rm -i --network none -v "$PWD:/bench" -w /bench wswt-bench-analyzer:dev python -B src/analysis/series.py hold < "$work/lock" > "$work/status" &
lock_pid=$!
exec 9> "$work/lock"
for i in 1 2 3 4 5; do [ ! -s "$work/status" ] || break; sleep 1; done
test "$(cat "$work/status")" = locked
date -u +%FT%TZ > "$run_dir/started"
git rev-parse HEAD > "$run_dir/commit"
compose up -d --no-build router server browser
. docker/links.sh
setup_links
. docker/calibration-neighbors.sh
compose ps -q | xargs docker inspect > "$run_dir/inspect.json"
for role in browser server; do
 docker run --rm -d --name "$project-probe-$role" --cap-drop ALL --network "container:$(compose ps -q "$role")" -v "$PWD/$base/tools:/diagnostic:ro" wswt-bench-analyzer:dev python -B /diagnostic/calibration_probe.py serve >/dev/null
 for i in 1 2 3 4 5; do [ "$(docker logs "$project-probe-$role")" != ready ] || break; sleep 1; done
 test "$(docker logs "$project-probe-$role")" = ready
done
uname -a > "$run_dir/host.txt"
docker info --format '{"kernel":"{{.KernelVersion}}","platform":"{{.Architecture}}","engine":"{{.ServerVersion}}","cpus":{{.NCPU}},"mem":{{.MemTotal}}}' > "$run_dir/vm.json"
docker inspect --format '{"id":"{{.Image}}","role":{{json .Name}},"cpu":{{.HostConfig.NanoCpus}},"memory":{{.HostConfig.Memory}},"shm":{{.HostConfig.ShmSize}}}' $(compose ps -q) | awk 'BEGIN{print "["} NR>1{print ","} {print} END{print "]"}' > "$run_dir/limits.json"
compose exec -T server cat /certs/good/cert.pem > "$run_dir/leaf.pem"
context() { docker run --rm --network none -v "$PWD:/bench" -w /bench wswt-bench-analyzer:dev python -B docker/calibration_report.py context "$run_dir" "$1"; }
context before
cmp "$run_dir/context-before.json" results/verify/diagnostic/timer-timer.2ST8NYBU/context.json
seed=20261112
for collection in r80p0-check r80p1-check; do
 seed=$((seed+2))
 dir="$run_dir/$collection";mkdir "$dir"
 option=
 case "$collection" in immediate-*) option=--immediate-mode ;; esac
 printf '%s\n' "$option" > "$dir/capture-option"
 compose exec -T router sh /usr/local/bin/network profile "${collection%-check}" "$seed" "$((seed+1))" > "$dir/profile.txt"
 compose exec -T router tc -s -j qdisc show > "$dir/qdisc-before.json"
 for role in server browser; do
  compose exec -d router sh -c 'role=$1;option=$2;echo $$ > "/tmp/$role.pid";exec tcpdump $option -Q in -n -U -s 96 -i "to_$role" -w "/tmp/$role.pcap" 2>"/tmp/$role.log"' sh "$role" "$option"
  compose exec -T router timeout 5 sh -c 'until grep -q "listening on" "/tmp/$1.log";do sleep .05;done' sh "$role"
 done
 compose exec -T router sh -c 'cat /proc/uptime /sys/fs/cgroup/cpu.stat;for role in server browser;do cat "/proc/$(cat /tmp/$role.pid)/stat";done' > "$dir/cpu-before.txt"
 docker exec "$project-probe-browser" cat /sys/fs/cgroup/cpu.stat > "$dir/sender-cpu-before.txt"
 docker exec "$project-probe-browser" python -B /diagnostic/probe.py 172.28.20.10 "$(basename "$run_dir")/$collection" > "$dir/probe.json"
 docker exec "$project-probe-browser" cat /sys/fs/cgroup/cpu.stat > "$dir/sender-cpu-after.txt"
 compose exec -T router sh -c 'cat /proc/uptime /sys/fs/cgroup/cpu.stat;for role in server browser;do cat "/proc/$(cat /tmp/$role.pid)/stat";done' > "$dir/cpu-after.txt"
 for role in server browser; do
  compose exec -T router sh -c 'kill -INT "$(cat /tmp/$1.pid)";timeout 5 sh -c "while kill -0 $(cat /tmp/$1.pid) 2>/dev/null;do sleep .05;done"' sh "$role"
  compose cp "router:/tmp/$role.pcap" "$dir/$role.pcap"
  compose exec -T router cat "/tmp/$role.log" > "$dir/$role.log"
  grep -x '0 packets dropped by kernel' "$dir/$role.log" >/dev/null
  compose exec -T router rm "/tmp/$role.log"
 done
 compose exec -T router tc -s -j qdisc show > "$dir/qdisc-after.json"
done
context after
cmp "$run_dir/context-before.json" "$run_dir/context-after.json"
python3 -B - "$run_dir" <<'PY'
import hashlib,json,sys
from pathlib import Path
run=Path(sys.argv[1]);old=json.loads((run/'sources-before.json').read_text());current={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in old}
(run/'sources-after.json').write_text(json.dumps(current,indent=2)+'\n');assert current==old
PY
