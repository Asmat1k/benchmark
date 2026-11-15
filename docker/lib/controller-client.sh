# Send a request to the series controller.
controller_request() {
  controller_line=$(($(wc -l <"$BENCH_CONTROLLER_RESPONSE") + 1))
  printf '%s\n' "$1" >&8
  while [ "$(wc -l <"$BENCH_CONTROLLER_RESPONSE")" -lt "$controller_line" ]; do
    kill -0 "$BENCH_CONTROLLER_PID" 2>/dev/null || {
      echo 'Controller stopped' >&2
      return 2
    }
    sleep 1
  done
  controller_result=$(sed -n "${controller_line}p" "$BENCH_CONTROLLER_RESPONSE")
  controller_code=$(printf '%s' "$controller_result" | sed -n 's/.*"code": \([0-9]*\).*/\1/p')
  test "$controller_code" = 0 || {
    printf '%s\n' "$controller_result" >&2
    return "${controller_code:-2}"
  }
  printf '%s\n' "$controller_result" | sed 's/^.*"value": "//; s/"}$//'
}
