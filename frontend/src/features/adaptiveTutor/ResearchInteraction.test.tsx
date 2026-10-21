import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ResearchInteraction } from "./ResearchInteraction";
import type {
  ResearchInteraction as ResearchResult,
  ResearchSession,
  ResearchTutorApi,
} from "./api";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const NOTICE = "EXPERIMENTAL AI RESPONSE — NOT VERIFIED / NOT FOR LEARNERS";
const session: ResearchSession = {
  session_id: "11111111-1111-4111-8111-111111111111",
  session_token: "research-session-token",
  learner_id: "22222222-2222-4222-8222-222222222222",
  expires_at: "2026-10-19T12:00:00Z",
  researcher_authorized: true,
};
const blocked: ResearchResult = {
  session_id: session.session_id,
  interaction_id: "33333333-3333-4333-8333-333333333333",
  interaction_sequence: 1,
  status: "CONTEXT_NOT_READY",
  safe_message: "Assessment evidence is not ready.",
  delivery_authorized: false,
  confirmed_skill_id: "MAT-FRC",
  skill_mapping_status: "MATCHED",
  assistance_level: "L0",
  controller_reason_codes: ["PRE_INTERACTION"],
  context_issue_codes: [],
  context_provenance: [
    { input: "SKILL_MAPPING", source_id: "mapper", origin: "REAL", status: "MATCHED" },
    { input: "MASTERY", source_id: "pp1-default", origin: "SYNTHETIC", status: "AVAILABLE" },
  ],
  curriculum_status: "NO_APPROVED_SOURCE",
  verification_reason_codes: [],
  verification_evidence_provenance: [],
  draft_attempt_count: 0,
  regeneration_reason_codes: [],
  execution_origin: "MIXED",
  assessment_mode: "RESEARCHER_REVIEWED_NOT_APPROVED_FOR_LEARNERS",
};
const experimental: ResearchResult = {
  ...blocked,
  status: "DELIVERY_NOT_AUTHORIZED",
  safe_message: "Controller decision available for experimental generation.",
  experimental_response_text: "Try drawing the same whole in equal parts.",
  experimental_generation_status: "GENERATED",
  experimental_provenance: "UNREVIEWED_EXPERIMENTAL",
  experimental_provider_name: "google-gemini",
  experimental_notice: NOTICE,
};

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
  vi.restoreAllMocks();
});

function api(overrides: Partial<ResearchTutorApi> = {}): ResearchTutorApi {
  return {
    authorize: vi.fn(async () => ({
      researcher_authorized: true as const,
      child_delivery_enabled: false as const,
    })),
    start: vi.fn(async () => session),
    ask: vi.fn(async () => blocked),
    attempt: vi.fn(async () => ({ ...blocked, interaction_sequence: 2, assistance_level: "L4" })),
    end: vi.fn(async () => undefined),
    ...overrides,
  };
}

async function flush() {
  await act(async () => new Promise((resolve) => setTimeout(resolve, 0)));
}

async function render(client: ResearchTutorApi) {
  await act(async () => root.render(<ResearchInteraction api={client} />));
  await flush();
  await flush();
}

function change(element: HTMLInputElement | HTMLTextAreaElement, value: string) {
  const prototype = element instanceof HTMLTextAreaElement
    ? HTMLTextAreaElement.prototype
    : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(prototype, "value")?.set?.call(element, value);
  element.dispatchEvent(new Event("input", { bubbles: true }));
}

async function askQuestion(text: string) {
  const input = host.querySelector<HTMLTextAreaElement>("#mindy-question");
  if (!input) throw new Error("composer missing");
  change(input, text);
  await act(async () =>
    input.closest("form")?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })),
  );
  await flush();
}

const log = () => host.querySelector('[role="log"]');
const researchDetails = () => [...host.querySelectorAll<HTMLDetailsElement>("details.research-details")];
const lastDetails = () => researchDetails().at(-1);
const button = (label: string) =>
  [...host.querySelectorAll("button")].find((item) => item.textContent?.includes(label));

describe("Mindy research chat", () => {
  it("authorizes, starts a session for the configured learner and enables the composer", async () => {
    const client = api();
    await render(client);

    expect(client.authorize).toHaveBeenCalledOnce();
    expect(client.start).toHaveBeenCalledWith(import.meta.env.VITE_MOBILE_LEARNING_LEARNER_ID ?? "");
    expect(host.querySelector(".mindy-topbar")?.textContent).toContain("Maths helper");
    expect(host.querySelector<HTMLTextAreaElement>("#mindy-question")?.disabled).toBe(false);
    expect(host.textContent).not.toContain("Learner UUID");
  });

  it("keeps the composer disabled and never starts a session when authorization is denied", async () => {
    const client = api({ authorize: vi.fn(async () => { throw new Error("Researcher access denied."); }) });
    await render(client);

    expect(host.querySelector('[role="alert"]')?.textContent).toBe("Researcher access denied.");
    expect(host.querySelector<HTMLTextAreaElement>("#mindy-question")?.disabled).toBe(true);
    expect(host.querySelector<HTMLButtonElement>('button[type="submit"]')?.disabled).toBe(true);
    expect(client.start).not.toHaveBeenCalled();
  });

  it("keeps a multi-turn history of real API results in order", async () => {
    const ask = vi
      .fn()
      .mockResolvedValueOnce(blocked)
      .mockResolvedValueOnce({ ...blocked, interaction_sequence: 2, assistance_level: "L1" });
    const client = api({ ask });
    await render(client);

    await askQuestion("Why is 1/2 equal to 2/4?");
    await askQuestion("Can you give me a hint?");

    expect(ask).toHaveBeenNthCalledWith(1, session, "Why is 1/2 equal to 2/4?", "en");
    expect(ask).toHaveBeenNthCalledWith(2, session, "Can you give me a hint?", "en");
    const asked = [...(log()?.querySelectorAll(".student-message") ?? [])].map((item) => item.textContent);
    expect(asked).toEqual(["Why is 1/2 equal to 2/4?", "Can you give me a hint?"]);
    expect(log()?.querySelectorAll(".mindy-held")).toHaveLength(2);
    expect(researchDetails()).toHaveLength(2);
    expect(lastDetails()?.textContent).toContain("L1 — Metacognitive prompt");
  });

  it("shows a loading state while Mindy is working", async () => {
    let finish: ((value: ResearchResult) => void) | undefined;
    const client = api({ ask: vi.fn(() => new Promise<ResearchResult>((resolve) => { finish = resolve; })) });
    await render(client);

    await askQuestion("Explain equivalent fractions.");
    expect(log()?.textContent).toContain("Mindy is thinking");
    expect(host.querySelector<HTMLButtonElement>('button[aria-label="Sending"]')?.disabled).toBe(true);

    await act(async () => finish?.(blocked));
    expect(log()?.textContent).not.toContain("Mindy is thinking");
  });

  it("presents only authorized, verified text as Mindy's answer", async () => {
    await render(api({
      ask: vi.fn(async () => ({
        ...blocked,
        status: "APPROVED_RESPONSE",
        delivery_authorized: true,
        response_text: "Think about cutting both pizzas into the same number of slices.",
      })),
    }));

    await askQuestion("Why is 1/2 equal to 2/4?");

    const answer = log()?.querySelector('[aria-label="Mindy\'s checked answer"]');
    expect(answer?.textContent).toContain("Think about cutting both pizzas");
    expect(answer?.textContent).toContain("Checked answer");
  });

  it("never shows response text as an answer when delivery is not authorized", async () => {
    await render(api({
      ask: vi.fn(async () => ({ ...blocked, response_text: "Must not be shown to learners." })),
    }));

    await askQuestion("Why is 1/2 equal to 2/4?");

    expect(log()?.querySelector('[aria-label="Mindy\'s checked answer"]')).toBeNull();
    expect(log()?.textContent).toContain("hasn't been checked for learners");
    expect(host.textContent).not.toContain("Must not be shown to learners.");
  });

  it("shows an unverified experimental draft as an amber bubble tagged Not verified", async () => {
    await render(api({ ask: vi.fn(async () => experimental) }));

    await askQuestion("Explain equivalent fractions.");

    const bubble = log()?.querySelector('[aria-label="Mindy\'s unverified draft"]');
    expect(bubble?.classList.contains("mindy-answer--unverified")).toBe(true);
    expect(bubble?.textContent).toContain("Try drawing the same whole in equal parts.");
    const tag = bubble?.querySelector(".status-chip--unverified");
    expect(tag?.textContent?.trim()).toBe("Not verified");
    expect(tag?.getAttribute("title")).toBe(NOTICE);
    expect(log()?.querySelector('[aria-label="Mindy\'s checked answer"]')).toBeNull();
    expect(log()?.querySelector(".mindy-held")).toBeNull();
    const provenance = lastDetails()?.querySelector(".draft-source");
    expect(provenance?.textContent).toContain("UNREVIEWED_EXPERIMENTAL");
    expect(provenance?.textContent).not.toContain("Try drawing");
  });

  it("prefers the verified answer over an experimental draft when delivery is authorized", async () => {
    await render(api({
      ask: vi.fn(async () => ({
        ...experimental,
        status: "APPROVED_RESPONSE",
        delivery_authorized: true,
        response_text: "Verified hint.",
      })),
    }));

    await askQuestion("Explain equivalent fractions.");

    expect(log()?.querySelector('[aria-label="Mindy\'s checked answer"]')?.textContent).toContain("Verified hint.");
    expect(log()?.querySelector(".mindy-answer--unverified")).toBeNull();
  });

  it("keeps researcher details collapsed behind a chevron toggle in each reply", async () => {
    await render(api({ ask: vi.fn(async () => experimental) }));
    await askQuestion("Explain equivalent fractions.");

    const details = lastDetails();
    expect(details?.open).toBe(false);
    expect(details?.querySelector("summary")?.textContent).toContain("Researcher");
    expect(details?.querySelector("summary")?.textContent).toContain("L0 · Not delivered · Draft ready");
    expect(details?.querySelector(".research-summary-flag")?.textContent).toBe("Synthetic data");
    expect(details?.querySelector(".research-chevron")).not.toBeNull();

    await act(async () => details?.querySelector("summary")?.click());
    expect(details?.open).toBe(true);
    await act(async () => details?.querySelector("summary")?.click());
    expect(details?.open).toBe(false);
  });

  it("reports experimental generation failures with the sanitized reason only", async () => {
    await render(api({
      ask: vi.fn(async () => ({
        ...blocked,
        status: "DELIVERY_NOT_AUTHORIZED",
        experimental_generation_status: "PROVIDER_ERROR",
        experimental_provenance: "UNREVIEWED_EXPERIMENTAL",
        experimental_provider_name: "google-gemini",
        experimental_provider_reason_code: "MODEL_NOT_FOUND",
        experimental_notice: NOTICE,
      })),
    }));

    await askQuestion("Explain equivalent fractions.");

    const draftTile = [...(lastDetails()?.querySelectorAll(".glance-tile") ?? [])].find((tile) =>
      tile.textContent?.startsWith("AI draft"),
    );
    expect(draftTile?.textContent).toContain("Not generated");
    expect(draftTile?.textContent).toContain("Model not found");
    expect(log()?.querySelector(".mindy-answer--unverified")).toBeNull();
    expect(log()?.querySelector(".mindy-held")).not.toBeNull();
    expect(lastDetails()?.textContent).toContain("MODEL_NOT_FOUND");
  });

  it("flags synthetic context provenance and shows the Controller decision in diagnostics", async () => {
    await render(api());
    await askQuestion("Explain equivalent fractions.");

    const tools = lastDetails();
    expect(tools?.querySelector('[role="note"]')?.textContent).toContain(
      "Synthetic defaults used for Mastery (knowledge tracing)",
    );
    const synthetic = tools?.querySelector('li[data-origin="SYNTHETIC"]');
    expect(synthetic?.textContent).toContain("Mastery (knowledge tracing)");
    expect(synthetic?.querySelector(".origin-badge")?.textContent).toBe("Synthetic");
    expect(tools?.querySelector('li[data-origin="REAL"] .origin-badge')?.textContent).toBe("Real");
    const glance = tools?.querySelector('[aria-label="At a glance"]');
    expect(glance?.textContent).toContain("MAT-FRC");
    expect(glance?.textContent).toContain("Independent retry");
    expect(glance?.textContent).toContain("Blocked");
    expect(tools?.querySelector(".reason-chips li")?.textContent).toBe("Pre interaction");
    expect(tools?.querySelector(".reason-chips li")?.getAttribute("title")).toBe("PRE_INTERACTION");
    const technical = tools?.querySelector("details.research-subsection");
    expect(technical?.querySelector("summary")?.textContent).toBe("Technical details");
    expect(technical?.textContent).toContain("L0 — Independent retry");
    expect(technical?.textContent).toContain("PRE_INTERACTION");
  });

  it("shows failed requests inline and retries the same question", async () => {
    const ask = vi
      .fn()
      .mockRejectedValueOnce(new Error("The Tutor demo timed out. Please try again."))
      .mockResolvedValueOnce(blocked);
    await render(api({ ask }));

    await askQuestion("Why is 1/2 equal to 2/4?");
    expect(log()?.querySelector('[role="alert"]')?.textContent).toContain("timed out");

    await act(async () => button("Try again")?.click());
    await flush();

    expect(ask).toHaveBeenCalledTimes(2);
    expect(ask).toHaveBeenLastCalledWith(session, "Why is 1/2 equal to 2/4?", "en");
    expect(log()?.querySelectorAll(".student-message")).toHaveLength(1);
    expect(log()?.querySelector('[role="alert"]')).toBeNull();
  });

  it("records a researcher-reviewed attempt as a new turn with the next Controller decision", async () => {
    const client = api();
    await render(client);
    await askQuestion("Why is 1/2 equal to 2/4?");

    const panel = host.querySelector("form.attempt-form");
    const policy = panel?.querySelectorAll<HTMLInputElement>('input:not([type="checkbox"])')[1];
    const reviewed = panel?.querySelectorAll<HTMLInputElement>('input[type="checkbox"]')[1];
    if (!policy || !reviewed) throw new Error("annotation controls missing");
    change(policy, "controlled-policy-v1");
    await act(async () => reviewed.click());
    await act(async () =>
      policy.closest("form")?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })),
    );
    await flush();

    expect(client.attempt).toHaveBeenCalledWith(
      session,
      blocked.interaction_id,
      expect.objectContaining({
        is_correct: false,
        severity_policy_version: "controlled-policy-v1",
        reviewer_confirmed: true,
      }),
    );
    expect(log()?.textContent).toContain("Researcher recorded an attempt review");
    expect(lastDetails()?.textContent).toContain("L4 — Guided steps");
    expect(host.querySelectorAll("form.attempt-form")).toHaveLength(1);
    expect(lastDetails()?.querySelector("form.attempt-form")).not.toBeNull();
  });

  it("ends the server session and starts a fresh one for a new chat", async () => {
    const client = api();
    await render(client);
    await askQuestion("Why is 1/2 equal to 2/4?");

    await act(async () => button("New chat")?.click());
    await flush();

    expect(client.end).toHaveBeenCalledWith(session);
    expect(client.start).toHaveBeenCalledTimes(2);
    expect(log()?.querySelectorAll(".student-message")).toHaveLength(0);
  });
});
