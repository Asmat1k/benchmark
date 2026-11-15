import assert from "node:assert/strict";
import test from "node:test";
import { frame, equal, StreamReader } from "./dist/protocol.js";

const sample = frame(2n ** 64n - 1n, 1, 2n ** 64n - 1n);
for (const chunks of [[1, 255], [255, 1], Array(256).fill(1), [768]]) {
  /** Resolve the pending operation or reject its connection failure. */
  test("stream chunks " + chunks.join(","), async () => {
    const bytes = Uint8Array.from([...sample, ...sample, ...sample]);
    let offset = 0;
    const stream = new ReadableStream({
      /** Return the callback result for start. */
      start(c) {
        for (const length of chunks) {
          c.enqueue(bytes.slice(offset, offset + length));
          offset += length;
        }
        c.close();
      },
    });
    const reader = new StreamReader(stream.getReader());
    for (let n = 0; n < offset / 256; n++) equal(await reader.read(256), sample);
    await assert.rejects(reader.read(256), /end of stream/);
  });
}
/** Check that partial EOF and corruption. */
test("partial EOF and corruption", async () => {
  const stream = new ReadableStream({
    /** Return the callback result for start. */
    start(c) {
      c.enqueue(sample.slice(0, 255));
      c.close();
    },
  });
  await assert.rejects(new StreamReader(stream.getReader()).read(256), /truncated/);
  for (const i of [4, 5, 8, 16, 24, 255]) {
    const corrupt = sample.slice();
    corrupt[i] ^= 1;
    /** Return the callback result for assert.throws. */
    assert.throws(() => equal(corrupt, sample));
  }
});

import { Measurement } from "./dist/measurement.js";

const run = {
  run_id: "fixture",
  nonce: "18446744073709551615",
  warmup_slots: 0,
  measurement_slots: 1200,
  interval_ms: 50,
  deadline_ms: 100,
  horizon_ms: 5000,
  queue_limit_bytes: 1048576,
  mode: "WS",
};

/** Check that inclusive personal deadlines and first valid complete echo. */
test("inclusive personal deadlines and first valid complete echo", async () => {
  for (const delta of [100, 5000, 5000.1]) {
    let t = 0;
    const clock = {
      /** Return the callback result for now. */ now: () => t,
      /** Return the callback result for wait. */ wait: async (ms) => {
        t += ms;
      },
    };
    const m = new Measurement({ ...run, measurement_slots: 1 }, clock);
    const result = await m.execute({
      /** Return the currently queued byte count. */ queued: () => 0,
      /** Return the current writer capacity when available. */ desired: () => null,
      /** Send bytes and track the pending write. */ send(bytes) {
        const bad = bytes.slice();
        bad[255] ^= 1;
        m.receive(bad);
        m.receive(bytes.subarray(0, 255));
        t = delta;
        m.receive(bytes);
        m.receive(bytes);
      },
    });
    assert.equal(result.slots[0].ontime, delta === 100);
    assert.equal(result.slots[0].completed_by_horizon, delta <= 5000);
    assert.equal(result.slots[0].first_correct_echo_ms, delta);
    /** Return the callback result for result.events.filter. */
    assert.deepEqual(result.events.filter((e) => e.type === "duplicate").length, 1);
  }
});

/** Check that 1200 planned slots survive missed wake, backlog, API errors and disconnect. */
test("1200 planned slots survive missed wake, backlog, API errors and disconnect", async () => {
  let t = 0,
    wake = 0,
    calls = 0;
  const clock = {
    /** Return the callback result for now. */ now: () => t,
    /** Return the callback result for wait. */ wait: async (ms) => {
      t += ms + (++wake === 1 ? 107 : 0);
    },
  };
  const m = new Measurement(run, clock);
  const result = await m.execute({
    /** Return the currently queued byte count. */ queued: () => (t === 200 ? 1048576 : 0),
    /** Return the current writer capacity when available. */ desired: () => 1,
    /** Send bytes and track the pending write. */ send(bytes) {
      ++calls;
      if (calls === 1) throw Error("API");
      if (calls === 2) return Promise.reject(Error("write"));
      m.receive(bytes);
      m.disconnect("injected");
    },
  });
  assert.equal(result.slots.length, 1200);
  /** Return the callback result for result.slots.slice(0, 7).map. */
  assert.deepEqual(
    result.slots.slice(0, 7).map((s) => s.send_state),
    [
      "local_api_error",
      "scheduler_miss",
      "scheduler_miss",
      "sent",
      "local_backpressure_error",
      "sent",
      "not_sent_after_disconnect",
    ],
  );
  /** Return the callback result for result.slots.filter. */
  assert.equal(result.slots.filter((s) => s.t_send_ms !== null).length, 3);
  /** Resolve the pending operation or reject its connection failure. */
  assert.equal(result.events.filter((e) => e.type === "write_rejection").length, 1);
});

import { timerResolution } from "./dist/timer.js";
/** Check that timer diagnostics with injected step, stalled and reversing clocks. */
test("timer diagnostics with injected step, stalled and reversing clocks", () => {
  let tick = 0;
  /** Return the callback result for timerResolution. */
  assert.equal(timerResolution(() => ++tick / 16, 16).passed, true);
  /** Return the callback result for timerResolution. */
  assert.equal(timerResolution(() => 1, 16).step_ms, null);
  /** Return the callback result for timerResolution. */
  assert.equal(timerResolution(() => --tick, 16).monotonic, false);
});

/** Check that synthetic lossless warmup and measurement preserve phases and all IDs. */
test("synthetic lossless warmup and measurement preserve phases and all IDs", async () => {
  let t = 0;
  const m = new Measurement(
    { ...run, warmup_slots: 200 },
    {
      /** Return the callback result for now. */ now: () => t,
      /** Return the callback result for wait. */ wait: async (ms) => {
        t += ms;
      },
    },
  );
  const result = await m.execute({
    /** Return the currently queued byte count. */ queued: () => 0,
    /** Return the current writer capacity when available. */ desired: () => null,
    /** Pass received bytes to the measurement. */ send: (bytes) => m.receive(bytes),
  });
  assert.equal(result.slots.length, 1400);
  /** Return the callback result for result.slots.filter. */
  assert.equal(result.slots.filter((s) => s.phase === 0 && s.completed_by_horizon).length, 200);
  /** Return the callback result for result.slots.filter. */
  assert.equal(result.slots.filter((s) => s.phase === 1 && s.ontime).length, 1200);
  assert.equal(result.slots[200].t_plan_ms, 10000);
  assert.equal(result.slots[200].seq, "0");
  /** Return the callback result for result.slots.map. */
  assert.equal(new Set(result.slots.map((s) => `${s.phase}:${s.seq}`)).size, 1400);
});
