set -eu
mkdir -p results/archives
cd results/archives
archive=$(mktemp wswt-images.XXXXXXXX)
trap 'rm -f "$archive"' EXIT
docker image save -o "$archive" wswt-bench-server:dev wswt-bench-browser:dev wswt-bench-router:dev wswt-bench-analyzer:dev
hash=$(shasum -a 256 "$archive" | cut -d' ' -f1)
mv "$archive" "images-$hash.tar"
shasum -a 256 "images-$hash.tar" >"images-$hash.tar.sha256"
