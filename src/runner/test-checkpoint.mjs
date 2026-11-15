import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { checkpointMeasurement } from "./dist/checkpoint.js";
import { chromium } from "playwright";

/** Resolve the pending operation with the received value. */
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/** Check that browser crash retains the last complete atomic checkpoint. */
test("browser crash retains the last complete atomic checkpoint", async () => {
  const directory = mkdtempSync(join(tmpdir(), "bench-checkpoint-"));
  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
  /** Complete without performing additional work. */
  let stop = async () => {};
  try {
    const page = await browser.newPage();
    /** Collect clock readings in the page. */
    await page.evaluate(() => {
      /** Collect clock readings in the page. */
      globalThis.measurementSnapshot = () => ({
        captured_page_ms: performance.now(),
        slots: [
          {
            run_id: "crash-fixture",
            phase: 1,
            seq: "0",
            t_plan_ms: 0,
            t_send_ms: 1,
            first_correct_echo_ms: 5,
          },
        ],
        events: [],
      });
    });
    const path = join(directory, "page.partial.json");
    /** Capture the current page measurement snapshot. */
    stop = checkpointMeasurement(path, "crash-fixture", () =>
      page.evaluate(() => globalThis.measurementSnapshot()),
    );
    await wait(2600);
    const saved = readFileSync(path, "utf8");
    const checkpoint = JSON.parse(saved);
    assert.equal(checkpoint.status, "partial");
    assert.equal(checkpoint.run_id, "crash-fixture");
    assert.equal(checkpoint.slots[0].first_correct_echo_ms, 5);
    assert.ok(checkpoint.captured_page_ms > 0);
    /** Resolve the pending operation with the received value. */
    const crashed = new Promise((resolve) => page.once("crash", resolve));
    const session = await page.context().newCDPSession(page);
    /** Complete without performing additional work. */
    void session.send("Page.crash").catch(() => {});
    /** Report the asynchronous operation failure. */
    await Promise.race([
      crashed,
      wait(5000).then(() => {
        throw Error("page did not crash");
      }),
    ]);
    await wait(2200);
    await stop();
    assert.equal(readFileSync(path, "utf8"), saved);
  } finally {
    await stop();
    await browser.close();
    rmSync(directory, { recursive: true, force: true });
  }
});

/** Check that a stalled browser snapshot cannot hang checkpoint shutdown. */
test("a stalled browser snapshot cannot hang checkpoint shutdown", async () => {
  const directory = mkdtempSync(join(tmpdir(), "bench-checkpoint-stall-"));
  try {
    /** Return the callback result for checkpointMeasurement. */
    const stop = checkpointMeasurement(
      join(directory, "page.partial.json"),
      "stall",
      () => new Promise(() => {}),
    );
    await wait(2100);
    /** Report the asynchronous operation failure. */
    await Promise.race([
      stop(),
      wait(2000).then(() => {
        throw Error("shutdown hung");
      }),
    ]);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});
