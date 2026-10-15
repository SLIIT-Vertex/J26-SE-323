import { describe, expect, it } from "vitest";

import { TelemetryQueue } from "./queue";

describe("TelemetryQueue", () => {
  it("keeps event ids stable when a batch is restored", () => {
    const queue = new TelemetryQueue();
    const first = queue.record("item_presented", { item_id: "shown" });
    queue.record("option_selected", { option_id: "A" });
    const batch = queue.take();
    expect(batch?.first_sequence_no).toBe(1);
    expect(batch?.events[0]?.event_id).toBe(first.event_id);
    expect(batch?.events.map((event) => event.sequence_no)).toEqual([1, 2]);
    queue.restore(batch ?? { first_sequence_no: 1, events: [] });
    const retried = queue.take();
    expect(retried?.events[0]?.event_id).toBe(first.event_id);
    expect(retried?.events[0]?.sequence_no).toBe(1);
  });
});
