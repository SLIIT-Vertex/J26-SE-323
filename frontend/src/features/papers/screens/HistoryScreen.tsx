import { getHistory, type PaperHistory } from "../api";
import { dayLabel, paperStatusLabel, paperTitle, scoreText } from "../format";
import { useAsync } from "../hooks";
import { t, tn, useLanguage } from "../i18n";
import { hrefFor } from "../router";
import { Chip, ErrorBox, HistoryIcon, Loading, ScreenHeader, Tick } from "../ui";
import { statusTone } from "./PapersHome";

// How a past paper went, as a bar: right (mint), not right (rose), left blank (sun).
function ResultBar({ paper }: { paper: PaperHistory }) {
  const totals = paper.results;
  if (!totals) return null;
  return (
    <>
      <p className="mb-score">
        <strong>{scoreText(totals)}</strong>
        <span className="mb-muted"> · {t("history.marked", { n: totals.marked })}</span>
      </p>
      <span
        className="mb-split mb-split--wide"
        role="img"
        aria-label={t("history.barAria", {
          correct: totals.correct,
          wrong: totals.wrong,
          blank: totals.blank,
        })}
      >
        <i className="mb-split__ok" style={{ flexGrow: totals.correct }} />
        <i className="mb-split__no" style={{ flexGrow: totals.wrong }} />
        <i className="mb-split__blank" style={{ flexGrow: totals.blank }} />
      </span>
    </>
  );
}

function PastPaper({ paper }: { paper: PaperHistory }) {
  const totals = paper.results;
  const finished = paper.results_complete;
  return (
    <li className="mb-card mb-past">
      <div className="mb-row">
        <div>
          <p className="mb-kicker">{t("home.weekOf", { date: dayLabel(paper.week_start) })}</p>
          <h3 className="mb-h3">{paperTitle(paper.mode)}</h3>
        </div>
        {finished ? (
          <Chip tone="mint" icon={<Tick className="mb-chip__tick" />}>
            {t("history.complete")}
          </Chip>
        ) : (
          <Chip tone={statusTone(paper.status)}>{paperStatusLabel(paper.status)}</Chip>
        )}
      </div>

      {totals ? <ResultBar paper={paper} /> : <p className="mb-muted">{t("history.noPagesMarked")}</p>}
      {totals && totals.waiting_for_parent > 0 ? (
        <p className="mb-fineprint">{tn("history.waiting", totals.waiting_for_parent)}</p>
      ) : null}
      {totals && totals.not_uploaded > 0 ? (
        <p className="mb-fineprint">{t("report.notUploaded", { n: totals.not_uploaded })}</p>
      ) : null}

      <div className="mb-actions">
        {totals ? (
          <a className="mb-btn mb-btn--small" href={hrefFor({ name: "report", id: paper.paper_id })}>
            {t("history.seeResults")}
          </a>
        ) : null}
        <a className="mb-btn mb-btn--ghost mb-btn--small" href={hrefFor({ name: "paper", id: paper.paper_id })}>
          {finished ? t("history.pages") : t("home.uploadPhotos")}
        </a>
      </div>
    </li>
  );
}

export function HistoryScreen({ learnerId }: { learnerId: string }) {
  useLanguage();
  const { state, reload } = useAsync(() => getHistory(learnerId), `history:${learnerId}`);
  const papers = state.status === "ready" ? state.data : [];
  const completed = papers.filter((p) => p.results_complete);
  const others = papers.filter((p) => !p.results_complete);

  return (
    <>
      <ScreenHeader
        title={t("history.title")}
        kicker={t("history.kicker")}
        back={{
          href: hrefFor({ name: "papers" }),
          label: t("common.practice"),
        }}
        icon={<HistoryIcon />}
      />
      <div className="mb-body-pad">
        {state.status === "loading" ? <Loading label={t("history.opening")} /> : null}
        {state.status === "error" ? <ErrorBox message={state.message} onRetry={reload} /> : null}
        {state.status === "ready" && papers.length === 0 ? <p className="mb-muted">{t("history.empty")}</p> : null}

        {completed.length > 0 ? (
          <section aria-labelledby="done-title">
            <h2 id="done-title" className="mb-h2 mb-h2--spaced">
              {t("history.completed")}
            </h2>
            <ul className="mb-list mb-list--loose">
              {completed.map((paper) => (
                <PastPaper key={paper.paper_id} paper={paper} />
              ))}
            </ul>
          </section>
        ) : null}

        {others.length > 0 ? (
          <section aria-labelledby="open-title">
            <h2 id="open-title" className="mb-h2 mb-h2--spaced">
              {t("history.stillOpen")}
            </h2>
            <ul className="mb-list mb-list--loose">
              {others.map((paper) => (
                <PastPaper key={paper.paper_id} paper={paper} />
              ))}
            </ul>
          </section>
        ) : null}
      </div>
    </>
  );
}
