import { useRef, useState } from "react";

import {
  anyPageChecking,
  describeFailure,
  friendlyMessage,
  getPaper,
  getSubmission,
  type PagePhoto,
  type PageState,
  type Paper,
  pageState,
  pdfUrl,
  uploadPagePhoto,
} from "../api";
import { dayLabel, pageCount, paperStatusLabel, paperTitle, questionCount } from "../format";
import { useAsync, useInterval } from "../hooks";
import { type MessageKey, t, useLanguage } from "../i18n";
import { hrefFor } from "../router";
import { Chip, ErrorBox, Loading, PageGuide, ScreenHeader, Tick, type Tone } from "../ui";
import { PrintNote, statusTone } from "./PapersHome";

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

  const canPhotograph =
    (state === "empty" || state === "retake" || state === "problem") && paper.status !== "cancelled";
  const reason =
    why.state.status === "ready" && why.state.data
      ? describeFailure(why.state.data.failure_reason, why.state.data.message)
      : null;

  return (
    <li className={`mb-page mb-page--${state}`}>
      <div className="mb-row">
        <h3 className="mb-h3">{t("page.pageOf", { page: page.page, total: paper.page_count })}</h3>
        <Chip tone={STATE_TONE[state]} icon={state === "done" ? <Tick className="mb-chip__tick" /> : undefined}>
          {t(`page.state.${state}` as MessageKey)}
        </Chip>
      </div>

      {state === "checking" ? <Loading label={t("page.checking")} /> : null}
      {state === "retake" ? <p>{reason ?? t("page.retakeDefault")}</p> : null}
      {state === "review" ? <p>{t("page.reviewText")}</p> : null}
      {state === "done" ? <p className="mb-muted">{t("page.doneText")}</p> : null}
      {state === "problem" ? <p>{t("page.problemText")}</p> : null}
      {error ? <ErrorBox message={error} /> : null}

      {state === "review" && page.submission_id ? (
        <a className="mb-btn" href={hrefFor({ name: "review", id: page.submission_id })}>
          {t("page.reviewButton")}
        </a>
      ) : null}

      {canPhotograph ? (
        <div className="mb-actions">
          <button type="button" className="mb-btn" disabled={sending} onClick={() => camera.current?.click()}>
            {sending ? t("page.sending") : state === "empty" ? t("page.take") : t("page.retake")}
          </button>
          <button
            type="button"
            className="mb-btn mb-btn--ghost"
            disabled={sending}
            onClick={() => gallery.current?.click()}
          >
            {t("page.choose")}
          </button>
          <input
            ref={camera}
            className="mb-hidden"
            type="file"
            accept="image/*"
            capture="environment"
            tabIndex={-1}
            aria-label={t("page.takeAria", { n: page.page })}
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
            aria-label={t("page.chooseAria", { n: page.page })}
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
  useLanguage();
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
        title={paper ? paperTitle(paper.mode) : t("detail.fallbackTitle")}
        kicker={paper ? t("home.weekOf", { date: dayLabel(paper.week_start) }) : undefined}
        back={{
          href: hrefFor({ name: "papers" }),
          label: t("common.practice"),
        }}
      />
      <div className="mb-body-pad">
        {state.status === "loading" ? <Loading label={t("detail.opening")} /> : null}
        {state.status === "error" ? <ErrorBox message={state.message} onRetry={reload} /> : null}

        {paper ? (
          <>
            <section className="mb-card mb-card--paper" aria-labelledby="print-title">
              <div className="mb-row">
                <Chip tone={statusTone(paper.status)}>{paperStatusLabel(paper.status)}</Chip>
                <span className="mb-code">{t("detail.code", { code: paper.code })}</span>
              </div>
              <h2 id="print-title" className="mb-h2">
                {t("detail.printIt")}
              </h2>
              <p className="mb-muted">
                {t("detail.details", {
                  questions: questionCount(paper.question_count),
                  minutes: Math.round(paper.estimated_minutes),
                  pages: pageCount(paper.page_count),
                })}
              </p>
              <a className="mb-btn mb-btn--sun" href={pdfUrl(paper)} target="_blank" rel="noreferrer">
                {t("home.openPdf")}
              </a>
              <PrintNote />
            </section>

            <section aria-labelledby="photos-title">
              <h2 id="photos-title" className="mb-h2 mb-h2--spaced">
                {t("detail.photograph")}
              </h2>
              <details className="mb-guide-box">
                <summary>{t("detail.guide.title")}</summary>
                <div className="mb-guide-box__body">
                  <PageGuide />
                  <ul>
                    <li>{t("detail.guide.1")}</li>
                    <li>{t("detail.guide.2")}</li>
                    <li>{t("detail.guide.3")}</li>
                    <li>{t("detail.guide.4")}</li>
                  </ul>
                </div>
              </details>
              {paper.status === "cancelled" ? (
                <div className="mb-note">{t("detail.cancelled")}</div>
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
                {t("detail.seeResults")}
              </a>
            ) : null}
          </>
        ) : null}
      </div>
    </>
  );
}
