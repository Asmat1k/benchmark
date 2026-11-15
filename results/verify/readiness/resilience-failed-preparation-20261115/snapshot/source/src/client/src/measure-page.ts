import { Measurement, type Run } from "./measurement.js";
import { openSocket, openTransport } from "./smoke.js";
import { StreamReader, equal } from "./protocol.js";

function measurement(run: Run) {
  const current = new Measurement(run);
  Object.assign(globalThis, {measurementSnapshot: () => ({
    captured_page_ms: performance.now(), slots: current.slots, events: current.events,
  })});
  return current;
}

async function measure(run: Run, pin: string) {
  const ready = new TextEncoder().encode("READY"), ack = new TextEncoder().encode("ACK");
  if (run.mode === "WS") {
    const socket = await openSocket(8443);
    try {
      const reply = new Promise<ArrayBuffer>((resolve, reject) => {
        socket.onmessage = event => resolve(event.data);
        socket.onclose = () => reject(Error("closed before ACK"));
      });
      socket.send(ready);
      equal(new Uint8Array(await reply), ack);
      const m = measurement(run);
      socket.onmessage = e => e.data instanceof ArrayBuffer ? m.receive(new Uint8Array(e.data)) : m.event("invalid_frame",null,{type:typeof e.data});
      socket.onclose = e => m.disconnect(String(e.code));
      return await m.execute({queued:() => socket.bufferedAmount, desired:() => null, send:b => socket.send(b)});
    } finally { socket.close(); }
  }
  const datagram = run.mode === "WT-D";
  const session = await openTransport(8443, pin, datagram);
  try {
    if (datagram && session.datagrams.maxDatagramSize < 256) throw Error("unsupported datagram size");
    const channel = datagram ? session.datagrams : await session.createBidirectionalStream();
    const writer = channel.writable.getWriter(), reader = channel.readable.getReader();
    const stream = new StreamReader(reader);
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
    session.closed.then(() => m.disconnect("closed"), e => m.disconnect(String(e)));
    const receive = async () => {
      try { while (!finished) m.receive(await read(256)); }
      catch (e) {
        if (!finished) {
          if (String(e).includes("truncated")) m.event("framing_error", null);
          m.disconnect(String(e));
        }
      }
    };
    void receive();
    try {
      return await m.execute({queued:() => pending, desired:() => writer.desiredSize,
        send(bytes) {
          const write = writer.write(bytes);
          pending += bytes.length;
          return write.finally(() => { pending -= bytes.length; });
        }});
    } finally { finished = true; }
  } finally { session.close(); }
}
Object.assign(globalThis, {measure});
import { timerResolution } from "./timer.js";
Object.assign(globalThis, {timerResolution});
