import { useRef, useState } from "react";

import {
  type PagePhoto,
  type PageState,
  type Paper,
  anyPageChecking,
  describeFailure,
  friendlyMessage,
  getPaper,
  getSubmission,
  pageState,
  pdfUrl,
  uploadPagePhoto,
} from "../api";
import { dayLabel, paperStatusLabel, paperTitle } from "../format";
import { useAsync, useInterval } from "../hooks";
import { hrefFor } from "../router";
import { Chip, ErrorBox, Loading, PageGuide, ScreenHeader, Tick, type Tone } from "../ui";
import { PrintNote, statusTone } from "./PapersHome";

const STATE_LABEL: Record<PageState, string> = {
  empty: "No photo yet",
  checking: "Checking…",
  retake: "Retake needed",
  review: "Needs you",
  done: "Marked",
  problem: "Try again",
};

const STATE_TONE: Record<PageState, Tone> = {
  empty: "plain",
  checking: "sun",
  retake: "rose",
  review: "rose",
  done: "mint",
  problem: "rose",
};

function PageCard({ paper, page, onChanged }: { paper: Paper; page: PagePhoto; onChanged: () => void }) {
  const state = pageState(page.submission_status);
  const camera = useRef<HTMLInputElement>(null);
  const gallery = useRef<HTMLInputElement>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Why the last photo could not be used (only asked for when a retake is needed)
  const why = useAsync(
    async () => (state === "retake" && page.submission_id ? await getSubmission(page.submission_id) : null),
    `why:${page.submission_id}:${state}`,
  );

  async function send(file: File | undefined) {
    if (!file) return;
    setSending(true);
    setError(null);
    try {
      await uploadPagePhoto(paper.paper_id, page.page, file);
      onChanged();
    } catch (problem) {
      setError(friendlyMessage(problem));
    } finally {
      setSending(false);
    }
  }

  const canPhotograph = (state === "empty" || state === "retake" || state === "problem") && paper.status !== "cancelled";
  const reason =
    why.state.status === "ready" && why.state.data
      ? describeFailure(why.state.data.failure_reason, why.state.data.message)
      : null;

  return (
    <li className={`mb-page mb-page--${state}`}>
      <div className="mb-row">
        <h3 className="mb-h3">
          Page {page.page} <span className="mb-muted">of {paper.page_count}</span>
        </h3>
        <Chip
          tone={STATE_TONE[state]}
          icon={state === "done" ? <Tick className="mb-chip__tick" /> : undefined}
        >
          {STATE_LABEL[state]}
        </Chip>
      </div>

      {state === "checking" ? (
        <Loading label="Straightening and reading your photo" />
      ) : null}
      {state === "retake" ? <p>{reason ?? "We could not use this photo. Please retake it."}</p> : null}
      {state === "review" ? (
        <p>A few answers were hard to read. Tell us what was written, and this page is done.</p>
      ) : null}
      {state === "done" ? <p className="mb-muted">This page has been marked.</p> : null}
      {state === "problem" ? <p>Something went wrong with this photo. Please take it again.</p> : null}
      {error ? <ErrorBox message={error} /> : null}

      {state === "review" && page.submission_id ? (
        <a className="mb-btn" href={hrefFor({ name: "review", id: page.submission_id })}>
          Review unclear answers
        </a>
      ) : null}

      {canPhotograph ? (
        <div className="mb-actions">
          <button type="button" className="mb-btn" disabled={sending} onClick={() => camera.current?.click()}>
            {sending ? "Sending…" : state === "empty" ? "Take photo" : "Retake photo"}
          </button>
          <button
            type="button"
            className="mb-btn mb-btn--ghost"
            disabled={sending}
            onClick={() => gallery.current?.click()}
          >
            Choose photo
          </button>
          <input
            ref={camera}
            className="mb-hidden"
            type="file"
            accept="image/*"
            capture="environment"
            tabIndex={-1}
            aria-label={`Take a photo of page ${page.page}`}
            onChange={(event) => {
              void send(event.target.files?.[0]);
              event.target.value = "";
            }}
          />
          <input
            ref={gallery}
            className="mb-hidden"
            type="file"
            accept="image/*"
            tabIndex={-1}
            aria-label={`Choose a photo of page ${page.page}`}
            onChange={(event) => {
              void send(event.target.files?.[0]);
              event.target.value = "";
            }}
          />
        </div>
      ) : null}
    </li>
  );
}

export function PaperDetail({ paperId }: { paperId: string }) {
  const { state, reload } = useAsync(() => getPaper(paperId), `paper:${paperId}`);
  const paper = state.status === "ready" ? state.data : null;
  useInterval(reload, anyPageChecking(paper?.pages) ? 2000 : null);

  const pages = paper?.pages ?? [];
  const anyMarked = pages.some((p) => {
    const s = pageState(p.submission_status);
    return s === "done" || s === "review";
  });

  return (
    <>
      <ScreenHeader
        title={paper ? paperTitle(paper.mode) : "Paper"}
        kicker={paper ? `Week of ${dayLabel(paper.week_start)}` : undefined}
        back={{ href: hrefFor({ name: "papers" }), label: "Papers" }}
      />
      <div className="mb-body-pad">
        {state.status === "loading" ? <Loading label="Opening the paper" /> : null}
        {state.status === "error" ? <ErrorBox message={state.message} onRetry={reload} /> : null}

        {paper ? (
          <>
            <section className="mb-card mb-card--paper" aria-labelledby="print-title">
              <div className="mb-row">
                <Chip tone={statusTone(paper.status)}>{paperStatusLabel(paper.status)}</Chip>
                <span className="mb-code">Code {paper.code}</span>
              </div>
              <h2 id="print-title" className="mb-h2">
                1 · Print it
              </h2>
              <p className="mb-muted">
                {paper.question_count} questions · about {Math.round(paper.estimated_minutes)} min ·{" "}
                {paper.page_count} {paper.page_count === 1 ? "page" : "pages"}
              </p>
              <a className="mb-btn mb-btn--sun" href={pdfUrl(paper)} target="_blank" rel="noreferrer">
                Open PDF to print
              </a>
              <PrintNote />
            </section>

            <section aria-labelledby="photos-title">
              <h2 id="photos-title" className="mb-h2 mb-h2--spaced">
                2 · Photograph each page
              </h2>
              <details className="mb-guide-box">
                <summary>How to take a good photo</summary>
                <div className="mb-guide-box__body">
                  <PageGuide />
                  <ul>
                    <li>Place the page flat.</li>
                    <li>All four black squares must be inside the picture.</li>
                    <li>Good light, with no shadow across the page.</li>
                    <li>Hold the phone straight above the page.</li>
                  </ul>
                </div>
              </details>
              {paper.status === "cancelled" ? (
                <div className="mb-note">This paper was cancelled.</div>
              ) : (
                <ol className="mb-bridge">
                  {pages.map((page) => (
                    <PageCard key={page.page} paper={paper} page={page} onChanged={reload} />
                  ))}
                </ol>
              )}
            </section>

            {anyMarked ? (
              <a className="mb-btn mb-btn--sun mb-btn--wide" href={hrefFor({ name: "report", id: paper.paper_id })}>
                See the results
              </a>
            ) : null}
          </>
        ) : null}
      </div>
    </>
  );
}
