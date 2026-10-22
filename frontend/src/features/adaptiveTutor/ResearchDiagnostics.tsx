import type { ReactNode } from "react";

import type { ResearchInteraction as Interaction } from "./api";
import { ASSISTANCE_LEVELS, describeDraftProvider, describeEvidence, describeLevel } from "./tutorLabels";

type Tone = "ok" | "warn" | "muted";

const INPUT_NAMES: Record<string, string> = {
  SKILL_MAPPING: "Skill mapping",
  LEARNER: "Learner profile",
  MASTERY: "Mastery (knowledge tracing)",
  SUPPORT_NEED: "Support need (learner state)",
  ASSESSMENT: "Assessment evidence",
  ASSISTANCE_HISTORY: "Help history",
};

/** "PRE_INTERACTION" → "Pre interaction"; the raw code stays available in Technical details. */
export function humanize(code: string | undefined, fallback = "Not reached"): string {
  if (!code) return fallback;
  const words = code.toLowerCase().replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function codes(values: string[] | undefined, empty = "None"): string {
  return values?.length ? values.join(", ") : empty;
}

function Tile({ label, value, note, tone }: { label: string; value: string; note: string; tone: Tone }) {
  return (
    <div className={`glance-tile glance-tile--${tone}`}>
      <dt>{label}</dt>
      <dd>
        <strong className="glance-value">{value}</strong>
        <span className="glance-note">{note}</span>
      </dd>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="research-section" aria-label={title}>
      <h4>{title}</h4>
      {children}
    </section>
  );
}

/** Researcher-only explanation of one Tutor turn, built only from what the API reported. */
export function ResearchDiagnostics({ result }: { result: Interaction }) {
  const provenance = result.context_provenance ?? [];
  const synthetic = provenance.filter((item) => item.origin !== "REAL");
  const matched = result.skill_mapping_status === "MATCHED";
  const draftGenerated = Boolean(result.experimental_response_text);

  return (
    <div className="research-diagnostics">
      <dl className="glance-grid" aria-label="At a glance">
        <Tile
          label="Skill"
          value={result.confirmed_skill_id ?? "Not confirmed"}
          note={humanize(result.skill_mapping_status)}
          tone={matched ? "ok" : "warn"}
        />
        <Tile
          label="Help level"
          value={result.assistance_level ?? "—"}
          note={result.assistance_level ? (ASSISTANCE_LEVELS[result.assistance_level] ?? "") : "Not selected"}
          tone={result.assistance_level ? "ok" : "muted"}
        />
        <Tile
          label="Learner delivery"
          value={result.delivery_authorized ? "Allowed" : "Blocked"}
          note={humanize(result.status)}
          tone={result.delivery_authorized ? "ok" : "warn"}
        />
        <Tile
          label="AI draft"
          value={draftGenerated ? "Generated" : result.experimental_generation_status ? "Not generated" : "Not run"}
          note={
            draftGenerated
              ? "Unverified"
              : humanize(result.experimental_provider_reason_code ?? result.experimental_generation_status, "—")
          }
          tone={draftGenerated ? "warn" : "muted"}
        />
      </dl>

      {synthetic.length ? (
        <div className="synthetic-flag" role="note">
          <p>This turn used evidence that is not real student data:</p>
          <ul>
            {synthetic.map((item) => (
              <li key={`${item.input}:${item.source_id}`}>
                <strong>{INPUT_NAMES[item.input] ?? humanize(item.input)}</strong>
                {` (${describeEvidence(item).badge.toLowerCase()}): ${describeEvidence(item).meaning}.`}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <Section title="Why this level">
        {result.controller_reason_codes.length ? (
          <ul className="reason-chips">
            {result.controller_reason_codes.map((code) => (
              <li key={code} title={code}>{humanize(code)}</li>
            ))}
          </ul>
        ) : (
          <p className="quiet">The Controller was not reached.</p>
        )}
      </Section>

      <Section title="Evidence used">
        {provenance.length ? (
          <ul className="evidence-list">
            {provenance.map((item) => (
              <li key={`${item.input}:${item.source_id}`} data-origin={item.origin}>
                <span className="evidence-name">{INPUT_NAMES[item.input] ?? humanize(item.input)}</span>
                <span className={`origin-badge origin-badge--${item.origin === "REAL" ? "real" : "synthetic"}`}>
                  {describeEvidence(item).badge}
                </span>
                <span className="evidence-status">{humanize(item.status)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="quiet">No evidence was reported.</p>
        )}
        {result.context_issue_codes.length ? (
          <p className="evidence-blocked">Blocked by: {result.context_issue_codes.map((code) => humanize(code)).join(", ")}</p>
        ) : null}
      </Section>

      <Section title="Checks">
        <dl className="check-list">
          <dt>Curriculum</dt>
          <dd>{humanize(result.curriculum_status)}</dd>
          <dt>Verification</dt>
          <dd>
            {humanize(result.verification_outcome, "Not run")}
            {result.verification_reason_codes.length
              ? ` — ${result.verification_reason_codes.map((code) => humanize(code)).join(", ")}`
              : ""}
          </dd>
          {draftGenerated ? (
            <>
              <dt>Draft source</dt>
              <dd className="draft-source">
                {describeDraftProvider(result.experimental_provider_name)} · {result.experimental_provenance} content
                <small>{result.experimental_notice}</small>
              </dd>
            </>
          ) : null}
        </dl>
      </Section>

      <details className="research-subsection">
        <summary>Technical details</summary>
        <dl className="evidence-grid">
          <dt>Workflow status</dt><dd>{result.status}</dd>
          <dt>Delivery authorized</dt><dd>{result.delivery_authorized ? "Yes" : "No — not authorized"}</dd>
          <dt>Assistance level</dt><dd>{describeLevel(result.assistance_level)}</dd>
          <dt>Controller reasons</dt><dd>{codes(result.controller_reason_codes, "Not reached")}</dd>
          <dt>Mapping status</dt><dd>{result.skill_mapping_status ?? "Not reached"}</dd>
          <dt>Context issues</dt><dd>{codes(result.context_issue_codes)}</dd>
          <dt>Evidence</dt>
          <dd>{provenance.map((item) => `${item.input}: ${item.origin}/${item.status}`).join("; ") || "None"}</dd>
          <dt>Execution origin</dt><dd>{result.execution_origin}</dd>
          <dt>Experimental status</dt><dd>{result.experimental_generation_status ?? "Not run"}</dd>
          <dt>Provider reason</dt><dd>{result.experimental_provider_reason_code ?? "None"}</dd>
          <dt>Provider</dt><dd>{result.experimental_provider_name ?? "None"}</dd>
          <dt>Content provenance</dt><dd>{result.experimental_provenance ?? "None"}</dd>
          <dt>Verified draft attempts</dt><dd>{result.draft_attempt_count}</dd>
          <dt>Regeneration reasons</dt><dd>{codes(result.regeneration_reason_codes)}</dd>
          <dt>Curriculum status</dt><dd>{result.curriculum_status ?? "Not reached"}</dd>
          <dt>Verification</dt><dd>{result.verification_outcome ?? "Not reached"} ({codes(result.verification_reason_codes)})</dd>
          <dt>Assessment mode</dt><dd>{result.assessment_mode}</dd>
          <dt>Safe message</dt><dd>{result.safe_message}</dd>
          <dt>Turn</dt><dd>{result.interaction_sequence}</dd>
          <dt>Session</dt><dd><code>{result.session_id}</code></dd>
          <dt>Interaction</dt><dd><code>{result.interaction_id}</code></dd>
        </dl>
        {result.verification_evidence_provenance.length ? (
          <ul className="diagnostics-references" aria-label="Curriculum references">
            {result.verification_evidence_provenance.map((reference) => (
              <li key={`${reference.source_id}:${reference.chunk_id}`}>
                {reference.source_id} ({reference.source_version}), {reference.chunk_id}
                {reference.page_number ? `, page ${reference.page_number}` : ""}
              </li>
            ))}
          </ul>
        ) : null}
      </details>
    </div>
  );
}
