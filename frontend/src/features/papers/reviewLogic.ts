import type { Decision, ReviewItem } from "./api";
import { t } from "./i18n";

// What the parent has decided for one unclear answer. A short answer counts as decided when text
// was typed or "No answer" was chosen on purpose; an empty box alone is not a decision.

export type Choice = {
  selected?: string | null;
  text?: string;
  blank?: boolean;
  instructionMet?: boolean;
};

export const itemKey = (item: Pick<ReviewItem, "paper_item_id" | "part_no">) => `${item.paper_item_id}:${item.part_no}`;

export const isInstruction = (item: ReviewItem) => item.ask !== null;

export function isDecided(item: ReviewItem, choice: Choice | undefined): boolean {
  if (!choice) return false;
  if (isInstruction(item)) return choice.instructionMet !== undefined;
  if (item.part_type === "mcq") return choice.selected !== undefined;
  return choice.blank === true || (choice.text ?? "").trim() !== "";
}

export function isReadyToSubmit(items: ReviewItem[], choices: Record<string, Choice>): boolean {
  return items.length > 0 && items.every((item) => isDecided(item, choices[itemKey(item)]));
}

export function decidedCount(items: ReviewItem[], choices: Record<string, Choice>): number {
  return items.filter((item) => isDecided(item, choices[itemKey(item)])).length;
}

/** The request body for POST /submissions/{id}/confirm. */
export function buildDecisions(items: ReviewItem[], choices: Record<string, Choice>): Decision[] {
  return items.map((item) => {
    const choice = choices[itemKey(item)] ?? {};
    const base = { paper_item_id: item.paper_item_id, part_no: item.part_no };
    if (isInstruction(item)) return { ...base, instruction_met: choice.instructionMet ?? false };
    if (item.part_type === "mcq") return { ...base, selected: choice.selected ?? null };
    return { ...base, text: choice.blank ? "" : (choice.text ?? "").trim() };
  });
}

/** What the reader saw, in words. It never says whether that is right. */
export function readingText(item: ReviewItem): string | null {
  if (item.part_type === "mcq") return item.reading.selected ? item.reading.selected : null;
  const text = (item.reading.text ?? "").trim();
  return text === "" ? null : text;
}

// ---- one card per question --------------------------------------------------------------------

export type QuestionGroup = {
  paperItemId: string;
  position: number;
  partCount: number;
  items: ReviewItem[];
};

/** The unclear answers grouped by question (in printed order), and each question's parts in order. */
export function groupByQuestion(items: ReviewItem[]): QuestionGroup[] {
  const groups = new Map<string, QuestionGroup>();
  for (const item of items) {
    const group = groups.get(item.paper_item_id) ?? {
      paperItemId: item.paper_item_id,
      position: item.position,
      partCount: item.part_count,
      items: [],
    };
    group.items.push(item);
    groups.set(item.paper_item_id, group);
  }
  return [...groups.values()]
    .map((group) => ({
      ...group,
      items: [...group.items].sort((a, b) => a.part_no - b.part_no),
    }))
    .sort((a, b) => a.position - b.position);
}

/** "Answer 2 of 5", with the printed label first when the question has one. */
export function partTitle(item: ReviewItem): string {
  const label = item.label ? `(${item.label}) ` : "";
  return `${label}${t("review.partTitle", { n: item.part_no, total: item.part_count })}`;
}

/** Decisions made on purpose as "No answer". Saving these deserves one more look. */
export function blankCount(items: ReviewItem[], choices: Record<string, Choice>): number {
  return items.filter((item) => {
    const choice = choices[itemKey(item)];
    if (!choice || isInstruction(item)) return false;
    return item.part_type === "mcq" ? choice.selected === null : choice.blank === true;
  }).length;
}

/**
 * "No answer" on a text box. What was typed is kept, so tapping it by accident, or tapping it again,
 * brings the text back instead of losing it.
 */
export function toggleBlank(choice: Choice | undefined): Choice {
  const text = choice?.text ?? "";
  return choice?.blank ? { text } : { blank: true, text };
}
