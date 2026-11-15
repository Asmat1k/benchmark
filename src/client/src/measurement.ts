import { equal, frame } from "./protocol.js";

export interface Run {
  run_id: string;
  nonce: string;
  mode: "WS" | "WT-S" | "WT-D";
  warmup_slots: number;
  measurement_slots: number;
  interval_ms: number;
  deadline_ms: number;
  horizon_ms: number;
  queue_limit_bytes: number;
}

export interface Channel {
  queued(): number;
  desired(): number | null;
  send(bytes: Uint8Array<ArrayBuffer>): void | Promise<void>;
}

export const pageClock = {
  /** Read the current page clock. */
  now: () => performance.now(),
  /** Resolve the pending operation with the received value. */
  wait: (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms)),
};

/** Return null for unavailable channel measurements. */
const absent = (): number | null => null;

export class Measurement {
  private readonly frames;
  readonly slots;
  readonly events: object[] = [];
  private disconnected = false;
  private active = true;

  /** Create the frame for this sequence number. */
  constructor(
    readonly run: Run,
    private clock = pageClock,
  ) {
    const nonce = BigInt(run.nonce);
    if (nonce < 0n || nonce > 0xffffffffffffffffn) throw Error("invalid nonce");
    const phases = [run.warmup_slots, run.measurement_slots];
    /** Create the frame for this sequence number. */
    this.frames = phases.map((count, phase) =>
      Array.from({ length: count }, (_, seq) => frame(nonce, phase as 0 | 1, BigInt(seq))),
    );
    const start = clock.now();
    /** Return the callback result for this.frames.flatMap. */
    this.slots = this.frames.flatMap((frames, phase) =>
      frames.map((_, seq) => ({
        schema_version: 1,
        run_id: run.run_id,
        phase,
        nonce: run.nonce,
        seq: String(seq),
        t_plan_ms: start + (seq + phase * run.warmup_slots) * run.interval_ms,
        t_send_ms: absent(),
        send_lag_ms: absent(),
        api_return_ms: absent(),
        write_fulfilled_ms: absent(),
        send_state: "scheduler_miss",
        bytes: 256,
        queue_before_bytes: absent(),
        desired_size: absent(),
        first_correct_echo_ms: absent(),
        echo_bytes: absent(),
        completed_by_horizon: false,
        ontime: false,
        terminal_reason: "scheduler_miss",
      })),
    );
  }

  /** Record a measurement event with its timestamp. */
  event(
    type: string,
    slot: { phase: number; nonce: string; seq: string } | null,
    details: object = {},
    t_ms = this.clock.now(),
  ) {
    if (this.active)
      this.events.push({
        schema_version: 1,
        event_index: this.events.length,
        run_id: this.run.run_id,
        t_ms,
        type,
        id: slot && { phase: slot.phase, nonce: slot.nonce, seq: slot.seq },
        details,
      });
  }

  /** Record the connection closure and stop further sends. */
  disconnect(reason: string) {
    if (!this.disconnected) this.event("disconnect", null, { reason });
    this.disconnected = true;
  }

  /** Process a received frame and record its timing. */
  receive(bytes: Uint8Array) {
    if (bytes.length !== 256) return this.event("invalid_frame", null, { length: bytes.length });
    const head = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const phase = bytes[5],
      seq = head.getBigUint64(16),
      nonce = head.getBigUint64(8).toString();
    if (phase > 1) return this.event("invalid_frame", null, { phase });
    const id = { phase, nonce, seq: seq.toString() };
    const expected = this.frames[phase]?.[Number(seq)];
    if (!expected || nonce !== this.run.nonce) return this.event("unknown_ID", id);
    try {
      equal(bytes, expected);
    } catch {
      return this.event("invalid_frame", id);
    }
    const time = this.clock.now();
    const slot = this.slots[phase * this.run.warmup_slots + Number(seq)];
    if (slot.t_send_ms === null) return this.event("unknown_ID", id);
    if (slot.first_correct_echo_ms !== null) return this.event("duplicate", id);
    slot.first_correct_echo_ms = time;
    slot.echo_bytes = bytes.length;
    slot.completed_by_horizon = time <= slot.t_plan_ms + this.run.horizon_ms;
    slot.ontime = time <= slot.t_plan_ms + this.run.deadline_ms;
    slot.terminal_reason = slot.ontime
      ? "ontime"
      : slot.completed_by_horizon
        ? "late_before_horizon"
        : "late_after_horizon";
    this.event("first_correct_echo", id, {}, time);
    if (!slot.ontime) this.event(slot.terminal_reason, id, {}, time);
  }

  /** Return the callback result for until. */
  private async until(time: number) {
    while (this.clock.now() < time) await this.clock.wait(time - this.clock.now());
  }

  /** Send the scheduled frames and collect measurement results. */
  async execute(channel: Channel) {
    for (const slot of this.slots) {
      await this.until(slot.t_plan_ms);
      if (slot.seq === "0") this.event("phase_transition", slot);
      if (this.clock.now() >= slot.t_plan_ms + this.run.interval_ms) continue;
      slot.queue_before_bytes = channel.queued();
      slot.desired_size = channel.desired();
      if (this.disconnected || slot.queue_before_bytes + 256 > this.run.queue_limit_bytes) {
        slot.send_state = slot.terminal_reason = this.disconnected
          ? "not_sent_after_disconnect"
          : "local_backpressure_error";
        this.event("buffer_sample", slot, { bytes: slot.queue_before_bytes });
        continue;
      }
      const bytes = this.frames[slot.phase][Number(slot.seq)];
      slot.send_state = "sent";
      slot.terminal_reason = "horizon";
      slot.t_send_ms = this.clock.now();
      try {
        const result = channel.send(bytes);
        slot.api_return_ms = this.clock.now();
        /** Return the callback result for result?.then. */
        result?.then(
          () => {
            slot.write_fulfilled_ms = this.clock.now();
          },
          (e) => {
            this.event("write_rejection", slot, { error: String(e) });
            if (slot.first_correct_echo_ms === null) slot.terminal_reason = "write_rejection";
          },
        );
      } catch (e) {
        slot.api_return_ms = this.clock.now();
        slot.send_state = slot.terminal_reason = "local_api_error";
        this.event("api_error", slot, { error: String(e) });
      }
      slot.send_lag_ms = slot.t_send_ms - slot.t_plan_ms;
    }
    await this.until(this.slots.at(-1)!.t_plan_ms + this.run.horizon_ms);
    this.active = false;
    return { slots: this.slots, events: this.events };
  }
}
