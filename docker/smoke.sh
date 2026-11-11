set -eu
BENCH_TLS_DIR=$(mktemp -d "${TMPDIR:-/tmp}/wswt-smoke.XXXXXXXX")
export BENCH_TLS_DIR
project="wswt-d2-$(basename "$BENCH_TLS_DIR" | tr '[:upper:].' '[:lower:]-')"
compose() { docker compose -p "$project" "$@"; }
run_dir="results/verify/path/$(basename "$BENCH_TLS_DIR")"
mkdir -p "$run_dir"
echo "$project" > "$run_dir/project"
cleanup() {
  for endpoint in server browser; do
    id=$(compose ps -q "$endpoint")
    if test -n "$id"; then
      docker run --rm --network "container:$id" --entrypoint sh wswt-bench-router:dev -c 'ip neigh; ip route; ip -s link' >"$run_dir/$endpoint-net.txt" || true
    fi
  done
  compose logs --no-color router server >"$run_dir/services.txt" 2>&1 || true
  compose exec -T router cat /tmp/path.trace >"$run_dir/final-trace.txt" 2>/dev/null || true
  sh docker/cleanup.sh "$run_dir"
}
trap cleanup EXIT
trap 'exit 130' INT TERM
docker run --rm --network none -v "$BENCH_TLS_DIR:/out" --entrypoint testcert wswt-bench-server:dev /out
compose up -d --no-build router browser server
. docker/links.sh
setup_links
for role in server browser router; do
  docker inspect --format '{{.Name}} {{.HostConfig.NanoCpus}} {{.HostConfig.Memory}} {{.HostConfig.ShmSize}} {{.HostConfig.CapAdd}} {{json .NetworkSettings.Networks}}' "$(compose ps -q "$role")" >> "$run_dir/limits.txt"
done
compose exec -T server cat /server-build.txt >"$run_dir/build.txt"
docker image inspect --format '{{.Os}}/{{.Architecture}} {{.Id}}' wswt-bench-server:dev wswt-bench-browser:dev >>"$run_dir/build.txt"
compose exec -d server bench -addr :8444 -certs /certs/wrong-san
compose exec -d server bench -addr :8445 -certs /certs/expired
compose exec -d server bench -addr :8446 -certs /certs/unknown-ca
compose exec -T router sh -c 'cat /proc/sys/net/ipv4/ip_forward; ip route; iptables -L -nv' >"$run_dir/router.txt"
compose exec -d router sh -c 'timeout 20 tcpdump -l -n -i any >/tmp/path.trace 2>&1'
compose exec -T router sh /usr/local/bin/network profile r20p0 20261108 20261109 >"$run_dir/seed-probe.txt" 2>&1
compose exec -T browser sh /usr/local/bin/bench-browser >"$run_dir/browser-baseline.txt" 2>&1
compose exec -d browser sh -c 'runuser -u pwuser -- timeout -k 1 45 node /runner/dist/path.js >/tmp/path.log 2>&1; echo $? >/tmp/path.exit'
compose exec -T browser timeout 10 sh -c 'until test -e /tmp/path-ready; do sleep .1; done'
BENCH_FORWARD=0 compose up -d --force-recreate --no-build router
setup_links
compose exec -T router cat /proc/sys/net/ipv4/ip_forward | grep -x 0 >"$run_dir/forwarding-disabled.txt"
compose exec -T browser touch /tmp/path-forwarding-disabled
compose exec -T browser timeout 10 sh -c 'until test -e /tmp/path.exit; do sleep .1; done; cat /tmp/path.log; exit "$(cat /tmp/path.exit)"' >>"$run_dir/forwarding-disabled.txt"
BENCH_FORWARD=1 compose up -d --no-build --force-recreate router
setup_links
compose exec -T router cat /proc/sys/net/ipv4/ip_forward | grep -x 1 >"$run_dir/forwarding-enabled.txt"
compose exec -d router sh -c 'timeout 20 tcpdump -l -n -i any "port 8443 and (tcp or udp)" >/tmp/path.trace 2>&1'
code=0
compose exec -T browser runuser -u pwuser -- timeout -k 1 45 node /runner/dist/main.js >"$run_dir/browser.txt" 2>&1 || code=$?
compose exec -T router ip -s link >"$run_dir/counters.txt"
compose exec -T router iptables -L FORWARD -nvx >>"$run_dir/counters.txt"
compose exec -T router cat /tmp/path.trace >"$run_dir/trace.txt"
compose logs --no-color server >"$run_dir/server.txt"
test "$code" = 0
for iface in to_server to_browser; do
  for proto in Flags UDP; do
    for direction in In Out; do
      grep -E "$iface +$direction .* $proto" "$run_dir/trace.txt" >/dev/null
    done
  done
done
for profile in r20p0 r20p1 r80p0 r80p1; do
  compose exec -T router sh /usr/local/bin/network profile "$profile" 20261108 20261109 >"$run_dir/$profile.txt" 2>&1
done
sh docker/interop-result.sh "$run_dir" 0
(cd "$run_dir" && shasum -a 256 project limits.txt *-route.txt router-links.txt counters.txt trace.txt forwarding-*.txt r[28]*.txt checks.json > SHA256SUMS)
