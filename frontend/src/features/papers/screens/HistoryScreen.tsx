import { type PaperHistory, getHistory } from "../api";
import { dayLabel, paperStatusLabel, paperTitle, scoreText } from "../format";
import { useAsync } from "../hooks";
import { hrefFor } from "../router";
import { Chip, ErrorBox, Loading, ScreenHeader, Tick } from "../ui";
import { statusTone } from "./PapersHome";

// How a past paper went, as a bar: right (mint), not right (rose), left blank (sun).
function ResultBar({ paper }: { paper: PaperHistory }) {
  const totals = paper.results;
  if (!totals) return null;
  return (
    <>
      <p className="mb-score">
        <strong>{scoreText(totals)}</strong>
        <span className="mb-muted"> · {totals.marked} marked</span>
      </p>
      <span
        className="mb-split mb-split--wide"
        role="img"
        aria-label={`${totals.correct} correct, ${totals.wrong} not correct, ${totals.blank} left blank`}
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
          <p className="mb-kicker">Week of {dayLabel(paper.week_start)}</p>
          <h3 className="mb-h3">{paperTitle(paper.mode)}</h3>
        </div>
        {finished ? (
          <Chip tone="mint" icon={<Tick className="mb-chip__tick" />}>
            Complete
          </Chip>
        ) : (
          <Chip tone={statusTone(paper.status)}>{paperStatusLabel(paper.status)}</Chip>
        )}
      </div>

      {totals ? (
        <ResultBar paper={paper} />
      ) : (
        <p className="mb-muted">No pages have been marked yet.</p>
      )}
      {totals && totals.waiting_for_parent > 0 ? (
        <p className="mb-fineprint">
          {totals.waiting_for_parent} answer{totals.waiting_for_parent === 1 ? " is" : "s are"} waiting for you.
        </p>
      ) : null}
      {totals && totals.not_uploaded > 0 ? (
        <p className="mb-fineprint">{totals.not_uploaded} questions are on pages with no photo yet.</p>
      ) : null}

      <div className="mb-actions">
        {totals ? (
          <a className="mb-btn mb-btn--small" href={hrefFor({ name: "report", id: paper.paper_id })}>
            See results
          </a>
        ) : null}
        <a className="mb-btn mb-btn--ghost mb-btn--small" href={hrefFor({ name: "paper", id: paper.paper_id })}>
          {finished ? "Pages" : "Upload photos"}
        </a>
      </div>
    </li>
  );
}

export function HistoryScreen({ learnerId }: { learnerId: string }) {
  const { state, reload } = useAsync(() => getHistory(learnerId), `history:${learnerId}`);
  const papers = state.status === "ready" ? state.data : [];
  const completed = papers.filter((p) => p.results_complete);
  const others = papers.filter((p) => !p.results_complete);

  return (
    <>
      <ScreenHeader title="Past papers" kicker="History" />
      <div className="mb-body-pad">
        {state.status === "loading" ? <Loading label="Opening past papers" /> : null}
        {state.status === "error" ? <ErrorBox message={state.message} onRetry={reload} /> : null}
        {state.status === "ready" && papers.length === 0 ? (
          <p className="mb-muted">No papers yet. This week's paper is on the Papers tab.</p>
        ) : null}

        {completed.length > 0 ? (
          <section aria-labelledby="done-title">
            <h2 id="done-title" className="mb-h2 mb-h2--spaced">
              Completed
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
              Still open
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
