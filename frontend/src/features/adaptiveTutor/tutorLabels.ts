/** Display names for Controller V1 assistance levels; the Controller remains the authority. */
export const ASSISTANCE_LEVELS: Record<string, string> = {
  L0: "Independent retry",
  L1: "Metacognitive prompt",
  L2: "Conceptual hint",
  L3: "Targeted hint",
  L4: "Guided steps",
  L5: "Analogous worked example",
  L6: "Full explanation",
};

export function describeLevel(level: string | undefined): string {
  if (!level) return "Not selected";
  return ASSISTANCE_LEVELS[level] ? `${level} — ${ASSISTANCE_LEVELS[level]}` : level;
}
