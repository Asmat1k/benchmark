/** Construct a protocol frame with the supplied identity. */
export function frame(nonce: bigint, phase: 0 | 1, seq: bigint) {
  const bytes = new Uint8Array(256);
  const header = new DataView(bytes.buffer);
  header.setUint32(0, 0x42575431);
  bytes[4] = 1;
  bytes[5] = phase;
  header.setBigUint64(8, nonce);
  header.setBigUint64(16, seq);
  for (let i = 24; i < bytes.length; i++) bytes[i] = Number((seq + BigInt(i)) & 255n);
  return bytes;
}

/** Reject a reply that differs from the expected bytes. */
export function equal(actual: Uint8Array, expected: Uint8Array) {
  /** Compare each expected byte with the received frame. */
  if (actual.length !== expected.length || !expected.every((v, i) => v === actual[i]))
    throw new Error("unexpected echo bytes");
}

export class StreamReader {
  private tail: Uint8Array = new Uint8Array();
  /** Retain the stream reader used to assemble complete frames. */
  constructor(private reader: ReadableStreamDefaultReader<Uint8Array>) {}
  /** Read the requested bytes or reject an incomplete reply. */
  async read(size: number) {
    const result = new Uint8Array(size);
    let filled = 0;
    while (filled < size) {
      if (!this.tail.length) {
        const next = await this.reader.read();
        if (next.done) throw new Error(filled ? "truncated frame" : "end of stream");
        this.tail = next.value;
      }
      const count = Math.min(size - filled, this.tail.length);
      result.set(this.tail.subarray(0, count), filled);
      this.tail = this.tail.subarray(count);
      filled += count;
    }
    return result;
  }
}
