import { getPaper, getReport, pictureUrl, type Report } from "../api";
import { dayLabel, shortDate } from "../format";
import { useAsync } from "../hooks";
import { hrefFor } from "../router";
import { Chip, ErrorBox, Loading, ScreenHeader } from "../ui";

function Tile({ tone, count, label }: { tone: "mint" | "rose" | "sun"; count: number; label: string }) {
  return (
    <li className={`mb-tile mb-tile--${tone}`}>
      <span className="mb-tile__count">{count}</span>
      <span className="mb-tile__label">{label}</span>
    </li>
  );
}

function Summary({ report }: { report: Report }) {
  const { summary } = report;
  return (
    <section aria-labelledby="summary-title">
      <h2 id="summary-title" className="mb-h2">
        {summary.marked} of {summary.questions} questions marked
      </h2>
      <ul className="mb-tiles">
        <Tile tone="mint" count={summary.correct} label="Correct" />
        <Tile tone="rose" count={summary.wrong} label="Not correct" />
        <Tile tone="sun" count={summary.blank} label="Left blank" />
      </ul>
    </section>
  );
}

function Skills({ report }: { report: Report }) {
  if (report.skills.length === 0) return null;
  return (
    <section aria-labelledby="skills-title">
      <h2 id="skills-title" className="mb-h2 mb-h2--spaced">
        By skill
      </h2>
      <ul className="mb-list">
        {report.skills.map((skill) => {
          const total = skill.correct + skill.wrong + skill.blank;
          return (
            <li key={skill.skill_code} className="mb-skillrow">
              <div>
                <strong>{skill.name}</strong>
                {skill.name_si ? (
                  <small lang="si" className="mb-muted">
                    {skill.name_si}
                  </small>
                ) : null}
              </div>
              <span
                className="mb-split"
                role="img"
                aria-label={`${skill.correct} correct, ${skill.wrong} not correct, ${skill.blank} blank`}
              >
                <i className="mb-split__ok" style={{ flexGrow: skill.correct }} />
                <i className="mb-split__no" style={{ flexGrow: skill.wrong }} />
                <i className="mb-split__blank" style={{ flexGrow: skill.blank }} />
              </span>
              <span className="mb-skillrow__score">
                {skill.correct}/{total}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function Mistakes({ report }: { report: Report }) {
  if (report.mistakes.length === 0) {
    return report.summary.marked > 0 ? (
      <div className="mb-note mb-note--mint">
        <p>No mistakes on the pages marked so far. Well done!</p>
      </div>
    ) : null;
  }
  return (
    <section aria-labelledby="mistakes-title">
      <h2 id="mistakes-title" className="mb-h2 mb-h2--spaced">
        Worth another look
      </h2>
      <ul className="mb-list mb-list--loose">
        {report.mistakes.map((mistake) => (
          <li key={mistake.question_id} className="mb-card mb-mistake">
            <div className="mb-row">
              <h3 className="mb-h3">Question {mistake.position}</h3>
              <Chip tone={mistake.result === "blank" ? "sun" : "rose"}>
                {mistake.result === "blank" ? "Left blank" : "Not correct"}
              </Chip>
            </div>
            <p className="mb-muted">
              {mistake.skill_name}
              {mistake.skill_name_si ? (
                <>
                  {" · "}
                  <span lang="si">{mistake.skill_name_si}</span>
                </>
              ) : null}
            </p>
            {mistake.picture_url ? (
              <img
                className="mb-mistake__picture"
                src={pictureUrl(mistake.picture_url)}
                alt={`Question ${mistake.position} with your child's writing`}
              />
            ) : (
              <p className="mb-fineprint">The photo has been removed.</p>
            )}
            <p className="mb-read">
              Written:{" "}
              <strong>
                {mistake.written.map((part) => part.text ?? "nothing").join(" · ") || "nothing"}
              </strong>
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}

// The correct answers are a separate list, by question number, as agreed: never next to the question.
function AnswerList({ report }: { report: Report }) {
  if (report.answer_list.length === 0) return null;
  return (
    <section className="mb-card mb-answers" aria-labelledby="answers-title">
      <h2 id="answers-title" className="mb-h2">
        Answer list
      </h2>
      <p className="mb-fineprint">Only for the questions above. Look after your child has tried them again.</p>
      <dl>
        {report.answer_list.map((entry) => (
          <div key={entry.position} className="mb-answers__row">
            <dt>Q{entry.position}</dt>
            <dd>
              {entry.answers.map((a) => (a.label ? `${a.label}: ${a.answer}` : a.answer)).join("  ·  ")}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

export function ReportScreen({ paperId }: { paperId: string }) {
  const report = useAsync(() => getReport(paperId), `report:${paperId}`);
  const paper = useAsync(() => getPaper(paperId), `report-paper:${paperId}`);
  const data = report.state.status === "ready" ? report.state.data : null;
  const waiting = paper.state.status === "ready" ? (paper.state.data.pages ?? []).filter((p) => p.submission_status === "needs_review") : [];

  return (
    <>
      <ScreenHeader
        title="Results"
        kicker={data ? `Week of ${dayLabel(data.week_start)}` : undefined}
        back={{ href: hrefFor({ name: "paper", id: paperId }), label: "The paper" }}
      />
      <div className="mb-body-pad">
        {report.state.status === "loading" ? <Loading label="Gathering the results" /> : null}
        {report.state.status === "error" ? <ErrorBox message={report.state.message} onRetry={report.reload} /> : null}

        {data ? (
          <>
            {waiting.length > 0 ? (
              <div className="mb-note mb-note--rose">
                <p>
                  {data.summary.waiting_for_parent} answer{data.summary.waiting_for_parent === 1 ? " is" : "s are"} waiting for
                  you before the results are complete.
                </p>
                {waiting.map((page) =>
                  page.submission_id ? (
                    <a
                      key={page.page}
                      className="mb-btn mb-btn--small"
                      href={hrefFor({ name: "review", id: page.submission_id })}
                    >
                      Review page {page.page}
                    </a>
                  ) : null,
                )}
              </div>
            ) : null}
            {data.summary.not_uploaded > 0 ? (
              <p className="mb-fineprint">
                {data.summary.not_uploaded} questions are on pages with no photo yet.
              </p>
            ) : null}

            {data.summary.marked > 0 ? <Summary report={data} /> : <p className="mb-muted">Nothing is marked yet.</p>}
            <Skills report={data} />
            <Mistakes report={data} />
            <AnswerList report={data} />

            <p className="mb-fineprint">
              {data.photos_kept_until
                ? `Photos of these pages are kept until ${shortDate(data.photos_kept_until)}, then deleted. `
                : ""}
              Next paper: {dayLabel(data.next_paper_date)}.
            </p>
          </>
        ) : null}
      </div>
    </>
  );
}
