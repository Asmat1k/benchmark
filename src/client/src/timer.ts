/** Measure timer monotonicity, resolution, and call overhead. */
export function timerResolution(now = () => performance.now(), count = 100000) {
  const deltas: number[] = [];
  let previous = now();
  let monotonic = true;
  let minStep = Infinity;
  for (let i = 0; i < count; i++) {
    const current = now();
    const delta = current - previous;
    deltas.push(delta);
    if (delta < 0) monotonic = false;
    if (delta > 0 && delta < minStep) minStep = delta;
    previous = current;
  }
  /** Compare numeric values in ascending order. */
  deltas.sort((a, b) => a - b);
  const p99 = deltas[Math.ceil(count * 0.99) - 1];
  return {
    count,
    monotonic,
    step_ms: Number.isFinite(minStep) ? minStep : null,
    p99_overhead_ms: p99,
    passed: monotonic && minStep <= 0.1 && p99 <= 0.1,
  };
}
