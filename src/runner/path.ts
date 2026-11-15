import assert from "node:assert/strict";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { setTimeout as sleep } from "node:timers/promises";
import { chromium } from "playwright";

const browser = await chromium.launch({ channel: "chromium", chromiumSandbox: true });
try {
  const page = await browser.newPage();
  await page.goto("https://bench.test:8443/");
  const { good } = JSON.parse(readFileSync("/trust/pins.json", "utf8"));
  writeFileSync("/tmp/path-ready", "");
  while (!existsSync("/tmp/path-forwarding-disabled")) await sleep(100);
  /** Resolve the pending operation or reject its connection failure. */
  const outcomes = await page.evaluate(async (pin: string) => {
    /** Report whether the connection opens successfully. */
    const check = async (connection: Promise<WebSocket | WebTransport>) =>
      Promise.race([
        connection.then(
          (channel) => {
            channel.close();
            return "connected";
          },
          () => "rejected",
        ),
        new Promise<string>((resolve) => setTimeout(() => resolve("timed_out"), 2500)),
      ]);
    return Promise.all([
      check(window.bench.openSocket(8443)),
      check(window.bench.openTransport(8443, pin)),
    ]);
  }, good);
  console.log(JSON.stringify({ forwarding: 0, ws: outcomes[0], wt: outcomes[1] }));
  for (const outcome of outcomes) assert(["rejected", "timed_out"].includes(outcome));
} finally {
  await browser.close();
}
