# Clean up resources when the command exits.
cleanup() {
  code=$?
  trap - EXIT
  if [ -d "$run_dir" ] && [ ! -f "$run_dir/SHA256SUMS" ]; then
    for name in page.partial.json page.json security.json clock-samples.json; do
      if [ ! -f "$run_dir/$name" ]; then
        compose cp "browser:/tmp/$name" "$run_dir/$name" 2>/dev/null || true
      fi
    done
    compose logs --no-color server >"$run_dir/server-final.log" 2>/dev/null || true
    compose cp server:/tmp/counters.json "$run_dir/counters-partial.json" 2>/dev/null || true
    for role in browser server router; do
      compose exec -T "$role" cat /tmp/resources.jsonl >"$run_dir/$role-final.jsonl" 2>/dev/null || true
      compose exec -T "$role" cat /tmp/resources-error.txt >"$run_dir/$role-sampler-error.txt" 2>/dev/null || true
    done
  fi
  compose down --timeout 2 || code=1
  if [ "$code" != 0 ]; then echo "Measurement failed at $stage" >&2; fi
  if [ -d "$run_dir" ]; then
    mkdir -p "$series_dir/quarantine"
    mv "$run_dir" "$series_dir/quarantine/$project"
    if [ -f "$series_dir/quarantine/$project/run.json" ]; then
      prepared=1
    fi
  fi
  if [ "$code" != 0 ] && [ "$code" != 3 ] && [ "$prepared" = 1 ] && [ "${BENCH_RESILIENT_RUN:-0}" != 1 ]; then
    echo "Incomplete raw or orchestration failure from $project at $stage" >"$series_dir/STOP"
    analyze execution.quarantine "$series_dir" "$index" "$project" || code=1
  fi
  if [ -n "${lock_pid:-}" ]; then
    exec 9>&-
    wait "$lock_pid" || true
  fi
  rm -rf "$work"
  exit "$code"
}
