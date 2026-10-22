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

/** What a non-real evidence source actually is, keyed by the backend's stable `source_id`. */
const RESEARCH_EVIDENCE: Record<string, { badge: string; meaning: string }> = {
  "adaptive-tutor:experimental-cold-start-mastery-default": {
    badge: "Cold-start default",
    meaning: "a fixed placeholder used because knowledge tracing had no estimate; not measured",
  },
  "adaptive-tutor:experimental-missing-support-need-default": {
    badge: "Cold-start default",
    meaning: "a fixed placeholder used because no learner-state reading existed; not measured",
  },
  "adaptive-tutor:assessment-ledger-controlled": {
    badge: "Researcher-entered",
    meaning:
      "attempt outcomes entered in the researcher panel or by a scripted test scenario; not observed from a student",
  },
  "adaptive-tutor:interaction-history-research-presentation": {
    badge: "Derived (research)",
    meaning:
      "built from drafts shown to the researcher and the entered attempt outcomes; nothing was delivered to a learner",
  },
};

export type EvidenceKind = { badge: string; meaning: string; real: boolean };

/** Classify one provenance entry; unknown non-real sources are reported as such, never guessed. */
export function describeEvidence(item: { source_id: string; origin: string }): EvidenceKind {
  if (item.origin === "REAL") return { badge: "Real", meaning: "", real: true };
  const known = RESEARCH_EVIDENCE[item.source_id];
  return known
    ? { ...known, real: false }
    : { badge: "Synthetic", meaning: `synthetic or test data (source ${item.source_id})`, real: false };
}

export const GEMINI_PROVIDER = "google-gemini";
export const REHEARSAL_PROVIDER = "fake-rehearsal-not-gemini";

/** Only the Gemini adapter is ever called Gemini; anything else says it is not. */
export function describeDraftProvider(name: string | undefined): string {
  if (!name) return "Unknown provider";
  if (name === GEMINI_PROVIDER) return "Google Gemini API";
  if (name === REHEARSAL_PROVIDER) return "Fake rehearsal provider — not Gemini output";
  return `${name} — not Gemini output`;
}
