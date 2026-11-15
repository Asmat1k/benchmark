import { equal, frame, StreamReader } from "./protocol.js";

type Mode = "WS" | "WT-S" | "WT-D";
const ready = new TextEncoder().encode("READY");
const ack = new TextEncoder().encode("ACK");

export async function openSocket(port: number) {
  const socket = new WebSocket(`wss://bench.test:${port}/ws`);
  socket.binaryType = "arraybuffer";
  await new Promise<void>((resolve, reject) => {
    socket.onopen = () => resolve();
    socket.onerror = () => reject(new Error("WebSocket handshake rejected"));
  });
  return socket;
}

export async function openTransport(
  port: number,
  hash: string,
  datagram = false,
) {
  const value = Uint8Array.from(hash.match(/../g)!, (b) => parseInt(b, 16));
  const session = new WebTransport(
    `https://bench.test:${port}/wt${datagram ? "?mode=datagram" : ""}`,
    {
      serverCertificateHashes: [{ algorithm: "sha-256", value }],
    },
  );
  await session.ready;
  return session;
}

export async function probe(mode: Mode, hash: string) {
  const frames = [0n, 1n, 2n].map((seq) => frame(0xffffffffffffffffn, 1, seq));
  if (mode === "WS") {
    const socket = await openSocket(8443);
    try {
      for (const request of [ready, ...frames]) {
        const reply = new Promise<Uint8Array>((resolve, reject) => {
          socket.onmessage = (e) =>
            e.data instanceof ArrayBuffer
              ? resolve(new Uint8Array(e.data))
              : reject(new Error("nonbinary"));
          socket.onclose = () => reject(new Error("closed"));
        });
        socket.send(request);
        equal(await reply, request === ready ? ack : request);
      }
    } finally {
      socket.close();
    }
    return { mode, exactFrames: frames.length };
  }
  const datagram = mode === "WT-D";
  const session = await openTransport(8443, hash, datagram);
  try {
    const maximum = session.datagrams.maxDatagramSize;
    if (datagram && maximum < 256) return { mode, supported: false, maximum };
    const channel = datagram
      ? session.datagrams
      : await session.createBidirectionalStream();
    const writer = channel.writable.getWriter();
    const reader = channel.readable.getReader();
    const stream = new StreamReader(reader);
    for (const request of [ready, ...frames]) {
      await writer.write(request);
      const expected = request === ready ? ack : request;
      const reply = datagram
        ? (await reader.read()).value
        : await stream.read(expected.length);
      if (!reply) throw new Error("unexpected EOF");
      equal(reply, expected);
    }
    if (!datagram) await writer.close();
    return { mode, supported: true, exactFrames: frames.length, maximum };
  } finally {
    session.close();
  }
}

Object.assign(globalThis, { bench: { probe, openSocket, openTransport } });
