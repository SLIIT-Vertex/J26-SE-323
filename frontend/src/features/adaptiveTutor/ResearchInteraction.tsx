import { type FormEvent, type KeyboardEvent, useEffect, useRef, useState } from "react";

import {
  type ResearchAnnotation,
  type ResearchInteraction as Interaction,
  type ResearchSession,
  type ResearchTutorApi,
  researchTutorApi,
} from "./api";
import { ResearchDiagnostics } from "./ResearchDiagnostics";

const configuredLearnerId = import.meta.env.VITE_MOBILE_LEARNING_LEARNER_ID ?? "";
const STARTERS = [
  "Why is 1/2 equal to 2/4?",
  "How do I compare 3/4 and 2/3?",
  "What does the bottom number in a fraction mean?",
];
const LANGUAGES = [
  { value: "en", label: "English" },
  { value: "si", label: "සිංහල" },
  { value: "ta", label: "தமிழ்" },
];
const MAX_INPUT_HEIGHT = 160;

type Turn = {
  id: string;
  kind: "question" | "review";
  question?: string;
  language: string;
  state: "pending" | "done" | "failed";
  result?: Interaction;
  error?: string;
};

function message(reason: unknown, fallback: string): string {
  return reason instanceof Error ? reason.message : fallback;
}

function MindyAvatar() {
  return (
    <span className="mindy-avatar" aria-hidden="true">
      <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M12 2l2.2 6.3L20.5 10l-6.3 2.2L12 18.5l-2.2-6.3L3.5 10l6.3-1.7z" /></svg>
    </span>
  );
}

export function ResearchInteraction({
  api = researchTutorApi,
  standalone = false,
}: {
  api?: ResearchTutorApi;
  standalone?: boolean;
}) {
  const [authorized, setAuthorized] = useState(false);
  const [session, setSession] = useState<ResearchSession | null>(null);
  const [starting, setStarting] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState("");
  const [language, setLanguage] = useState("en");
  const [error, setError] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const pending = turns.some((turn) => turn.state === "pending");
  const busy = starting || pending;
  const ready = authorized && Boolean(session) && !busy;
  const latestDone = [...turns].reverse().find((turn) => turn.state === "done" && turn.result);

  useEffect(() => {
    let active = true;
    api.authorize().then(
      () => active && setAuthorized(true),
      (reason: unknown) => active && setError(message(reason, "Researcher authorization failed.")),
    );
    return () => { active = false; };
  }, [api]);

  useEffect(() => {
    if (!authorized || session || !configuredLearnerId) return;
    let active = true;
    setStarting(true);
    setError("");
    api.start(configuredLearnerId).then(
      (created) => {
        if (!active) return;
        setSession(created);
        setStarting(false);
      },
      (reason: unknown) => {
        if (!active) return;
        setError(message(reason, "The research session could not start."));
        setStarting(false);
      },
    );
    return () => { active = false; };
  }, [api, authorized, session]);

  useEffect(() => {
    const scroller = scrollRef.current;
    if (scroller && turns.length) scroller.scrollTop = scroller.scrollHeight;
  }, [turns]);

  useEffect(() => {
    const input = inputRef.current;
    if (!input) return;
    input.style.height = "auto";
    if (question) input.style.height = `${Math.min(input.scrollHeight, MAX_INPUT_HEIGHT)}px`;
  }, [question]);

  function settle(id: string, update: Partial<Turn>) {
    setTurns((current) => current.map((turn) => (turn.id === id ? { ...turn, ...update } : turn)));
  }

  async function run(turn: Turn, call: () => Promise<Interaction>) {
    setError("");
    try {
      settle(turn.id, { state: "done", result: await call() });
    } catch (reason) {
      settle(turn.id, { state: "failed", error: message(reason, "Mindy could not be reached.") });
    }
  }

  async function ask(text: string, existing?: Turn) {
    if (!session || !text) return;
    const turn: Turn = existing
      ? { ...existing, state: "pending", error: undefined }
      : { id: crypto.randomUUID(), kind: "question", question: text, language, state: "pending" };
    setTurns((current) => (existing ? current.map((item) => (item.id === turn.id ? turn : item)) : [...current, turn]));
    await run(turn, () => api.ask(session, text, turn.language));
  }

  async function recordAttempt(target: Turn, annotation: ResearchAnnotation) {
    const interaction = target.result;
    if (!session || !interaction || busy) return;
    const turn: Turn = { id: crypto.randomUUID(), kind: "review", language: target.language, state: "pending" };
    setTurns((current) => [...current, turn]);
    await run(turn, () => api.attempt(session, interaction.interaction_id, annotation));
  }

  function submitQuestion(event: FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (!ready || !text) return;
    setQuestion("");
    void ask(text);
  }

  function submitOnEnter(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  async function newChat() {
    const current = session;
    setSession(null);
    setTurns([]);
    setQuestion("");
    setError("");
    if (current) await api.end(current).catch(() => undefined);
  }

  const status = error && !authorized
    ? "Not available"
    : !authorized
      ? "Connecting…"
      : starting
        ? "Starting a session…"
        : session
          ? "Maths helper"
          : "No active session";

  return (
    <section className="mindy-chat" aria-labelledby="mindy-title">
      <header className="mindy-topbar">
        {standalone ? (
          <a className="mindy-icon-button" href="#/" title="Back to MindBridge">
            <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" d="M15 18l-6-6 6-6" /></svg>
            <span className="sr-only">Back to MindBridge</span>
          </a>
        ) : null}
        <MindyAvatar />
        <div className="mindy-topbar-copy">
          <h1 id="mindy-title">Mindy</h1>
          <p role="status">{status}</p>
        </div>
        <button type="button" className="mindy-icon-button" onClick={() => void newChat()} disabled={busy || !authorized} title="New chat">
          <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" d="M12 20h9M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z" /></svg>
          <span className="sr-only">New chat</span>
        </button>
      </header>

      <div ref={scrollRef} className="mindy-scroll" role="log" aria-live="polite" aria-label="Conversation with Mindy">
        <div className="mindy-thread">
          {error ? <p role="alert" className="mindy-banner">{error}</p> : null}
          {authorized && !configuredLearnerId ? (
            <p role="alert" className="mindy-banner">
              VITE_MOBILE_LEARNING_LEARNER_ID is required to start the local research session.
            </p>
          ) : null}

          {turns.length === 0 ? (
            <div className="mindy-empty">
              <MindyAvatar />
              <h2>Hi! I'm Mindy.</h2>
              <p>Ask me about fractions and I'll help you think it through.</p>
              <div className="starter-list">
                {STARTERS.map((starter) => (
                  <button
                    key={starter}
                    type="button"
                    className="starter-chip"
                    onClick={() => {
                      setQuestion(starter);
                      inputRef.current?.focus();
                    }}
                    disabled={!ready}
                  >
                    {starter}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {turns.map((turn) => (
            <div key={turn.id} className="mindy-turn" lang={turn.language}>
              {turn.kind === "question" ? (
                <p className="student-message">{turn.question}</p>
              ) : (
                <p className="turn-divider">Researcher recorded an attempt review</p>
              )}
              <TutorReply
                turn={turn}
                annotatable={turn === latestDone && Boolean(turn.result?.confirmed_skill_id)}
                busy={busy}
                onRetry={turn.kind === "question" && turn.question && ready ? () => void ask(turn.question ?? "", turn) : undefined}
                onAttempt={(annotation) => void recordAttempt(turn, annotation)}
              />
            </div>
          ))}
        </div>
      </div>

      <footer className="mindy-footer">
        <form className="mindy-composer" onSubmit={submitQuestion}>
          <label className="sr-only" htmlFor="mindy-question">Your question</label>
          <textarea
            id="mindy-question"
            ref={inputRef}
            className="mindy-input"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            onKeyDown={submitOnEnter}
            placeholder={ready || pending ? "Ask Mindy a question…" : "Please wait…"}
            rows={1}
            maxLength={4000}
            disabled={!authorized || !session || starting}
          />
          <div className="mindy-composer-bar">
            <label className="sr-only" htmlFor="mindy-language">Answer language</label>
            <select id="mindy-language" className="mindy-language" value={language} onChange={(event) => setLanguage(event.target.value)} disabled={busy || !authorized}>
              {LANGUAGES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
            <button className="mindy-send" type="submit" disabled={!ready || !question.trim()} aria-label={pending ? "Sending" : "Send"}>
              <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" d="M12 19V5M5 12l7-7 7 7" /></svg>
            </button>
          </div>
        </form>
        <p className="mindy-disclaimer">Research session · Learners only see answers that pass verification.</p>
      </footer>
    </section>
  );
}

function TutorReply({
  turn,
  annotatable,
  busy,
  onRetry,
  onAttempt,
}: {
  turn: Turn;
  annotatable: boolean;
  busy: boolean;
  onRetry?: () => void;
  onAttempt: (annotation: ResearchAnnotation) => void;
}) {
  if (turn.state === "pending") {
    return (
      <div className="mindy-reply">
        <MindyAvatar />
        <p className="mindy-typing" role="status">
          <span className="typing-dots" aria-hidden="true"><i /><i /><i /></span>
          <span className="sr-only">Mindy is thinking…</span>
        </p>
      </div>
    );
  }
  if (turn.state === "failed") {
    return (
      <div className="mindy-reply">
        <MindyAvatar />
        <div className="mindy-reply-body mindy-reply-error" role="alert">
          <p>Mindy couldn't answer right now. {turn.error}</p>
          {onRetry ? <button type="button" className="mindy-link" onClick={onRetry}>Try again</button> : null}
        </div>
      </div>
    );
  }

  const result = turn.result;
  if (!result) return null;
  const answer = result.delivery_authorized ? result.response_text : undefined;
  const draft = answer ? undefined : result.experimental_response_text;
  const usesSynthetic = (result.context_provenance ?? []).some((item) => item.origin !== "REAL");
  const summary = [
    result.assistance_level ?? "No level",
    result.delivery_authorized ? "Delivered" : "Not delivered",
    result.experimental_response_text ? "Draft ready" : result.experimental_generation_status ? "No draft" : null,
  ].filter(Boolean).join(" · ");

  return (
    <div className="mindy-reply">
      <MindyAvatar />
      <div className="mindy-reply-body">
        {answer ? (
          <article className="mindy-answer" aria-label="Mindy's checked answer">
            <p>{answer}</p>
            <span className="status-chip status-chip--ok">Checked answer</span>
          </article>
        ) : draft ? (
          <article className="mindy-answer mindy-answer--unverified" aria-label="Mindy's unverified draft">
            <p>{draft}</p>
            <span className="status-chip status-chip--unverified" title={result.experimental_notice}>
              Not verified
            </span>
          </article>
        ) : (
          <p className="mindy-held">
            No answer to share yet — this reply hasn't been checked for learners.
          </p>
        )}

        <details className="research-details">
          <summary>
            <svg className="research-chevron" viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" d="M9 6l6 6-6 6" /></svg>
            <span>Researcher</span>
            <span className="research-summary-meta">{summary}</span>
            {usesSynthetic ? <span className="research-summary-flag">Synthetic data</span> : null}
          </summary>
          <div className="research-details-body">
            <ResearchDiagnostics result={result} />
            {annotatable ? (
              <details className="research-subsection">
                <summary>Record reviewed attempt</summary>
                <AttemptForm sequence={result.interaction_sequence} busy={busy} onSubmit={onAttempt} />
              </details>
            ) : null}
          </div>
        </details>
      </div>
    </div>
  );
}

function AttemptForm({
  sequence,
  busy,
  onSubmit,
}: {
  sequence: number;
  busy: boolean;
  onSubmit: (annotation: ResearchAnnotation) => void;
}) {
  const [correct, setCorrect] = useState(false);
  const [severity, setSeverity] = useState("0.7");
  const [policy, setPolicy] = useState("");
  const [reviewed, setReviewed] = useState(false);

  function submit(event: FormEvent) {
    event.preventDefault();
    onSubmit({
      idempotency_key: crypto.randomUUID(),
      is_correct: correct,
      partial_credit: null,
      severity_category: correct ? "CORRECT" : "RESEARCHER_ANNOTATED_ERROR",
      severity_value: correct ? 0 : Number(severity),
      severity_policy_version: policy,
      scoring_version: "researcher-review-v1",
      item_rubric_version: "researcher-supplied-v1",
      reviewer_confirmed: reviewed,
    });
    setReviewed(false);
  }

  return (
    <form className="attempt-form" onSubmit={submit} aria-label="Record researcher-reviewed attempt">
      <p className="quiet">Controlled research annotation for turn {sequence}. It is not an approved learner assessment.</p>
      <label className="attempt-check"><input type="checkbox" checked={correct} onChange={(event) => setCorrect(event.target.checked)} /> Answer is correct</label>
      <label className="attempt-field"><span>Error severity</span><input type="number" min="0" max="1" step="0.05" value={correct ? "0" : severity} onChange={(event) => setSeverity(event.target.value)} disabled={correct} /></label>
      <label className="attempt-field"><span>Severity policy version</span><input value={policy} onChange={(event) => setPolicy(event.target.value)} required /></label>
      <label className="attempt-check"><input type="checkbox" checked={reviewed} onChange={(event) => setReviewed(event.target.checked)} required /> I am a qualified researcher and reviewed this annotation</label>
      <button className="attempt-submit" type="submit" disabled={busy || !reviewed || !policy}>Record attempt and rerun Controller</button>
    </form>
  );
}
