// Small helpers that turn API values into the words and colours the screens show.

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

const dayFormat = new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short" });
const shortFormat = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" });

export function dayLabel(value: string): string {
  return dayFormat.format(asLocalDate(value));
}

export function shortDate(value: string): string {
  return shortFormat.format(asLocalDate(value));
}

export function shortId(id: string): string {
  return id.slice(0, 4).toUpperCase();
}

// ---- skills are grouped into the four areas of the question bank -----------------------------

export type Area = "APT" | "MAT" | "LAN" | "ENV";

export const AREAS: { code: Area; name: string; blurb: string }[] = [
  { code: "APT", name: "Aptitude", blurb: "Patterns, logic and spotting what fits" },
  { code: "MAT", name: "Maths", blurb: "Numbers, shapes and measures" },
  { code: "LAN", name: "Language", blurb: "Words, grammar and understanding" },
  { code: "ENV", name: "Environment", blurb: "People, nature and the world around us" },
];

export function percent(value: number): number {
  return Math.round(value * 100);
}

// ---- paper and page wording ------------------------------------------------------------------

const PAPER_STATUS: Record<string, string> = {
  generated: "Ready to print",
  partially_uploaded: "Photos in progress",
  graded: "Marked",
  needs_review: "Needs you",
  confirmed: "Done",
  cancelled: "Cancelled",
};

export function paperStatusLabel(status: string): string {
  return PAPER_STATUS[status] ?? status;
}

export function paperTitle(mode: string): string {
  return mode === "diagnostic" ? "First check-up paper" : "Practice paper";
}
