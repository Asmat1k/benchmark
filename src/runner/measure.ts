import { chromium } from "playwright";
import { readFileSync, writeFileSync } from "node:fs";
import { X509Certificate } from "node:crypto";
import { checkpointMeasurement } from "./checkpoint.js";

const run = JSON.parse(readFileSync("/tmp/run.json", "utf8"));
const pins = JSON.parse(readFileSync("/trust/pins.json", "utf8"));
const browser = await chromium.launch({ channel: "chromium", chromiumSandbox: true });
try {
  const page = await browser.newPage();
  const response = await page.goto("https://bench.test:8443/");
  /** Read whether the page has a secure context. */
  if (!response?.ok() || !(await page.evaluate(() => window.isSecureContext)))
    throw Error("untrusted page");
  const control = await browser.newBrowserCDPSession();
  const commandLine = await control.send("Browser.getBrowserCommandLine");
  await control.detach();
  if (process.env.BENCH_TIMER === "yes") {
    /** Collect clock readings in the page. */
    const samples = await page.evaluate(() => {
      const timestamps = new Float64Array(100001);
      for (let i = 0; i < timestamps.length; i++) timestamps[i] = performance.now();
      return Array.from(timestamps);
    });
    writeFileSync("/tmp/clock-samples.json", JSON.stringify(samples));
  }
  /** Capture the current page measurement snapshot. */
  const stopCheckpoints =
    process.env.BENCH_CHECKPOINT === "yes"
      ? checkpointMeasurement("/tmp/page.partial.json", run.run_id, () =>
          page.evaluate(
            () =>
              (
                globalThis as unknown as { measurementSnapshot?: () => unknown }
              ).measurementSnapshot?.() ?? null,
          ),
        )
      : async () => {};
  let result;
  try {
    /** Run the page measurement with the supplied parameters. */
    result = await page.evaluate(
      ([spec, pin]) =>
        (globalThis as unknown as { measure: (s: unknown, p: string) => Promise<unknown> }).measure(
          spec,
          pin,
        ),
      [run, pins.good],
    );
  } finally {
    await stopCheckpoints();
  }
  writeFileSync("/tmp/page.json", JSON.stringify(result));
  const ca = new X509Certificate(readFileSync("/trust/ca.crt"));
  writeFileSync(
    "/tmp/security.json",
    JSON.stringify({
      leaf_der_sha256: pins.good,
      ca_sha256: ca.fingerprint256,
      chromium: browser.version(),
      secure_context: true,
      endpoint: response.url(),
      tls: await response.securityDetails(),
      args: commandLine.arguments,
    }),
  );
} finally {
  await browser.close();
}
