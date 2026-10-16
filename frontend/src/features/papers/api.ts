// The paper, photo, review, report and mastery endpoints of the backend.
// Types are written by hand to match the API; none of them can carry the answer key.

const apiUrl: string = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api/v1";

/** Pictures come back as paths that start at the API prefix, so they need the origin. */
export const apiOrigin = new URL(apiUrl).origin;

// ---- types -------------------------------------------------------------------------------------

export type Learner = {
  id: string;
  grade: number;
  preferred_language: string;
  created_at: string;
};

export type PagePhoto = {
  page: number;
  submission_id: string | null;
  submission_status: string | null;
};

export type Paper = {
  paper_id: string;
  code: string;
  status: string;
  mode: string;
  language: string;
  week_start: string;
  next_paper_date: string;
  page_count: number;
  question_count: number;
  estimated_minutes: number;
  pdf_url: string;
  created_at: string | null;
  skipped_skills: string[];
  pages?: PagePhoto[] | null;
};

export type Availability = {
  state: "not_yet_eligible" | "available" | "generated";
  can_generate: boolean;
  joined_at: string;
  eligible_from: string;
  days_until_eligible: number;
  week_start: string;
  next_paper_date: string;
  paper: Paper | null;
};

export type ReviewItem = {
  paper_item_id: string;
  position: number;
  part_no: number;
  part_type: "mcq" | "short";
  crop_url: string;
  reading: { selected?: string | null; text?: string | null };
  reason: string | null;
  options: string[] | null;
  ask: string | null;
};

export type Submission = {
  submission_id: string;
  paper_id: string;
  page: number;
  status: string;
  in_progress: boolean;
  failure_reason: string | null;
  message: string | null;
  uploaded_at: string;
  summary: { items: number; auto_final: number; needs_review: number };
  review_items: ReviewItem[];
};

export type Decision = {
  paper_item_id: string;
  part_no: number;
  selected?: string | null;
  text?: string | null;
  instruction_met?: boolean | null;
};

export type SkillMastery = {
  code: string;
  area: string;
  name_en: string;
  name_si: string | null;
  mastery: number | null;
  attempts: number;
};

export type Mastery = {
  computed_at: string;
  model_version: string;
  n_attempts: number;
  definition: string;
  skills: SkillMastery[];
};

export type ReportItem = {
  position: number;
  question_id: string;
  skill_code: string;
  result: "correct" | "wrong" | "blank" | "under_review" | "not_uploaded";
  correct_answer_text: string | null;
};

export type Written = { part_no: number; label: string | null; text: string | null };

export type Mistake = {
  position: number;
  question_id: string;
  skill_code: string;
  skill_name: string;
  skill_name_si: string | null;
  result: "wrong" | "blank";
  written: Written[];
  picture_available: boolean;
  picture_url: string | null;
};

export type Report = {
  paper_id: string;
  code: string;
  week_start: string;
  language: string;
  pages_total: number;
  pages_marked: number;
  complete: boolean;
  summary: {
    questions: number;
    marked: number;
    correct: number;
    wrong: number;
    blank: number;
    waiting_for_parent: number;
    not_uploaded: number;
  };
  skills: {
    skill_code: string;
    name: string;
    name_si: string | null;
    correct: number;
    wrong: number;
    blank: number;
  }[];
  items: ReportItem[];
  mistakes: Mistake[];
  answer_list: {
    position: number;
    answers: { part_no: number; label: string | null; answer: string }[];
  }[];
  next_paper_date: string;
  photos_kept_until: string | null;
};

// ---- errors ------------------------------------------------------------------------------------

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

const FRIENDLY: Record<string, string> = {
  network: "We could not reach MindBridge. Check your connection and try again.",
  not_found: "We could not find that.",
  paper_cancelled: "This paper was cancelled.",
  photo_too_large: "That photo is too big. Please try a smaller one.",
  unreadable_image: "We could not open that photo. Please take it again.",
  page_already_graded: "This page has already been marked.",
  page_in_progress:
    "Some answers on this page already count. Please finish the unclear ones first.",
  photos_removed: "This picture is no longer kept.",
  not_eligible_yet: "The weekly paper opens after the first week in the app.",
};

/** What to show a parent for an error. Technical text from the server is only a fallback. */
export function friendlyMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return FRIENDLY[error.code] ?? (error.status >= 500 ? "Something went wrong on our side. Please try again." : error.message);
  }
  return FRIENDLY.network;
}

export async function toApiError(response: Response): Promise<ApiError> {
  let code = `http_${response.status}`;
  let message = `The server answered ${response.status}`;
  try {
    const body = (await response.json()) as { detail?: unknown };
    const detail = body.detail;
    if (typeof detail === "string") {
      message = detail;
    } else if (detail && typeof detail === "object" && !Array.isArray(detail)) {
      const record = detail as { code?: unknown; message?: unknown };
      if (typeof record.code === "string") code = record.code;
      if (typeof record.message === "string") message = record.message;
    }
  } catch {
    // not JSON: keep the generic text
  }
  return new ApiError(response.status, code, message);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiUrl}${path}`, init);
  } catch {
    throw new ApiError(0, "network", FRIENDLY.network);
  }
  if (!response.ok) throw await toApiError(response);
  return response.json() as Promise<T>;
}

// ---- what the parent is told when a photo cannot be used ----------------------------------------

const FAILURES: Record<string, string> = {
  markers_missing:
    "We could not see all four black squares. Please retake the photo and keep every corner in the picture.",
  low_match:
    "We could not match this photo to the printed page. Lay the page flat in good light and try again.",
  blurry: "The photo is blurry. Hold the phone steady and retake it.",
  wrong_paper: "This looks like a different paper. Please photograph the right one.",
  wrong_page: "This looks like a different page. Please check the page number.",
  internal_error: "Something went wrong on our side. Please try again in a moment.",
  file_missing: "Something went wrong on our side. Please try again in a moment.",
  paper_missing: "Something went wrong on our side. Please try again in a moment.",
};

export function describeFailure(reason: string | null, fallback?: string | null): string {
  if (reason && FAILURES[reason]) return FAILURES[reason];
  return fallback || "We could not use this photo. Please retake it.";
}

// ---- how a page is shown ----------------------------------------------------------------------

export type PageState = "empty" | "checking" | "retake" | "review" | "done" | "problem";

export function pageState(submissionStatus: string | null): PageState {
  switch (submissionStatus) {
    case null:
      return "empty";
    case "uploaded":
    case "grading":
      return "checking";
    case "failed_alignment":
      return "retake";
    case "needs_review":
      return "review";
    case "graded":
    case "confirmed":
      return "done";
    default:
      return "problem";
  }
}

/** Keep asking the server while any page is still being checked. */
export function anyPageChecking(pages: PagePhoto[] | null | undefined): boolean {
  return (pages ?? []).some((p) => pageState(p.submission_status) === "checking");
}

// ---- endpoints ---------------------------------------------------------------------------------

export const listLearners = () => request<Learner[]>("/learners");

export const createLearner = (grade: 4 | 5, preferredLanguage: "si" | "ta") =>
  request<Learner>("/learners", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ grade, preferred_language: preferredLanguage }),
  });

export const getLearner = (id: string) => request<Learner>(`/learners/${id}`);

export const getAvailability = (learnerId: string) =>
  request<Availability>(`/learners/${learnerId}/papers/availability`);

export const createWeeklyPaper = (learnerId: string) =>
  request<Paper>(`/learners/${learnerId}/papers`, { method: "POST" });

export const listPapers = (learnerId: string) =>
  request<Paper[]>(`/learners/${learnerId}/papers?limit=20`);

export const getPaper = (paperId: string) => request<Paper>(`/papers/${paperId}`);

export const getSubmission = (submissionId: string) =>
  request<Submission>(`/submissions/${submissionId}`);

export async function uploadPagePhoto(
  paperId: string,
  page: number,
  photo: File,
): Promise<{ submission_id: string; status: string }> {
  const form = new FormData();
  form.append("image", photo, photo.name || "page.jpg");
  return request(`/papers/${paperId}/pages/${page}/photo`, { method: "POST", body: form });
}

export const confirmDecisions = (submissionId: string, decisions: Decision[]) =>
  request<Submission>(`/submissions/${submissionId}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decisions }),
  });

export const getReport = (paperId: string) => request<Report>(`/papers/${paperId}/report`);

export const getMastery = (learnerId: string) => request<Mastery>(`/learners/${learnerId}/mastery`);

/** A picture path from the API, made into a full address. */
export const pictureUrl = (path: string) => (path.startsWith("http") ? path : `${apiOrigin}${path}`);

export const pdfUrl = (paper: Paper) => pictureUrl(paper.pdf_url);
