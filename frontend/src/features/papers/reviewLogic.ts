import type { Decision, ReviewItem } from "./api";

// What the parent has decided for one unclear answer. A short answer counts as decided when text
// was typed or "No answer" was chosen on purpose; an empty box alone is not a decision.

export type Choice = {
  selected?: string | null;
  text?: string;
  blank?: boolean;
  instructionMet?: boolean;
};

export const itemKey = (item: Pick<ReviewItem, "paper_item_id" | "part_no">) =>
  `${item.paper_item_id}:${item.part_no}`;

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
