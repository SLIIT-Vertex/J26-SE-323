import { useState } from "react";

import {
  type Availability,
  type Paper,
  createWeeklyPaper,
  friendlyMessage,
  getAvailability,
  listPapers,
  pdfUrl,
} from "../api";
import { dayLabel, paperStatusLabel, paperTitle, shortDate } from "../format";
import { useAsync } from "../hooks";
import { go, hrefFor } from "../router";
import { Chip, ErrorBox, Loading, ScreenHeader, type Tone } from "../ui";

export function statusTone(status: string): Tone {
  switch (status) {
    case "needs_review":
      return "rose";
    case "graded":
    case "confirmed":
      return "mint";
    case "partially_uploaded":
      return "sky";
    case "cancelled":
      return "plain";
    default:
      return "sun";
  }
}

export function PrintNote() {
  return (
    <p className="mb-fineprint">
      Print at <strong>Actual size (100%)</strong>. Keep all four black squares in the corners: do not crop, fold or
      staple over them.
    </p>
  );
}

function Countdown({ availability }: { availability: Availability }) {
  return (
    <section className="mb-hero mb-hero--wait" aria-labelledby="wait-title">
      <div className="mb-hero__arch">
        <span className="mb-hero__number">{availability.days_until_eligible}</span>
        <span className="mb-hero__unit">{availability.days_until_eligible === 1 ? "day" : "days"}</span>
      </div>
      <h2 id="wait-title" className="mb-h2">
        Your first paper is on its way
      </h2>
      <p>
        A few days of play first, so the paper fits your child. It opens on{" "}
        <strong>{dayLabel(availability.eligible_from)}</strong>.
      </p>
    </section>
  );
}

function MakePaper({ learnerId }: { learnerId: string }) {
  const [making, setMaking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function make() {
    setMaking(true);
    setError(null);
    try {
      const paper = await createWeeklyPaper(learnerId);
      go({ name: "paper", id: paper.paper_id });
    } catch (problem) {
      setError(friendlyMessage(problem));
      setMaking(false);
    }
  }

  return (
    <section className="mb-hero" aria-labelledby="make-title">
      <div className="mb-hero__arch mb-hero__arch--sun">
        <svg viewBox="0 0 40 40" aria-hidden="true" focusable="false">
          <circle cx="20" cy="22" r="8" />
          <path d="M20 4v6M7 9l4 4M33 9l-4 4" />
        </svg>
      </div>
      <h2 id="make-title" className="mb-h2">
        This week's paper is ready to make
      </h2>
      <p>It is chosen from what your child found easy and hard, in games and on paper.</p>
      {error ? <ErrorBox message={error} /> : null}
      <button type="button" className="mb-btn" onClick={make} disabled={making}>
        {making ? "Making your paper… a few seconds" : "Make this week's paper"}
      </button>
    </section>
  );
}

function ThisWeek({ paper }: { paper: Paper }) {
  return (
    <section className="mb-card mb-card--paper" aria-labelledby="week-title">
      <div className="mb-row">
        <Chip tone={statusTone(paper.status)}>{paperStatusLabel(paper.status)}</Chip>
        <span className="mb-code">Code {paper.code}</span>
      </div>
      <h2 id="week-title" className="mb-h2">
        {paperTitle(paper.mode)}
      </h2>
      <p className="mb-muted">
        Week of {dayLabel(paper.week_start)} · {paper.question_count} questions · about{" "}
        {Math.round(paper.estimated_minutes)} min · {paper.page_count} {paper.page_count === 1 ? "page" : "pages"}
      </p>
      <div className="mb-actions">
        <a className="mb-btn mb-btn--sun" href={pdfUrl(paper)} target="_blank" rel="noreferrer">
          Open PDF to print
        </a>
        <a className="mb-btn" href={hrefFor({ name: "paper", id: paper.paper_id })}>
          Upload photos
        </a>
      </div>
      <PrintNote />
    </section>
  );
}

function EarlierPapers({ papers }: { papers: Paper[] }) {
  if (papers.length === 0) return null;
  return (
    <section aria-labelledby="earlier-title">
      <h2 id="earlier-title" className="mb-h2 mb-h2--spaced">
        Earlier papers
      </h2>
      <ul className="mb-list">
        {papers.map((paper) => (
          <li key={paper.paper_id}>
            <a className="mb-paper-row" href={hrefFor({ name: "paper", id: paper.paper_id })}>
              <span className="mb-paper-row__date">
                <strong>{shortDate(paper.week_start)}</strong>
                <small>{paper.question_count} questions</small>
              </span>
              <span className="mb-paper-row__title">{paperTitle(paper.mode)}</span>
              <Chip tone={statusTone(paper.status)}>{paperStatusLabel(paper.status)}</Chip>
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function PapersHome({ learnerId }: { learnerId: string }) {
  const availability = useAsync(() => getAvailability(learnerId), `availability:${learnerId}`);
  const list = useAsync(() => listPapers(learnerId), `papers:${learnerId}`);

  const current = availability.state.status === "ready" ? availability.state.data : null;
  const earlier =
    list.state.status === "ready"
      ? list.state.data.filter((paper) => paper.paper_id !== current?.paper?.paper_id)
      : [];

  return (
    <>
      <ScreenHeader
        title="Weekly paper"
        kicker={current ? `Week of ${dayLabel(current.week_start)}` : "This week"}
      />
      <div className="mb-body-pad">
        {availability.state.status === "loading" ? <Loading label="Checking this week" /> : null}
        {availability.state.status === "error" ? (
          <ErrorBox message={availability.state.message} onRetry={availability.reload} />
        ) : null}

        {current?.state === "not_yet_eligible" ? <Countdown availability={current} /> : null}
        {current?.state === "available" && current.can_generate ? <MakePaper learnerId={learnerId} /> : null}
        {current?.state === "generated" && current.paper ? <ThisWeek paper={current.paper} /> : null}
        {current && current.state !== "not_yet_eligible" ? (
          <p className="mb-fineprint">Next paper: {dayLabel(current.next_paper_date)}</p>
        ) : null}

        {list.state.status === "error" ? <ErrorBox message={list.state.message} onRetry={list.reload} /> : null}
        <EarlierPapers papers={earlier} />
      </div>
    </>
  );
}
