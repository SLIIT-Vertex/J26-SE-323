// Small helpers that turn API values into the words and colours the screens show.

import { locale, type MessageKey, t, tn } from "./i18n";

const LANGUAGES: Record<string, { name: string; native: string }> = {
  si: { name: "Sinhala", native: "සිංහල" },
  ta: { name: "Tamil", native: "தமிழ்" },
};

export function languageName(code: string): string {
  return LANGUAGES[code]?.name ?? code;
}

export function languageNative(code: string): string {
  return LANGUAGES[code]?.native ?? code;
}

/** "2026-10-17" is a calendar date, so it is read as local time (no time-zone shift). */
function asLocalDate(value: string): Date {
  const plain = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (plain) return new Date(Number(plain[1]), Number(plain[2]) - 1, Number(plain[3]));
  return new Date(value);
}

export function dayLabel(value: string): string {
  return new Intl.DateTimeFormat(locale(), {
    weekday: "short",
    day: "numeric",
    month: "short",
  }).format(asLocalDate(value));
}

export function shortDate(value: string): string {
  return new Intl.DateTimeFormat(locale(), {
    day: "numeric",
    month: "short",
  }).format(asLocalDate(value));
}

export function shortId(id: string): string {
  return id.slice(0, 4).toUpperCase();
}

// ---- skills are grouped into the four areas of the question bank -----------------------------

export type Area = "APT" | "MAT" | "LAN" | "ENV";

export const AREAS: { code: Area; name: string; blurb: string }[] = (["APT", "MAT", "LAN", "ENV"] as const).map(
  (code) => ({
    code,
    get name() {
      return t(`area.${code}.name` as MessageKey);
    },
    get blurb() {
      return t(`area.${code}.blurb` as MessageKey);
    },
  }),
);

export function percent(value: number): number {
  return Math.round(value * 100);
}

// ---- paper and page wording ------------------------------------------------------------------

const PAPER_STATUS = new Set(["generated", "partially_uploaded", "graded", "needs_review", "confirmed", "cancelled"]);

export function paperStatusLabel(status: string): string {
  return PAPER_STATUS.has(status) ? t(`status.${status}` as MessageKey) : status;
}

export function paperTitle(mode: string): string {
  return t(mode === "diagnostic" ? "paper.title.diagnostic" : "paper.title.practice");
}

/** "7 of 11 correct": how a paper went, among the questions that have a final mark. */
export function scoreText(totals: { correct: number; marked: number }): string {
  return t("history.score", { correct: totals.correct, marked: totals.marked });
}

export function resultLabel(result: string): string {
  return result === "correct" || result === "wrong" || result === "blank"
    ? t(`result.${result}` as MessageKey)
    : result;
}

/** "5 questions" / "1 question" / "1 page" / "3 pages". */
export function questionCount(n: number): string {
  return tn("count.questions", n);
}

export function pageCount(n: number): string {
  return tn("count.pages", n);
}

/** The skill's name in the selected language: Sinhala where it exists, English otherwise (also for Tamil). */
export function skillName(names: { en: string; si: string | null }): string {
  return locale().startsWith("si") && names.si ? names.si : names.en;
}
