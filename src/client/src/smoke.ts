import { equal, frame, StreamReader } from "./protocol.js";

type Mode = "WS" | "WT-S" | "WT-D";
const ready = new TextEncoder().encode("READY");
const ack = new TextEncoder().encode("ACK");

/** Open a binary WebSocket connection. */
export async function openSocket(port: number) {
  const socket = new WebSocket(`wss://bench.test:${port}/ws`);
  socket.binaryType = "arraybuffer";
  /** Resolve the pending operation or reject its connection failure. */
  await new Promise<void>((resolve, reject) => {
    /** Resolve the pending operation with the received value. */
    socket.onopen = () => resolve();
    /** Resolve the pending operation or reject its connection failure. */
    socket.onerror = () => reject(new Error("WebSocket handshake rejected"));
  });
  return socket;
}

/** Open a pinned WebTransport connection. */
export async function openTransport(port: number, hash: string, datagram = false) {
  /** Decode the hexadecimal byte. */
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

/** Send probe frames and validate their echoes. */
export async function probe(mode: Mode, hash: string) {
  /** Create the frame for this sequence number. */
  const frames = [0n, 1n, 2n].map((seq) => frame(0xffffffffffffffffn, 1, seq));
  if (mode === "WS") {
    const socket = await openSocket(8443);
    try {
      for (const request of [ready, ...frames]) {
        /** Resolve the pending operation or reject its connection failure. */
        const reply = new Promise<Uint8Array>((resolve, reject) => {
          /** Resolve the pending operation or reject its connection failure. */
          socket.onmessage = (e) =>
            e.data instanceof ArrayBuffer
              ? resolve(new Uint8Array(e.data))
              : reject(new Error("nonbinary"));
          /** Resolve the pending operation or reject its connection failure. */
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
    const channel = datagram ? session.datagrams : await session.createBidirectionalStream();
    const writer = channel.writable.getWriter();
    const reader = channel.readable.getReader();
    const stream = new StreamReader(reader);
    for (const request of [ready, ...frames]) {
      await writer.write(request);
      const expected = request === ready ? ack : request;
      const reply = datagram ? (await reader.read()).value : await stream.read(expected.length);
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
