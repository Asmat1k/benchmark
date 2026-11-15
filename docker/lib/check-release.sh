set -eu
expected_commit=$1
actual_commit=$(git rev-parse HEAD)
test "$actual_commit" = "$expected_commit" || {
  echo 'Release HEAD changed before network' >&2
  exit 2
}
source_status=$(git status --porcelain -- Makefile compose.yaml src docker configs/schemas configs/contracts/protocol.json configs/policies configs/plan.json configs/profiles.json configs/thresholds.json)
test -z "$source_status" || {
  echo 'Release sources changed before network' >&2
  exit 2
}
