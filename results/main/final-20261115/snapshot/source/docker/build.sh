set -eu
test "$(docker info --format '{{.Architecture}}')" = aarch64 || { echo "This lock requires native arm64" >&2; exit 1; }
docker compose --profile analysis build
mkdir -p build/figures build/wheelhouse
roles="wswt-bench-server:dev wswt-bench-browser:dev wswt-bench-router:dev wswt-bench-analyzer:dev"
docker image inspect $roles | docker run -i --rm --network none wswt-bench-analyzer:dev python -c '
import json, sys
records = [{"tag": x["RepoTags"][0], "image_id": x["Id"], "os": x["Os"], "architecture": x["Architecture"]} for x in json.load(sys.stdin)]
if any((x["os"], x["architecture"]) != ("linux", "arm64") for x in records):
    raise SystemExit("locked build requires native linux/arm64")
json.dump(records, sys.stdout, indent=2)
' >build/evidence.json
docker run --rm --network none -v "$PWD/build/wheelhouse:/output" wswt-bench-analyzer:dev sh -ec 'cp /wheelhouse/*.whl /wheelhouse/SHA256SUMS /output/; cd /output; sha256sum -c SHA256SUMS'
docker run --rm --network none -v "$PWD/build/figures:/output" wswt-bench-analyzer:dev python check_environment.py /output >build/python.txt
for role in $roles; do
  echo "$role"
  docker run --rm --network none --entrypoint dpkg-query "$role" -W
done >build/os-packages.txt
