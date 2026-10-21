import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import gameSource from "../mobile-learning-flow/MobileLearningApp.tsx?raw";
import {
  ApiError,
  anyPageChecking,
  describeFailure,
  friendlyMessage,
  type PagePhoto,
  pageState,
  type ReviewItem,
  toApiError,
} from "./api";
import { dayLabel, scoreText, skillName } from "./format";
import { dictionaries, getLanguage, initialLanguage, setLanguage, tn } from "./i18n";
import { DEFAULT_SHARED_LEARNER_ID, SHARED_LEARNER_ID } from "./hooks";
import { PapersApp } from "./PapersApp";
import {
  blankCount,
  buildDecisions,
  type Choice,
  decidedCount,
  groupByQuestion,
  isReadyToSubmit,
  itemKey,
  partTitle,
  toggleBlank,
} from "./reviewLogic";
import { parseRoute } from "./router";
import { HistoryScreen } from "./screens/HistoryScreen";
import { MasteryScreen, skillLine } from "./screens/MasteryScreen";
import { ReportScreen } from "./screens/ReportScreen";
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
    const plain = await toApiError(
      new Response(JSON.stringify({ detail: "Paper not found" }), {
        status: 404,
      }),
    );
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
    expect(parseRoute(`#/papers/${ID_A}/report`)).toEqual({
      name: "report",
      id: ID_A,
    });
    expect(parseRoute(`#/review/${ID_B}`)).toEqual({
      name: "review",
      id: ID_B,
    });
    expect(parseRoute("#/mastery")).toEqual({ name: "mastery" });
    expect(parseRoute("#/history")).toEqual({ name: "history" });
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
  label: null,
  part_count: 1,
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
    const blank: Record<string, Choice> = {
      [itemKey(items[1])]: { blank: true, text: "ignored" },
    };
    expect(buildDecisions([items[1]], blank)).toEqual([{ paper_item_id: ID_B, part_no: 1, text: "" }]);
  });
});

// ---- one card per question, one labelled box per answer -----------------------------------------

describe("questions with several answers", () => {
  const part = (n: number, count: number, label: string | null = null): ReviewItem => ({
    ...short(ID_B, 9),
    part_no: n,
    part_count: count,
    label,
    reading: { text: "" },
  });

  it("puts the five answers of question 9 on one card, in order", () => {
    const five = [part(3, 5), part(1, 5), part(5, 5), part(2, 5), part(4, 5)];
    const groups = groupByQuestion([...five, mcq(ID_A, 4)]);

    expect(groups.map((g) => g.position)).toEqual([4, 9]);
    const nine = groups[1];
    expect(nine.partCount).toBe(5);
    expect(nine.items.map((i) => i.part_no)).toEqual([1, 2, 3, 4, 5]);
  });

  it("names each box, with the printed label when there is one", () => {
    expect(partTitle(part(2, 5))).toBe("Answer 2 of 5");
    expect(partTitle(part(2, 2, "ii"))).toBe("(ii) Answer 2 of 2");
  });

  it("keeps what was typed when 'No answer' is tapped, and again when it is tapped back", () => {
    const typed: Choice = { text: "උතුර" };
    const blank = toggleBlank(typed);
    expect(blank).toEqual({ blank: true, text: "උතුර" });
    expect(toggleBlank(blank)).toEqual({ text: "උතුර" });
    expect(toggleBlank(undefined)).toEqual({ blank: true, text: "" });
  });

  it("counts the answers that were left as 'No answer' on purpose", () => {
    const a = part(1, 2);
    const b = part(2, 2);
    const m = mcq(ID_A, 4);
    const choices: Record<string, Choice> = {
      [itemKey(a)]: { blank: true, text: "" },
      [itemKey(b)]: { text: "දකුණ" },
      [itemKey(m)]: { selected: null },
    };
    expect(blankCount([a, b, m], choices)).toBe(2);
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
      results: [
        {
          paper_item_id: ID_C,
          position: 1,
          question_id: "1.1",
          result: "correct",
        },
      ],
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

describe("review screen with a question that has several answers", () => {
  it("shows one picture and one labelled box per answer, and asks before saving blanks", async () => {
    const part = (n: number): ReviewItem => ({
      ...short(ID_B, 3),
      part_no: n,
      part_count: 2,
      label: n === 1 ? "i" : "ii",
      reading: { text: "" },
    });
    answerWith({
      submission_id: "s1",
      paper_id: ID_A,
      page: 1,
      status: "needs_review",
      in_progress: false,
      failure_reason: null,
      message: null,
      uploaded_at: "2026-10-17T10:00:00Z",
      summary: { items: 1, auto_final: 0, needs_review: 1 },
      review_items: [part(1), part(2)],
      results: [],
    });

    await show(<Review submissionId="s1" />);

    expect(host.querySelectorAll("li.mb-review").length).toBe(1); // one card for the question
    expect(host.querySelectorAll("img").length).toBe(1); // one picture
    expect(host.querySelectorAll("input[type=text]").length).toBe(2); // one box per answer
    const text = host.textContent ?? "";
    expect(text).toContain("(i) Answer 1 of 2");
    expect(text).toContain("(ii) Answer 2 of 2");
    expect(text).toContain("This question has 2 answers");
  });
});

// ---- the results list shows every marked question, and past papers have their own list -------

const reportItem = (position: number, result: string, extra: object = {}) => ({
  position,
  question_id: `q${position}`,
  skill_code: "MAT-FRC",
  result,
  correct_answer_text: result === "wrong" || result === "blank" ? "1" : null,
  skill_name: "Fractions",
  skill_name_si: null,
  written: [{ part_no: 1, label: null, text: result === "blank" ? null : "2" }],
  picture_url: `/api/v1/submissions/s1/crops/i${position}`,
  ...extra,
});

const reportBody = {
  paper_id: ID_A,
  code: "ABC",
  week_start: "2026-10-17",
  language: "si",
  pages_total: 1,
  pages_marked: 1,
  complete: true,
  summary: {
    questions: 4,
    marked: 3,
    correct: 1,
    wrong: 1,
    blank: 1,
    waiting_for_parent: 1,
    not_uploaded: 0,
  },
  skills: [],
  items: [
    reportItem(1, "correct"),
    reportItem(2, "wrong"),
    reportItem(3, "blank"),
    reportItem(4, "under_review", { picture_url: null }),
  ],
  mistakes: [],
  answer_list: [{ position: 2, answers: [{ part_no: 1, label: null, answer: "1" }] }],
  next_paper_date: "2026-10-24",
  photos_kept_until: null,
};

describe("results screen", () => {
  it("lists the right questions together with the wrong ones, and leaves out those still waiting", async () => {
    answerWith(reportBody);

    await show(<ReportScreen paperId={ID_A} />);

    const cards = [...host.querySelectorAll("li.mb-mistake")].map((c) => c.textContent ?? "");
    expect(cards.length).toBe(3);
    expect(cards[0]).toContain("Question 1");
    expect(cards[0]).toContain("Correct");
    expect(cards[1]).toContain("Not correct");
    expect(cards[2]).toContain("Left blank");
    expect(host.textContent).not.toContain("Question 4"); // under review: not shown yet
    expect(host.textContent).toContain("All (3)");
    expect(host.textContent).toContain("Correct (1)");
    expect(host.textContent).toContain("To practise (2)");
  });

  it("the filter shows only the right questions, or only the ones to practise", async () => {
    answerWith(reportBody);
    await show(<ReportScreen paperId={ID_A} />);
    const pick = async (label: string) => {
      const radio = [...host.querySelectorAll("label")].find((l) => l.textContent?.startsWith(label));
      await act(async () => {
        radio?.querySelector("input")?.click();
      });
    };

    await pick("Correct");
    expect([...host.querySelectorAll("li.mb-mistake h3")].map((h) => h.textContent)).toEqual(["Question 1"]);

    await pick("To practise");
    expect([...host.querySelectorAll("li.mb-mistake h3")].map((h) => h.textContent)).toEqual([
      "Question 2",
      "Question 3",
    ]);
  });

  it("gives the answer list only for the questions that were not right", async () => {
    answerWith(reportBody);
    await show(<ReportScreen paperId={ID_A} />);

    const list = host.querySelector(".mb-answers")?.textContent ?? "";
    expect(list).toContain("Q2");
    expect(list).not.toContain("Q1");
  });
});

describe("past papers screen", () => {
  const paper = (id: string, status: string, results: object | null, complete: boolean) => ({
    paper_id: id,
    code: "C",
    status,
    mode: "practice",
    language: "si",
    week_start: "2026-10-10",
    next_paper_date: "2026-10-17",
    page_count: 2,
    question_count: 20,
    estimated_minutes: 30,
    pdf_url: "/x",
    created_at: null,
    skipped_skills: [],
    results,
    results_complete: complete,
  });

  it("shows how each paper went, and links to its results", async () => {
    answerWith([
      paper(
        ID_A,
        "confirmed",
        {
          questions: 11,
          marked: 11,
          correct: 7,
          wrong: 3,
          blank: 1,
          waiting_for_parent: 0,
          not_uploaded: 0,
        },
        true,
      ),
      paper(ID_B, "generated", null, false),
    ]);

    await show(<HistoryScreen learnerId={ID_C} />);

    const text = host.textContent ?? "";
    expect(text).toContain("7 of 11 correct");
    expect(text).toContain("Complete");
    expect(text).toContain("No pages have been marked yet.");
    const links = [...host.querySelectorAll("a")].map((a) => a.getAttribute("href"));
    expect(links).toContain(`#/papers/${ID_A}/report`);
    expect(links).not.toContain(`#/papers/${ID_B}/report`); // nothing to see yet for that one
    expect(scoreText({ correct: 7, marked: 11 })).toBe("7 of 11 correct");
  });
});

// ---- one shared learner for the game and the practice screens (there is no login yet) -------------

describe("the shared learner", () => {
  it("is the same learner the game uses, so game answers and paper answers belong together", () => {
    // The game imports the papers constant, so there is one learner id to change.
    expect(gameSource).toMatch(/import \{ SHARED_LEARNER_ID \} from "\.\.\/papers\/hooks"/);
    expect(gameSource).toContain("learnerId = SHARED_LEARNER_ID");
    expect(gameSource).not.toMatch(/"00000000-0000-4000-8000-000000000721"/);
    expect(SHARED_LEARNER_ID).toBe(import.meta.env.VITE_MOBILE_LEARNING_LEARNER_ID ?? DEFAULT_SHARED_LEARNER_ID);
  });

  it("asks the backend about that learner, with no saved choice involved", async () => {
    window.localStorage.setItem("mindbridge.learnerId", ID_A); // a leftover from the old picker
    const asked: string[] = [];
    const learner = {
      id: SHARED_LEARNER_ID,
      grade: 5,
      preferred_language: "si",
      created_at: "2026-10-01T00:00:00Z",
      updated_at: "2026-10-01T00:00:00Z",
    };
    vi.stubGlobal("fetch", async (url: string) => {
      asked.push(String(url));
      const body = String(url).endsWith(`/learners/${SHARED_LEARNER_ID}`) ? learner : [];
      return new Response(JSON.stringify(body), { status: 200 });
    });

    await show(<PapersApp embedded route={{ name: "history" }} />);

    expect(asked.some((u) => u.includes(`/learners/${SHARED_LEARNER_ID}`))).toBe(true);
    expect(asked.some((u) => u.includes(ID_A))).toBe(false); // the old choice is ignored
    window.localStorage.removeItem("mindbridge.learnerId");
  });

  it("says how to create the learner when this database does not have it", async () => {
    vi.stubGlobal(
      "fetch",
      async () =>
        new Response(JSON.stringify({ detail: "Learner not found" }), {
          status: 404,
        }),
    );

    await show(<PapersApp embedded route={{ name: "papers" }} />);

    const text = host.textContent ?? "";
    expect(text).toContain("Learner not set up");
    expect(text).toContain(SHARED_LEARNER_ID);
    expect(text).toContain("python -m scripts.seed_dev_learner");
    expect(host.querySelector("a.mb-link-card")).toBeNull(); // nothing to open until it exists
  });
});

// ---- the practice area is one page with buttons, not a second tab bar -----------------------------

describe("practice navigation", () => {
  const learner = {
    id: SHARED_LEARNER_ID,
    grade: 5,
    preferred_language: "si",
    created_at: "2026-10-01T00:00:00Z",
    updated_at: "2026-10-01T00:00:00Z",
  };
  const waiting = {
    state: "not_yet_eligible",
    can_generate: false,
    joined_at: "2026-10-18T00:00:00Z",
    eligible_from: "2026-10-25T00:00:00Z",
    days_until_eligible: 7,
    week_start: "2026-10-17",
    next_paper_date: "2026-10-24",
    paper: null,
  };

  function backend() {
    vi.stubGlobal("fetch", async (url: string) => {
      const address = String(url);
      let body: unknown = [];
      if (address.endsWith("/availability")) body = waiting;
      else if (address.endsWith(`/learners/${SHARED_LEARNER_ID}`)) body = learner;
      else if (address.endsWith("/mastery"))
        body = {
          computed_at: "2026-10-18T00:00:00Z",
          model_version: "v",
          n_attempts: 0,
          definition: "",
          skills: [],
        };
      return new Response(JSON.stringify(body), { status: 200 });
    });
  }

  it("opens past papers and skills with buttons on the practice page, and has no tab bar", async () => {
    backend();

    await show(<PapersApp embedded route={{ name: "papers" }} />);

    const cards = [...host.querySelectorAll("a.mb-link-card")];
    expect(cards.map((c) => c.getAttribute("href"))).toEqual(["#/history", "#/mastery"]);
    expect(cards.map((c) => c.querySelector("strong")?.textContent)).toEqual(["Past papers", "My skills"]);
    expect(cards.every((c) => c.textContent?.includes("Open"))).toBe(true);
    // each card carries its own picture (decorative: the title says what it is)
    const pictures = cards.map((c) => c.querySelector("img"));
    expect(pictures.map((p) => p?.getAttribute("src"))).toEqual([
      "/practice/past-papers.png",
      "/practice/my-skills.png",
    ]);
    expect(pictures.every((p) => p?.getAttribute("alt") === "")).toBe(true);
    expect(host.querySelector(".mb-tabs, .mb-tab, nav")).toBeNull();
  });

  it("gives every other practice page a way back to the practice page", async () => {
    backend();
    for (const route of [{ name: "history" } as const, { name: "mastery" } as const]) {
      host.replaceChildren();
      await show(<PapersApp embedded route={route} />);
      const back = host.querySelector("a.mb-back");
      expect(back?.getAttribute("href")).toBe("#/papers");
      expect(back?.textContent).toContain("Practice");
      expect(host.querySelector(".mb-tabs")).toBeNull();
    }
  });
});

// ---- skill areas open and close -----------------------------------------------------------------------

describe("skill areas", () => {
  const skill = (code: string, area: string, mastery: number | null, attempts: number) => ({
    code,
    area,
    name_en: `Skill ${code}`,
    name_si: null,
    mastery,
    attempts,
  });
  const body = {
    computed_at: "2026-10-18T00:00:00Z",
    model_version: "v",
    n_attempts: 9,
    definition: "",
    skills: [skill("APT-PAT", "APT", 0.8, 6), skill("MAT-FRC", "MAT", 0.6, 5), skill("MAT-NUM", "MAT", null, 1)],
  };

  const toggles = () => [...host.querySelectorAll<HTMLButtonElement>("button.mb-area__toggle")];
  const panelOf = (button: HTMLButtonElement) => document.getElementById(button.getAttribute("aria-controls") ?? "");

  it("shows the four areas closed, with how many of their skills are measured", async () => {
    answerWith(body);

    await show(<MasteryScreen learnerId={ID_A} />);

    expect(toggles().map((b) => b.querySelector(".mb-area__name")?.textContent)).toEqual([
      "Aptitude",
      "Maths",
      "Language",
      "Environment",
    ]);
    expect(toggles().every((b) => b.getAttribute("aria-expanded") === "false")).toBe(true);
    expect(toggles()[1].textContent).toContain("1 of 2 measured");
    // closed: the skills are there but cannot be reached or read out
    const closed = panelOf(toggles()[1])?.querySelector(".mb-area__inner");
    expect(closed?.hasAttribute("inert")).toBe(true);
    expect(host.querySelectorAll(".mb-area.is-open").length).toBe(0);
  });

  it("opens one area to show its own skills, and closes it again", async () => {
    answerWith(body);
    await show(<MasteryScreen learnerId={ID_A} />);
    const maths = toggles()[1];

    await act(async () => maths.click());

    expect(maths.getAttribute("aria-expanded")).toBe("true");
    const inner = panelOf(maths)?.querySelector(".mb-area__inner");
    expect(inner?.hasAttribute("inert")).toBe(false);
    expect([...(inner?.querySelectorAll(".mb-skill__names strong") ?? [])].map((s) => s.textContent)).toEqual([
      "Skill MAT-FRC",
      "Skill MAT-NUM",
    ]); // each skill of Maths, once, and none from another area
    expect(toggles().filter((b) => b.getAttribute("aria-expanded") === "true")).toEqual([maths]);

    await act(async () => maths.click());

    expect(maths.getAttribute("aria-expanded")).toBe("false");
    expect(panelOf(maths)?.querySelector(".mb-area__inner")?.hasAttribute("inert")).toBe(true);
  });

  it("opens each area on its own", async () => {
    answerWith(body);
    await show(<MasteryScreen learnerId={ID_A} />);

    await act(async () => toggles()[0].click());
    await act(async () => toggles()[1].click());

    expect(toggles().map((b) => b.getAttribute("aria-expanded"))).toEqual(["true", "true", "false", "false"]);
  });
});

// ---- the language of the practice pages -----------------------------------------------------------------

describe("language", () => {
  const emptyMastery = {
    computed_at: "2026-10-18T00:00:00Z",
    model_version: "v",
    n_attempts: 0,
    definition: "",
    skills: [],
  };
  const gear = () => host.querySelector<HTMLButtonElement>("button.mb-settings-btn");
  const choices = () => [...document.querySelectorAll<HTMLInputElement>(".mb-sheet__choice input")];

  it("speaks Sinhala until someone picks another language", () => {
    localStorage.removeItem("mindbridge.practiceLanguage");
    expect(initialLanguage()).toBe("si");
  });

  it("remembers the saved language, and ignores a value it does not know", () => {
    localStorage.setItem("mindbridge.practiceLanguage", "ta");
    expect(initialLanguage()).toBe("ta");
    localStorage.setItem("mindbridge.practiceLanguage", "fr");
    expect(initialLanguage()).toBe("si");
  });

  it("puts a settings gear at the top of the page, closed until it is tapped", async () => {
    answerWith(emptyMastery);
    await show(<MasteryScreen learnerId={ID_A} />);

    expect(gear()?.getAttribute("aria-label")).toBe("Settings");
    expect(document.querySelector(".mb-sheet")).toBeNull();
  });

  it("changes the words, saves the choice and closes with Done", async () => {
    answerWith(emptyMastery);
    await show(<MasteryScreen learnerId={ID_A} />);

    await act(async () => gear()?.click());
    expect(choices().map((c) => c.closest("label")?.textContent)).toEqual(["සිංහල", "English", "தமிழ்"]);
    expect(choices().map((c) => c.checked)).toEqual([false, true, false]); // the tests start in English

    await act(async () => choices()[0].click());
    expect(host.querySelector("h1")?.textContent).toBe("ඉගෙනීම සිදුවන ආකාරය");
    expect(getLanguage()).toBe("si");
    expect(localStorage.getItem("mindbridge.practiceLanguage")).toBe("si");

    await act(async () => choices()[2].click());
    expect(host.querySelector("h1")?.textContent).toBe("கற்றல் எப்படிப் போகிறது");

    await act(async () => document.querySelector<HTMLButtonElement>(".mb-sheet__panel .mb-btn")?.click());
    expect(document.querySelector(".mb-sheet")).toBeNull();
  });

  it("closes the sheet with the Escape key", async () => {
    answerWith(emptyMastery);
    await show(<MasteryScreen learnerId={ID_A} />);
    await act(async () => gear()?.click());

    await act(async () => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    });

    expect(document.querySelector(".mb-sheet")).toBeNull();
  });

  it("writes dates in the chosen language", () => {
    const english = dayLabel("2026-10-17");
    setLanguage("si", { remember: false });
    expect(dayLabel("2026-10-17")).not.toBe(english);
  });

  it("names skills in Sinhala where there is a name, and in English otherwise", () => {
    setLanguage("si", { remember: false });
    expect(skillName({ en: "Fractions", si: "භාග" })).toBe("භාග");
    expect(skillName({ en: "Fractions", si: null })).toBe("Fractions");
    setLanguage("ta", { remember: false });
    expect(skillName({ en: "Fractions", si: "භාග" })).toBe("Fractions");
  });

  it("gives Sinhala and Tamil every sentence English has, with the same {blanks}", () => {
    const blanks = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
    const bold = (text: string) => (text.match(/\*\*/g) ?? []).length;
    for (const language of ["si", "ta"] as const) {
      const words = dictionaries[language];
      expect(Object.keys(words).sort()).toEqual(Object.keys(dictionaries.en).sort());
      for (const key of Object.keys(dictionaries.en) as (keyof typeof words)[]) {
        expect(words[key].trim(), `${language} ${key}`).not.toBe("");
        expect(blanks(words[key]), `${language} ${key}`).toEqual(blanks(dictionaries.en[key]));
        expect(bold(words[key]), `${language} ${key}`).toBe(bold(dictionaries.en[key]));
      }
    }
  });

  it("uses singular and plural sentences", () => {
    expect(tn("count.questions", 1)).toBe("1 question");
    expect(tn("count.questions", 3)).toBe("3 questions");
  });
});
