set -eu
run_dir=$1
code=$2
status=passed
reason=null
if [ "$code" -ne 0 ]; then
  status=failed
  reason='"browser scenario failed; inspect traces"'
fi
digest() { shasum -a 256 "$1" | cut -d' ' -f1; }
cat >"$run_dir/checks.json" <<JSON
{
  "schema_version": 1,
  "checks": [{
    "id": "development-interop-smoke",
    "mandatory": true,
    "expected": 0,
    "actual": $code,
    "units": "runner exit code",
    "tolerance": 0,
    "status": "$status",
    "reason": $reason,
    "utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "evidence": [
      {"path": "browser.txt", "sha256": "$(digest "$run_dir/browser.txt")"},
      {"path": "server.txt", "sha256": "$(digest "$run_dir/server.txt")"},
      {"path": "build.txt", "sha256": "$(digest "$run_dir/build.txt")"}
    ]
  }]
}
JSON
