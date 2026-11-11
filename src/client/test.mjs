import assert from "node:assert/strict";
import test from "node:test";
import { frame, equal, StreamReader } from "./dist/protocol.js";

const sample = frame(2n ** 64n - 1n, 1, 2n ** 64n - 1n);
for (const chunks of [[1, 255], [255, 1], Array(256).fill(1), [768]]) {
  test("stream chunks " + chunks.join(","), async () => {
    const bytes = Uint8Array.from([...sample, ...sample, ...sample]);
    let offset = 0;
    const stream = new ReadableStream({
      start(c) {
        for (const length of chunks) {
          c.enqueue(bytes.slice(offset, offset + length));
          offset += length;
        }
        c.close();
      },
    });
    const reader = new StreamReader(stream.getReader());
    for (let n = 0; n < offset / 256; n++)
      equal(await reader.read(256), sample);
    await assert.rejects(reader.read(256), /end of stream/);
  });
}
test("partial EOF and corruption", async () => {
  const stream = new ReadableStream({
    start(c) {
      c.enqueue(sample.slice(0, 255));
      c.close();
    },
  });
  await assert.rejects(
    new StreamReader(stream.getReader()).read(256),
    /truncated/,
  );
  for (const i of [4, 5, 8, 16, 24, 255]) {
    const corrupt = sample.slice();
    corrupt[i] ^= 1;
    assert.throws(() => equal(corrupt, sample));
  }
});
