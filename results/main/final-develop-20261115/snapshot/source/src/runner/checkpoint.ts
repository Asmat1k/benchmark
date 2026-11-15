import { closeSync, fsyncSync, openSync, renameSync, writeFileSync } from "node:fs";

export const checkpointIntervalMs = 2000;

export function writeCheckpoint(path: string, value: unknown) {
  const temporary = `${path}.tmp`;
  const file = openSync(temporary, "w");
  try {
    writeFileSync(file, JSON.stringify(value));
    fsyncSync(file);
  } finally { closeSync(file); }
  renameSync(temporary, path);
}

export function checkpointMeasurement(path: string, runId: string, snapshot: () => Promise<unknown>) {
  let pending = Promise.resolve();
  let stopped = false;
  const capture = async () => {
    let deadline: ReturnType<typeof setTimeout> | undefined;
    try {
      const value = await Promise.race([snapshot(), new Promise<never>((_, reject) => {
        deadline = setTimeout(() => reject(Error("snapshot timeout")), checkpointIntervalMs / 2);
      })]);
      if (value !== null) writeCheckpoint(path, {
        schema_version: 1, status: "partial", run_id: runId,
        checkpoint_interval_ms: checkpointIntervalMs, captured_utc: new Date().toISOString(),
        ...(value as object),
      });
    } catch (error) { process.stderr.write(`Measurement checkpoint failed: ${error}\n`); }
    finally { clearTimeout(deadline); }
  };
  const timer = setInterval(() => {
    if (stopped) return;
    stopped = true;
    pending = capture().finally(() => { stopped = false; });
  }, checkpointIntervalMs);
  return async () => {
    clearInterval(timer);
    await pending;
  };
}
