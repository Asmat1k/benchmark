set -eu
gate=$1
: "${SERIES_TLS_DIR:?persistent series TLS directory required}"
case "$gate" in timer) frequencies=timer ;; generator)
  frequencies="20 100"
  test -f "$2"
  ;;
*) exit 2 ;; esac
mkdir -p results/verify/diagnostic
# Run the analyzer container.
analyze() {
  docker run --rm --network none -v "$PWD:/bench" -v "$PWD:$PWD" -w /bench wswt-bench-analyzer:dev python -B "$@"
}
if [ "$gate" = generator ]; then
  : "${BENCH_GENERATOR_ADMISSION:?source-bound diagnostic generator admission required}"
  analyze src/analysis/admission/browser_admission.py check "$BENCH_GENERATOR_ADMISSION" "$2"
fi
dirs=""
for frequency in $frequencies; do
  directory=$(mktemp -d "results/verify/diagnostic/$gate-$frequency.XXXXXXXX")
  echo "$directory"
  if [ "$gate" = timer ]; then
    analyze src/analysis/execution/schedule.py smoke "$directory" --blocks 1 --sessions 1 --baseline --timer
  else
    analyze src/analysis/execution/schedule.py diagnostic "$directory" --blocks 1 --sessions 1 --baseline --datagrams --generator-hz "$frequency"
  fi
  indexes="0 1"
  if [ "$gate" = generator ]; then indexes="0 1 2"; fi
  for index in $indexes; do sh docker/commands/measure.sh "$directory" "$index"; done
  dirs="$dirs $directory"
done
case "$gate" in timer) environment="$directory/context.json" ;; generator) environment=$2 ;; esac
output="results/verify/diagnostic/$(basename "$directory")-report"
analyze src/analysis/measurement/diagnostic_input.py "$gate" "$environment" "$output" $dirs
echo "$output/report.json"
analyze src/analysis/execution/experiments.py "$gate" --kind real --input "$output/input.json" --environment "$environment" --output "$output/report.json"
