set -eu
BENCH_TLS_DIR=$(mktemp -d "${TMPDIR:-/tmp}/wswt-smoke.XXXXXXXX")
export BENCH_TLS_DIR
project="wswt-d1-$(basename "$BENCH_TLS_DIR" | tr '[:upper:].' '[:lower:]-')"
compose() { docker compose -p "$project" "$@"; }
cleanup() {
  compose down --timeout 2
  rm -rf "$BENCH_TLS_DIR"
}
trap cleanup EXIT
trap 'exit 130' INT TERM
run_dir="results/verify/interop/$(basename "$BENCH_TLS_DIR")"
mkdir -p "$run_dir"
docker run --rm --network none -v "$BENCH_TLS_DIR:/out" --entrypoint testcert wswt-bench-server:dev /out
compose up -d --no-build server
compose exec -T server cat /server-build.txt >"$run_dir/build.txt"
docker image inspect --format '{{.Os}}/{{.Architecture}} {{.Id}}' wswt-bench-server:dev wswt-bench-browser:dev >>"$run_dir/build.txt"
compose exec -d server bench -addr :8444 -certs /certs/wrong-san
compose exec -d server bench -addr :8445 -certs /certs/expired
compose exec -d server bench -addr :8446 -certs /certs/unknown-ca
code=0
compose run --rm --no-deps browser >"$run_dir/browser.txt" 2>&1 || code=$?
compose logs --no-color server >"$run_dir/server.txt"
sh docker/interop-result.sh "$run_dir" "$code"
cat "$run_dir/browser.txt" "$run_dir/server.txt"
exit "$code"
