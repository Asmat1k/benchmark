set -eu
out=$1
base="$PWD/results/verify/readiness/stage4/transition-trace-v1"
token="transition-selftest-$$"
cleanup() {
 touch "$out/trace-stop"
 docker rm -f "$token-server" "$token-trace" >/dev/null 2>&1 || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM
docker run -d --rm --name "$token-server" --network none --cap-drop ALL -v "$base/tools:/diagnostic:ro" -v "$out:/out" wswt-bench-analyzer:dev python -B /diagnostic/server.py unix "$token" /out 20 > "$out/server-container"
for i in $(seq 1 100); do [ ! -f "$out/server-ready.json" ] || break; sleep .05; done
test -f "$out/server-ready.json"
docker inspect "$token-server" > "$out/server-inspect.json"
docker run --rm --name "$token-trace" --network none --privileged --pid host -v "$base/tools:/diagnostic:ro" -v "$out:/out" wswt-bench-analyzer:dev python -B /diagnostic/trace.py "$token" /out > "$out/tracer.log" 2>&1 &
tracer=$!
for i in $(seq 1 200); do [ ! -f "$out/trace-ready.json" ] || break; kill -0 "$tracer"; sleep .05; done
test -f "$out/trace-ready.json"
touch "$out/server-go"
docker exec "$token-server" python -B -c 'import socket,time,struct; s=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM);s.bind("/tmp/client");s.settimeout(2)
for i in range(20):
 d=struct.pack("!I8s",i,b"selftest")+bytes(244);s.sendto(d,"/tmp/echo-selftest");assert s.recv(1024)==d;time.sleep(.01)'
for i in $(seq 1 100); do [ ! -f "$out/server-records.json" ] || break; sleep .05; done
test -f "$out/server-records.json"
touch "$out/trace-stop"
wait "$tracer"
python3 -B "$base/tools/check.py" "$out" selftest
