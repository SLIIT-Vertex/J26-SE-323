import type { EventBatchRequest, TelemetryEvent } from "../api/generated";

export class TelemetryQueue {
  private nextSequence = 1;
  private pending: TelemetryEvent[] = [];

  record(
    eventType: TelemetryEvent["event_type"],
    payload: TelemetryEvent["payload"] = {},
  ): TelemetryEvent {
    const event: TelemetryEvent = {
      event_id: crypto.randomUUID(),
      sequence_no: this.nextSequence,
      event_type: eventType,
      event_version: 1,
      client_occurred_at: new Date().toISOString(),
      payload,
    };
    this.nextSequence += 1;
    this.pending.push(event);
    return event;
  }

  take(): EventBatchRequest | null {
    const first = this.pending[0];
    if (!first) return null;
    const batch = { first_sequence_no: first.sequence_no, events: [...this.pending] };
    this.pending = [];
    return batch;
  }

  restore(batch: EventBatchRequest): void {
    this.pending = [...batch.events, ...this.pending];
  }
}
