import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TutorDemo } from "./TutorDemo";
import type { ResearchTutorApi } from "./api";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  host.remove();
});

function client(): ResearchTutorApi {
  return {
    authorize: vi.fn(async () => {
      throw new Error("Researcher access denied.");
    }),
    start: vi.fn(),
    ask: vi.fn(),
    attempt: vi.fn(),
    end: vi.fn(),
  };
}

async function render(embedded: boolean) {
  await act(async () => root.render(<TutorDemo api={client()} embedded={embedded} />));
  await act(async () => new Promise((resolve) => setTimeout(resolve, 0)));
}

describe("Adaptive Tutor entry point", () => {
  it("embeds only the research chat in the shared shell without a nested shell or back link", async () => {
    await render(true);

    expect(host.querySelector(".tutor-workspace .mindy-chat")).not.toBeNull();
    expect(host.querySelector(".mobile-shell")).toBeNull();
    expect(host.querySelector('a[title="Back to MindBridge"]')).toBeNull();
    expect(host.textContent).not.toContain("Synthetic demo");
  });

  it("renders standalone as a full-height shell with a back link", async () => {
    await render(false);

    expect(host.querySelector("main.mobile-shell.tutor-shell .mindy-chat")).not.toBeNull();
    expect(host.querySelector('a[title="Back to MindBridge"]')?.getAttribute("href")).toBe("#/");
  });
});
