set -eu
mkdir -p results/verify/measurement
directory=$(mktemp -d results/verify/measurement/smoke.XXXXXXXX)
tls=$(mktemp -d "${TMPDIR:-/tmp}/wswt-d3-tls.XXXXXXXX")
trap 'rm -rf "$tls"' EXIT
trap 'exit 130' INT TERM
docker run --rm --network none -v "$PWD:/bench" -w /bench wswt-bench-analyzer:dev python -m execution.schedule smoke "$directory" --blocks 1 --sessions 1 --baseline
docker run --rm --network none -v "$tls:/out" --entrypoint testcert wswt-bench-server:dev /out
for index in 0 1; do SERIES_TLS_DIR="$tls" sh docker/commands/measure.sh "$directory" "$index"; done
docker run --rm --network none -v "$PWD:/bench" -w /bench wswt-bench-analyzer:dev python -B -m measurement.smoke "$directory"
echo "$directory"
