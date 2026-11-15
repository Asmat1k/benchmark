set -eu
mkdir -p build
release_commit=$(git rev-parse HEAD)
git archive HEAD src docker configs/schemas configs/contracts/protocol.json configs/policies configs/plan.json configs/profiles.json configs/thresholds.json Makefile compose.yaml | docker run --rm -i --network none -e RELEASE_COMMIT="$release_commit" wswt-bench-analyzer:dev python -c 'import hashlib,json,os,sys,tarfile; archive=tarfile.open(fileobj=sys.stdin.buffer,mode="r|*"); files={};
for member in archive:
 if member.isfile(): files[member.name]=hashlib.sha256(archive.extractfile(member).read()).hexdigest()
json.dump(dict(commit=os.environ["RELEASE_COMMIT"],files=files),sys.stdout,sort_keys=True)' >build/release-state.tmp
mv build/release-state.tmp build/release-state.json
