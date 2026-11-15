set -eu
if [ -z "$1" ]; then
  for run in results/verify/path/wswt-smoke.????????; do
    [ -f "$run/project" ] || continue
    project=$(cat "$run/project")
    active=$(docker ps -aq --filter "label=com.docker.compose.project=$project")
    if [ -n "$active" ]; then
      echo "Select the active project with RUN_DIR=$run" >&2
      exit 2
    fi
  done
  exit 0
fi
case "$1" in results/verify/path/wswt-smoke.????????) ;; *) exit 2 ;; esac
name=$(basename "$1")
project="wswt-d2-$(echo "$name" | tr '[:upper:].' '[:lower:]-')"
test "$project" = "$(cat "$1/project")"
docker compose -p "$project" down --timeout 2
temp_dir="${TMPDIR:-/tmp}/$name"
if [ -d "$temp_dir" ]; then
  test ! -L "$temp_dir"
  rm -rf "$temp_dir"
fi
containers=$(docker ps -aq --filter "label=com.docker.compose.project=$project")
networks=$(docker network ls -q --filter "label=com.docker.compose.project=$project")
test -z "$containers$networks"
printf '{"project":"%s","containers":0,"networks":0,"utc":"%s"}\n' "$project" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$1/cleanup.json"
