import { useState } from "react";

import { type Report, type ReportItem, getPaper, getReport, pictureUrl } from "../api";
import { dayLabel, resultLabel, shortDate } from "../format";
import { useAsync } from "../hooks";
import { hrefFor } from "../router";
import { Chip, ErrorBox, Loading, ScreenHeader, Tick } from "../ui";

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

type Filter = "all" | "right" | "practise";

const isRight = (item: ReportItem) => item.result === "correct";
const needsPractice = (item: ReportItem) => item.result === "wrong" || item.result === "blank";
const isMarked = (item: ReportItem) => isRight(item) || needsPractice(item);

function visibleIn(items: ReportItem[], filter: Filter): ReportItem[] {
  const marked = items.filter(isMarked);
  if (filter === "right") return marked.filter(isRight);
  if (filter === "practise") return marked.filter(needsPractice);
  return marked;
}

function QuestionRow({ item }: { item: ReportItem }) {
  const right = isRight(item);
  const tone = right ? "mint" : item.result === "blank" ? "sun" : "rose";
  const photo = item.picture_url ? (
    <img
      className="mb-mistake__picture"
      src={pictureUrl(item.picture_url)}
      alt={`Question ${item.position} with your child's writing`}
    />
  ) : (
    <p className="mb-fineprint">The photo has been removed.</p>
  );
  return (
    <li className={`mb-card mb-mistake mb-q--${item.result}`}>
      <div className="mb-row">
        <h3 className="mb-h3">Question {item.position}</h3>
        <Chip tone={tone} icon={right ? <Tick className="mb-chip__tick" /> : undefined}>
          {resultLabel(item.result)}
        </Chip>
      </div>
      <p className="mb-muted">
        {item.skill_name ?? item.skill_code}
        {item.skill_name_si ? (
          <>
            {" · "}
            <span lang="si">{item.skill_name_si}</span>
          </>
        ) : null}
      </p>
      {right ? (
        <details className="mb-photo">
          <summary>See the photo</summary>
          {photo}
        </details>
      ) : (
        photo
      )}
      <p className="mb-read">
        Written:{" "}
        <strong>{item.written.map((part) => part.text ?? "nothing").join(" · ") || "nothing"}</strong>
      </p>
    </li>
  );
}

// Every question that has a final result, in printed order: the right ones and the ones to practise.
function Questions({ report }: { report: Report }) {
  const [filter, setFilter] = useState<Filter>("all");
  const marked = report.items.filter(isMarked);
  if (marked.length === 0) return null;
  const right = marked.filter(isRight).length;
  const practise = marked.length - right;
  const shown = visibleIn(report.items, filter);
  const options: { value: Filter; label: string }[] = [
    { value: "all", label: `All (${marked.length})` },
    { value: "right", label: `Correct (${right})` },
    { value: "practise", label: `To practise (${practise})` },
  ];
  return (
    <section aria-labelledby="questions-title">
      <h2 id="questions-title" className="mb-h2 mb-h2--spaced">
        Question by question
      </h2>
      {practise === 0 ? (
        <div className="mb-note mb-note--mint">
          <p>No mistakes on the pages marked so far. Well done!</p>
        </div>
      ) : null}
      <fieldset className="mb-seg mb-seg--filter">
        <legend className="mb-visually-hidden">Show</legend>
        {options.map((option) => (
          <label key={option.value}>
            <input
              type="radio"
              name="question-filter"
              checked={filter === option.value}
              onChange={() => setFilter(option.value)}
            />
            <span>{option.label}</span>
          </label>
        ))}
      </fieldset>
      <ul className="mb-list mb-list--loose">
        {shown.map((item) => (
          <QuestionRow key={item.question_id + item.position} item={item} />
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
            <Questions report={data} />
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
