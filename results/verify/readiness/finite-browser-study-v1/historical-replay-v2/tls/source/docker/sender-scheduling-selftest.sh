set -eu
out="$PWD/results/verify/readiness/sender-scheduling-preflight/selftest.$(date -u +%Y%m%dT%H%M%S)"
mkdir -p "$out"
token="sender-selftest-$$"
name="$token-probe"
trace_name="$token-trace"
cleanup() {
    touch "$out/trace-stop"
    docker rm -f "$name" "$trace_name" >/dev/null 2>&1 || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM
docker run -d --rm --name "$name" --network none --cap-drop ALL -v "$PWD/docker:/diagnostic:ro" wswt-bench-analyzer:dev sleep 90 >/dev/null
docker exec "$name" python -B /diagnostic/sender_diagnostic_resources.py 60 /tmp/resources-ready /tmp/resources-stop > "$out/resources.jsonl" &
sampler=$!
for attempt in $(seq 1 100); do
    docker exec "$name" test -f /tmp/resources-ready && break
    sleep .1
done
docker exec "$name" test -f /tmp/resources-ready
docker exec "$name" python -B /diagnostic/sender_scheduling_probe.py selftest "$token" /tmp/sender-ready /tmp/sender-go > "$out/probe.json" &
sender=$!
for attempt in $(seq 1 100); do
    docker exec "$name" test -f /tmp/sender-ready && break
    sleep .1
done
docker cp "$name:/tmp/sender-ready" "$out/sender-ready.json"
docker run --rm --name "$trace_name" --network none --privileged --pid host -v "$PWD/docker:/diagnostic:ro" -v "$out:/out" wswt-bench-analyzer:dev python -B /diagnostic/sender_scheduling_trace.py "$token" /out > "$out/tracer.log" 2>&1 &
tracer=$!
for attempt in $(seq 1 100); do
    [ ! -f "$out/trace-ready.json" ] || break
    kill -0 "$tracer"
    sleep .1
done
test -f "$out/trace-ready.json"
docker exec "$name" touch /tmp/sender-go
wait "$sender"
touch "$out/trace-stop"
wait "$tracer"
docker exec "$name" touch /tmp/resources-stop
wait "$sampler"
python3 - "$out" <<'PY'
import json
from pathlib import Path
import re
import sys
p = Path(sys.argv[1])
probe = json.loads((p/'probe.json').read_text())
trace = (p/'trace.txt').read_text()
assert len(probe['trace']) == 22
assert len(re.findall(r'sys_sendto\(', trace)) == 1
assert len(re.findall(r'sys_recvfrom\(', trace)) == 1
assert len(re.findall(r'sys_pselect6\(', trace)) == 20
assert len(re.findall(r'sys_pselect6 ->', trace)) == 20
entries = [round(float(t)*1e9) for t in re.findall(r'(\d+\.\d+): sys_pselect6\(', trace)]
exits = [round(float(t)*1e9) for t in re.findall(r'(\d+\.\d+): sys_pselect6 ->', trace)]
selects = [r for r in probe['trace'] if r['kind'] == 'select']
assert all(r['before']['wall_ns']-2000 <= a <= b <= r['after']['wall_ns']+2000 for r,a,b in zip(selects, entries, exits))
assert 'sched_wakeup:' in trace and 'sched_switch:' in trace
first = json.loads((p/'resources.jsonl').read_text().splitlines()[0])
assert first['wall_ns'] < probe['trace'][0]['before']['wall_ns']
assert all(v == 0 for row in json.loads((p/'trace-loss.json').read_text()).values() for v in row.values())
assert 'sender-trace-ready' in trace and 'sender-trace-stop' in trace
print('PASS: 20 non-network pselect waits, paired events, scheduling, resource barrier, zero loss')
PY
echo "$out"
