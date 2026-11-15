import { Measurement, type Run } from "./measurement.js";
import { openSocket, openTransport } from "./smoke.js";
import { StreamReader, equal } from "./protocol.js";

/** Create the measurement and expose its current snapshot. */
function measurement(run: Run) {
  const current = new Measurement(run);
  Object.assign(globalThis, {
    /** Return the current measurement records and page timestamp. */ measurementSnapshot: () => ({
      captured_page_ms: performance.now(),
      slots: current.slots,
      events: current.events,
    }),
  });
  return current;
}

/** Run the measurement over the selected transport. */
async function measure(run: Run, pin: string) {
  const ready = new TextEncoder().encode("READY"),
    ack = new TextEncoder().encode("ACK");
  if (run.mode === "WS") {
    const socket = await openSocket(8443);
    try {
      /** Resolve the pending operation or reject its connection failure. */
      const reply = new Promise<ArrayBuffer>((resolve, reject) => {
        /** Resolve the pending operation with the received value. */
        socket.onmessage = (event) => resolve(event.data);
        /** Resolve the pending operation or reject its connection failure. */
        socket.onclose = () => reject(Error("closed before ACK"));
      });
      socket.send(ready);
      equal(new Uint8Array(await reply), ack);
      const m = measurement(run);
      /** Pass received bytes to the measurement. */
      socket.onmessage = (e) =>
        e.data instanceof ArrayBuffer
          ? m.receive(new Uint8Array(e.data))
          : m.event("invalid_frame", null, { type: typeof e.data });
      /** Record the connection termination. */
      socket.onclose = (e) => m.disconnect(String(e.code));
      return await m.execute({
        /** Return the currently queued byte count. */ queued: () => socket.bufferedAmount,
        /** Return the current writer capacity when available. */ desired: () => null,
        /** Send the supplied bytes over the connection. */ send: (b) => socket.send(b),
      });
    } finally {
      socket.close();
    }
  }
  const datagram = run.mode === "WT-D";
  const session = await openTransport(8443, pin, datagram);
  try {
    if (datagram && session.datagrams.maxDatagramSize < 256)
      throw Error("unsupported datagram size");
    const channel = datagram ? session.datagrams : await session.createBidirectionalStream();
    const writer = channel.writable.getWriter(),
      reader = channel.readable.getReader();
    const stream = new StreamReader(reader);
    /** Read the requested bytes or reject an incomplete reply. */
    async function read(size: number) {
      if (!datagram) return stream.read(size);
      const result = await reader.read();
      if (result.done) throw Error("end of datagrams");
      return result.value;
    }
    await writer.write(ready);
    equal(await read(ack.length), ack);
    const m = measurement(run);
    let pending = 0;
    let finished = false;
    /** Record the connection termination. */
    session.closed.then(
      () => m.disconnect("closed"),
      (e) => m.disconnect(String(e)),
    );
    /** Process a received frame and record its timing. */
    const receive = async () => {
      try {
        while (!finished) m.receive(await read(256));
      } catch (e) {
        if (!finished) {
          if (String(e).includes("truncated")) m.event("framing_error", null);
          m.disconnect(String(e));
        }
      }
    };
    void receive();
    try {
      return await m.execute({
        /** Return the currently queued byte count. */ queued: () => pending,
        /** Return the current writer capacity when available. */ desired: () => writer.desiredSize,
        /** Send bytes and track the pending write. */
        send(bytes) {
          const write = writer.write(bytes);
          pending += bytes.length;
          /** Remove the completed write from the pending byte count. */
          return write.finally(() => {
            pending -= bytes.length;
          });
        },
      });
    } finally {
      finished = true;
    }
  } finally {
    session.close();
  }
}
Object.assign(globalThis, { measure });
import { timerResolution } from "./timer.js";
Object.assign(globalThis, { timerResolution });
