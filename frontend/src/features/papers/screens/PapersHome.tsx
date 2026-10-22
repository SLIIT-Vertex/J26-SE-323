import { useState } from "react";

import {
  type Availability,
  createWeeklyPaper,
  friendlyMessage,
  getAvailability,
  listPapers,
  type Paper,
  pdfUrl,
} from "../api";
import { dayLabel, pageCount, paperStatusLabel, paperTitle, questionCount, shortDate } from "../format";
import { useAsync } from "../hooks";
import { getLanguage, rich, t, useLanguage } from "../i18n";
import { go, hrefFor } from "../router";
import { Chip, ErrorBox, LinkCard, Loading, PaperIcon, ScreenHeader, type Tone } from "../ui";

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
  return <p className="mb-fineprint">{rich("print.note")}</p>;
}

function Countdown({ availability }: { availability: Availability }) {
  return (
    <section className="mb-hero mb-hero--wait" aria-labelledby="wait-title">
      <div className="mb-hero__arch">
        <span className="mb-hero__number">{availability.days_until_eligible}</span>
        <span className="mb-hero__unit">
          {t(availability.days_until_eligible === 1 ? "home.day.one" : "home.day.other")}
        </span>
      </div>
      <h2 id="wait-title" className="mb-h2">
        {t("home.wait.title")}
      </h2>
      <p>{rich("home.wait.body", { date: dayLabel(availability.eligible_from) })}</p>
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
      // the language chosen with the gear also chooses the printed paper (English: the child's own language)
      const chosen = getLanguage();
      const paper = await createWeeklyPaper(learnerId, chosen === "si" || chosen === "ta" ? chosen : undefined);
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
        {t("home.make.title")}
      </h2>
      <p>{t("home.make.body")}</p>
      {error ? <ErrorBox message={error} /> : null}
      <button type="button" className="mb-btn" onClick={make} disabled={making}>
        {making ? t("home.make.busy") : t("home.make.button")}
      </button>
    </section>
  );
}

function ThisWeek({ paper }: { paper: Paper }) {
  return (
    <section className="mb-card mb-card--paper" aria-labelledby="week-title">
      <div className="mb-row">
        <Chip tone={statusTone(paper.status)}>{paperStatusLabel(paper.status)}</Chip>
        <span className="mb-code">{t("detail.code", { code: paper.code })}</span>
      </div>
      <h2 id="week-title" className="mb-h2">
        {paperTitle(paper.mode)}
      </h2>
      <p className="mb-muted">
        {t("home.details", {
          date: dayLabel(paper.week_start),
          questions: questionCount(paper.question_count),
          minutes: Math.round(paper.estimated_minutes),
          pages: pageCount(paper.page_count),
        })}
      </p>
      <div className="mb-actions">
        <a className="mb-btn mb-btn--sun" href={pdfUrl(paper)} target="_blank" rel="noreferrer">
          {t("home.openPdf")}
        </a>
        <a className="mb-btn" href={hrefFor({ name: "paper", id: paper.paper_id })}>
          {t("home.uploadPhotos")}
        </a>
      </div>
      <PrintNote />
    </section>
  );
}

function EarlierPapers({ papers }: { papers: Paper[] }) {
  if (papers.length === 0) return null;
  const latest = papers.slice(0, 3);
  return (
    <section aria-labelledby="earlier-title">
      <h2 id="earlier-title" className="mb-h2 mb-h2--spaced">
        {t("home.earlier")}
      </h2>
      <ul className="mb-list">
        {latest.map((paper) => (
          <li key={paper.paper_id}>
            <a className="mb-paper-row" href={hrefFor({ name: "paper", id: paper.paper_id })}>
              <span className="mb-paper-row__date">
                <strong>{shortDate(paper.week_start)}</strong>
                <small>{questionCount(paper.question_count)}</small>
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

/** Where else the practice area goes: buttons, not another tab bar. */
function MoreLinks() {
  return (
    <section aria-labelledby="more-title">
      <h2 id="more-title" className="mb-h2 mb-h2--spaced">
        {t("home.more")}
      </h2>
      <div className="mb-link-cards">
        <LinkCard
          href={hrefFor({ name: "history" })}
          tone="sky"
          image="/practice/past-papers.png"
          title={t("home.pastPapers.title")}
          text={t("home.pastPapers.text")}
        />
        <LinkCard
          href={hrefFor({ name: "mastery" })}
          tone="mint"
          image="/practice/my-skills.png"
          title={t("home.skills.title")}
          text={t("home.skills.text")}
        />
      </div>
    </section>
  );
}

export function PapersHome({ learnerId }: { learnerId: string }) {
  useLanguage();
  const availability = useAsync(() => getAvailability(learnerId), `availability:${learnerId}`);
  const list = useAsync(() => listPapers(learnerId), `papers:${learnerId}`);

  const current = availability.state.status === "ready" ? availability.state.data : null;
  // a cancelled paper was replaced by another one, so it is not listed
  const earlier =
    list.state.status === "ready"
      ? list.state.data.filter((paper) => paper.paper_id !== current?.paper?.paper_id && paper.status !== "cancelled")
      : [];

  return (
    <>
      <ScreenHeader
        title={t("home.title")}
        kicker={current ? t("home.weekOf", { date: dayLabel(current.week_start) }) : t("home.thisWeek")}
        icon={<PaperIcon />}
      />
      <div className="mb-body-pad">
        {availability.state.status === "loading" ? <Loading label={t("home.checking")} /> : null}
        {availability.state.status === "error" ? (
          <ErrorBox message={availability.state.message} onRetry={availability.reload} />
        ) : null}

        {current?.state === "not_yet_eligible" ? <Countdown availability={current} /> : null}
        {current?.state === "available" && current.can_generate ? <MakePaper learnerId={learnerId} /> : null}
        {current?.state === "generated" && current.paper ? <ThisWeek paper={current.paper} /> : null}
        {current && current.state !== "not_yet_eligible" ? (
          <p className="mb-fineprint">{t("home.nextPaper", { date: dayLabel(current.next_paper_date) })}</p>
        ) : null}

        {list.state.status === "error" ? <ErrorBox message={list.state.message} onRetry={list.reload} /> : null}
        <EarlierPapers papers={earlier} />
        <MoreLinks />
      </div>
    </>
  );
}
