import { chromium } from "playwright";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";

declare global {
  interface Window {
    bench: {
      probe(
        mode: string,
        hash: string,
      ): Promise<{ supported?: boolean; exactFrames?: number }>;
      openSocket(port: number): Promise<WebSocket>;
      openTransport(port: number, hash: string): Promise<WebTransport>;
    };
  }
}

const require = createRequire(import.meta.url);
const pins = JSON.parse(readFileSync("/trust/pins.json", "utf8"));
const browser = await chromium.launch({
  channel: "chromium",
  chromiumSandbox: true,
  headless: true,
});
try {
  const version = browser.version();
  assert.equal(version, "140.0.7339.16");
  assert.equal(process.version, "v22.18.0");
  const page = await browser.newPage();
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Network.enable");
  cdp.on("Network.webSocketHandshakeResponseReceived", (e) =>
    console.log(
      JSON.stringify({
        wsStatus: e.response.status,
        statusText: e.response.statusText,
      }),
    ),
  );
  page.on("console", (e) => {
    if (e.type() === "error") console.error(e.text());
  });
  await page.goto("https://bench.test:8443/", { timeout: 6000 });
  assert(await page.evaluate(() => window.isSecureContext && !!window.bench));
  console.log(
    JSON.stringify({
      utc: new Date().toISOString(),
      version,
      node: process.version,
      npm: require("node:child_process")
        .execFileSync("npm", ["-v"], { encoding: "utf8" })
        .trim(),
      typescript: require("typescript/package.json").version,
      typesNode: require("@types/node/package.json").version,
      playwright: require("playwright/package.json").version,
      executable: chromium.executablePath(),
      secureContext: true,
      leaf: pins.good,
      ca: createHash("sha256")
        .update(readFileSync("/trust/ca.crt"))
        .digest("hex"),
    }),
  );
  for (const mode of ["WS", "WT-S", "WT-D"]) {
    const result = await page.evaluate(
      ([mode, hash]) => window.bench.probe(mode, hash),
      [mode, pins.good],
    );
    assert(
      result.exactFrames === 3 ||
        (mode === "WT-D" && result.supported === false),
    );
    console.log(JSON.stringify(result));
  }
  for (const [name, port, reason] of [
    ["wrong-san", 8444, "CERT_COMMON_NAME_INVALID"],
    ["expired", 8445, "CERT_DATE_INVALID"],
    ["unknown-ca", 8446, "CERT_AUTHORITY_INVALID"],
  ] as const) {
    const navigation = await browser.newPage();
    try {
      await assert.rejects(
        navigation.goto(`https://bench.test:${port}/`),
        new RegExp("ERR_" + reason),
      );
    } finally {
      await navigation.close();
    }
    const certError = page.waitForEvent("console", {
      predicate: (m) =>
        m.text().includes(`wss://bench.test:${port}/ws`) &&
        m.text().includes("ERR_" + reason),
      timeout: 3000,
    });
    assert.equal(
      await page.evaluate(async (port) => {
        try {
          (await window.bench.openSocket(port)).close();
          return "connected";
        } catch (e) {
          return (e as Error).message;
        }
      }, port),
      "WebSocket handshake rejected",
    );
    await certError;
    console.log(JSON.stringify({ name, port, https: reason, wss: "rejected" }));
  }
  for (const [name, port, pin] of [
    ["wrong-pin", 8443, "00".repeat(32)],
    ["expired", 8445, pins.expired],
  ] as const) {
    const tlsFailure = page.waitForEvent("console", {
      predicate: (m) =>
        m.text().includes(`https://bench.test:${port}/wt`) &&
        m.text().includes("CERTIFICATE_VERIFY_FAILED"),
      timeout: 3000,
    });
    const outcome = await page.evaluate(
      async ([port, pin]) => {
        try {
          (await window.bench.openTransport(Number(port), String(pin))).close();
          return "connected";
        } catch (e) {
          return (e as Error).name;
        }
      },
      [port, pin],
    );
    await tlsFailure;
    assert.equal(outcome, "WebTransportError");
    console.log(JSON.stringify({ name, port, wt: outcome }));
  }
} finally {
  await browser.close();
}
