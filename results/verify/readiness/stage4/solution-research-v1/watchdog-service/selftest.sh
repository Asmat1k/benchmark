set -eu
base=results/verify/readiness/stage4/solution-research-v1/watchdog-service
execution=$1
token="watchdog-selftest-$(basename "$execution")-$$"
router="$token-net"
server="$token-server"
client="$token-client"
tracer="$token-trace"
cleanup() {
 docker kill --signal USR1 "$tracer" >/dev/null 2>&1 || true
 docker rm -f "$server" "$client" "$tracer" "$router" >/dev/null 2>&1 || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM
touch "$execution/selftest-mode"
docker run --rm -d --name "$router" --network none --cap-drop ALL --cap-add NET_ADMIN --entrypoint sh wswt-bench-router:dev -ec 'ip link set lo up; tc qdisc replace dev lo root netem delay 10ms rate 10mbit; touch /tmp/net-ready; exec sleep 60' > "$execution/router-container"
for attempt in $(seq 1 20); do
 docker exec "$router" test -f /tmp/net-ready && break
 sleep .05
done
docker exec "$router" test -f /tmp/net-ready
docker exec "$router" tc -s -j qdisc show dev lo > "$execution/qdisc-before.json"
docker run --rm -d --name "$server" --network "container:$router" --cap-drop ALL -v "$PWD/$base/tools:/diagnostic:ro" -v "$execution:/out" wswt-bench-analyzer:dev python -B /diagnostic/server.py udp "$token" /out 20 > "$execution/server-container"
docker run --rm -d --name "$client" --network "container:$router" --cap-drop ALL -v "$PWD/$base/tools:/diagnostic:ro" -v "$execution:/out" wswt-bench-analyzer:dev sleep 60 > "$execution/client-container"
docker exec "$client" python -B /diagnostic/sender.py selftest "$token" 127.0.0.1 selftest /out > "$execution/sender.stdout" 2> "$execution/sender.stderr" &
sender_job=$!
for attempt in $(seq 1 100); do
 if [ -f "$execution/server-ready.json" ] && [ -f "$execution/sender-ready.json" ]; then break; fi
 sleep .05
done
test -f "$execution/server-ready.json"
test -f "$execution/sender-ready.json"
docker run --rm --name "$tracer" --network none --privileged --pid host -v "$PWD/$base/tools:/diagnostic:ro" -v "$execution:/out" wswt-bench-analyzer:dev python -B /diagnostic/trace.py "$token" /out 1 > "$execution/tracer.log" 2>&1 &
trace_job=$!
for attempt in $(seq 1 100); do
 [ ! -f "$execution/trace-ready.json" ] || break
 kill -0 "$trace_job"
 sleep .05
done
test -f "$execution/trace-ready.json"
touch "$execution/server-go" "$execution/sender-go"
wait "$sender_job"
test "$(cat "$execution/sender-done")" = 0
for attempt in $(seq 1 100); do
 [ ! -f "$execution/server-records.json" ] || break
 sleep .05
done
test -f "$execution/server-records.json"
docker kill --signal USR1 "$tracer" > "$execution/tracer-stop.stdout"
wait "$trace_job"
docker exec "$router" tc -s -j qdisc show dev lo > "$execution/qdisc-after.json"
python3 -B "$base/tools/check.py" "$execution" selftest > "$execution/trace-check.stdout"
python3 -B "$base/tools/timer_check.py" "$execution" > "$execution/timer-check.stdout"
