import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it } from "vitest";

import type { SupportView } from "../api/generated";
import { SupportLayer } from "./SupportLayer";

const support: SupportView = {
  scaffold_type: "step_by_step_guidance",
  title: "A short hint",
  steps: ["Look at the groups.", "Count one group."],
  maximum_duration_ms: 60_000,
  maximum_number_of_steps: 2,
};

describe("SupportLayer", () => {
  it("unmounts completely when support is withdrawn", async () => {
    const container = document.createElement("div");
    document.body.append(container);
    const root = createRoot(container);
    await act(async () => {
      root.render(<SupportLayer support={support} reducedMotion />);
    });
    expect(container.querySelector("[data-support-layer]")).not.toBeNull();
    await act(async () => {
      root.render(<SupportLayer support={null} reducedMotion />);
    });
    expect(container.querySelector("[data-support-layer]")).toBeNull();
    expect(container.textContent).toBe("");
    await act(async () => root.unmount());
  });
});
