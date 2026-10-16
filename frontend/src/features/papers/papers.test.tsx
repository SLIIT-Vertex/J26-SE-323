import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  type PagePhoto,
  type ReviewItem,
  anyPageChecking,
  describeFailure,
  friendlyMessage,
  pageState,
  toApiError,
} from "./api";
import { dayLabel } from "./format";
import { parseRoute } from "./router";
import { type Choice, buildDecisions, decidedCount, isReadyToSubmit, itemKey } from "./reviewLogic";
import { MasteryScreen, skillLine } from "./screens/MasteryScreen";
import { Review } from "./screens/Review";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const ID_A = "11111111-1111-4111-8111-111111111111";
const ID_B = "22222222-2222-4222-8222-222222222222";
const ID_C = "33333333-3333-4333-8333-333333333333";

// ---- the API client: status mapping and failure text -------------------------------------------

describe("api errors", () => {
  it("reads the code and message the server sends", async () => {
    const response = new Response(JSON.stringify({ detail: { code: "photos_removed", message: "gone" } }), {
      status: 410,
    });
    const error = await toApiError(response);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(410);
    expect(error.code).toBe("photos_removed");
  });

  it("reads a plain text detail and survives a body that is not JSON", async () => {
    const plain = await toApiError(new Response(JSON.stringify({ detail: "Paper not found" }), { status: 404 }));
    expect(plain.message).toBe("Paper not found");
    const broken = await toApiError(new Response("<html>", { status: 502 }));
    expect(broken.code).toBe("http_502");
  });

  it("shows a friendly sentence, not server wording", () => {
    expect(friendlyMessage(new ApiError(413, "photo_too_large", "payload"))).toContain("too big");
    expect(friendlyMessage(new ApiError(500, "http_500", "Traceback ..."))).toBe(
      "Something went wrong on our side. Please try again.",
    );
    expect(friendlyMessage(new TypeError("fetch failed"))).toContain("could not reach MindBridge");
  });

  it("explains why a photo cannot be used", () => {
    expect(describeFailure("markers_missing")).toContain("four black squares");
    expect(describeFailure("blurry")).toContain("blurry");
    expect(describeFailure("wrong_paper")).toContain("different paper");
    expect(describeFailure("wrong_page")).toContain("different page");
    expect(describeFailure("something_new", "server text")).toBe("server text");
  });
});

// ---- uploading: when to keep asking the server --------------------------------------------------

const page = (n: number, status: string | null): PagePhoto => ({
  page: n,
  submission_id: status ? `s${n}` : null,
  submission_status: status,
});

describe("page states and polling", () => {
  it("keeps polling only while a page is being checked", () => {
    expect(anyPageChecking([page(1, "uploaded")])).toBe(true);
    expect(anyPageChecking([page(1, "grading"), page(2, null)])).toBe(true);
  });

  it("stops on graded, needs_review, failed_alignment and confirmed", () => {
    for (const status of ["graded", "needs_review", "failed_alignment", "confirmed", "error"]) {
      expect(anyPageChecking([page(1, status)])).toBe(false);
    }
    expect(anyPageChecking([])).toBe(false);
    expect(anyPageChecking(null)).toBe(false);
  });

  it("maps submission statuses to what the parent sees", () => {
    expect(pageState(null)).toBe("empty");
    expect(pageState("uploaded")).toBe("checking");
    expect(pageState("failed_alignment")).toBe("retake");
    expect(pageState("needs_review")).toBe("review");
    expect(pageState("graded")).toBe("done");
    expect(pageState("confirmed")).toBe("done");
    expect(pageState("error")).toBe("problem");
  });
});

// ---- routes and dates ----------------------------------------------------------------------------

describe("routes", () => {
  it("knows its own screens and leaves the others alone", () => {
    expect(parseRoute("#/papers")).toEqual({ name: "papers" });
    expect(parseRoute("#/papers/")).toEqual({ name: "papers" });
    expect(parseRoute(`#/papers/${ID_A}`)).toEqual({ name: "paper", id: ID_A });
    expect(parseRoute(`#/papers/${ID_A}/report`)).toEqual({ name: "report", id: ID_A });
    expect(parseRoute(`#/review/${ID_B}`)).toEqual({ name: "review", id: ID_B });
    expect(parseRoute("#/mastery")).toEqual({ name: "mastery" });
    expect(parseRoute("#/play")).toBeNull();
    expect(parseRoute("")).toBeNull();
  });

  it("shows a calendar date on the same day in every time zone", () => {
    expect(dayLabel("2026-10-17")).toContain("17");
    expect(dayLabel("2026-10-17")).toContain("Oct");
  });
});

// ---- the review: nothing is submitted until every unclear answer has a decision ----------------

const mcq = (id: string, position: number): ReviewItem => ({
  paper_item_id: id,
  position,
  part_no: 1,
  part_type: "mcq",
  crop_url: `/api/v1/submissions/s/crops/${id}`,
  reading: { selected: "3" },
  reason: "near_miss",
  options: ["1", "2", "3", "4"],
  ask: null,
});

const short = (id: string, position: number): ReviewItem => ({
  ...mcq(id, position),
  part_type: "short",
  reading: { text: "කුරුල්ලා" },
  options: null,
});

const instruction = (id: string, position: number): ReviewItem => ({
  ...short(id, position),
  reading: { text: "" },
  ask: "Is it done as the question asks?",
});

describe("review decisions", () => {
  const items = [mcq(ID_A, 4), short(ID_B, 9), instruction(ID_C, 12)];

  it("cannot be submitted until every flagged item has a decision", () => {
    const choices: Record<string, Choice> = {};
    expect(isReadyToSubmit(items, choices)).toBe(false);
    choices[itemKey(items[0])] = { selected: "2" };
    choices[itemKey(items[1])] = { text: "kurulla" };
    expect(isReadyToSubmit(items, choices)).toBe(false);
    expect(decidedCount(items, choices)).toBe(2);
    choices[itemKey(items[2])] = { instructionMet: false };
    expect(isReadyToSubmit(items, choices)).toBe(true);
  });

  it("treats an empty text box as undecided until 'No answer' is chosen on purpose", () => {
    const item = short(ID_B, 9);
    expect(isReadyToSubmit([item], { [itemKey(item)]: { text: "   " } })).toBe(false);
    expect(isReadyToSubmit([item], { [itemKey(item)]: { blank: true, text: "" } })).toBe(true);
    expect(isReadyToSubmit([], {})).toBe(false);
  });

  it("builds the request the server expects, with null or empty for 'no answer'", () => {
    const choices: Record<string, Choice> = {
      [itemKey(items[0])]: { selected: null },
      [itemKey(items[1])]: { text: " kurulla " },
      [itemKey(items[2])]: { instructionMet: true },
    };
    expect(buildDecisions(items, choices)).toEqual([
      { paper_item_id: ID_A, part_no: 1, selected: null },
      { paper_item_id: ID_B, part_no: 1, text: "kurulla" },
      { paper_item_id: ID_C, part_no: 1, instruction_met: true },
    ]);
    const blank: Record<string, Choice> = { [itemKey(items[1])]: { blank: true, text: "ignored" } };
    expect(buildDecisions([items[1]], blank)).toEqual([{ paper_item_id: ID_B, part_no: 1, text: "" }]);
  });
});

// ---- rendering: the review shows no correctness, the mastery screen no placeholder numbers ------

let host: HTMLDivElement;

beforeEach(() => {
  host = document.createElement("div");
  document.body.append(host);
});

afterEach(() => {
  host.remove();
  vi.unstubAllGlobals();
});

function answerWith(body: unknown) {
  vi.stubGlobal("fetch", async () => new Response(JSON.stringify(body), { status: 200 }));
}

async function show(element: React.ReactElement) {
  const root = createRoot(host);
  await act(async () => {
    root.render(element);
  });
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
  return root;
}

describe("review screen", () => {
  it("never says whether an answer is right or wrong, and starts with nothing chosen", async () => {
    answerWith({
      submission_id: "s1",
      paper_id: ID_A,
      page: 2,
      status: "needs_review",
      in_progress: false,
      failure_reason: null,
      message: null,
      uploaded_at: "2026-10-17T10:00:00Z",
      summary: { items: 3, auto_final: 1, needs_review: 2 },
      review_items: [mcq(ID_A, 4), short(ID_B, 9)],
      // other questions on the page were already decided; the screen must not show them
      results: [{ paper_item_id: ID_C, position: 1, question_id: "1.1", result: "correct" }],
    });

    await show(<Review submissionId="s1" />);

    // the explanation at the top says "right or wrong" in words; everything else must not
    host.querySelector(".mb-lead")?.remove();
    const text = (host.textContent ?? "").toLowerCase();
    expect(text).toContain("question 4");
    expect(text).toContain("question 9");
    expect(text).not.toContain("question 1");
    expect(text).not.toMatch(/\b(correct|wrong|incorrect|right answer|mistake)\b/);
    for (const pressed of host.querySelectorAll("[aria-pressed]")) {
      expect(pressed.getAttribute("aria-pressed")).toBe("false");
    }
    const save = [...host.querySelectorAll("button")].find((b) => b.textContent === "Save answers");
    expect(save?.disabled).toBe(true);
  });
});

describe("mastery screen", () => {
  const skill = (code: string, area: string, mastery: number | null, attempts: number) => ({
    code,
    area,
    name_en: `Skill ${code}`,
    name_si: null,
    mastery,
    attempts,
  });

  it("describes skills with fewer than three answers instead of showing a number", () => {
    expect(skillLine(skill("MAT-FRC", "MAT", null, 0))).toBe("Not enough questions yet");
    expect(skillLine(skill("MAT-FRC", "MAT", null, 2))).toBe("Not enough questions yet (2 answered)");
    expect(skillLine(skill("MAT-FRC", "MAT", 0.62, 14))).toBe("62%");
  });

  it("renders unknown skills as 'Not enough questions yet' and no placeholder percentage", async () => {
    answerWith({
      computed_at: "2026-10-17T10:00:00Z",
      model_version: "dkt-test",
      n_attempts: 5,
      definition: "Chance of answering a medium paper question correctly",
      skills: [skill("MAT-FRC", "MAT", null, 2), skill("APT-PAT", "APT", 0.8, 9)],
    });

    await show(<MasteryScreen learnerId={ID_A} />);

    const text = host.textContent ?? "";
    expect(text).toContain("Not enough questions yet (2 answered)");
    expect(text).toContain("80%");
    expect(text).not.toContain("50%");
    expect(text).not.toMatch(/(^|[^0-9])0%/);
    expect(text).toContain("1 of 2");
  });
});
