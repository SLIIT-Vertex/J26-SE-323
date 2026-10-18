import { useState } from "react";

import { getPaper, getReport, pictureUrl, type Report, type ReportItem } from "../api";
import { dayLabel, resultLabel, shortDate, skillName } from "../format";
import { useAsync } from "../hooks";
import { t, tn, useLanguage } from "../i18n";
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
        {t("report.summary", {
          marked: summary.marked,
          questions: summary.questions,
        })}
      </h2>
      <ul className="mb-tiles">
        <Tile tone="mint" count={summary.correct} label={t("result.correct")} />
        <Tile tone="rose" count={summary.wrong} label={t("result.wrong")} />
        <Tile tone="sun" count={summary.blank} label={t("result.blank")} />
      </ul>
    </section>
  );
}

function Skills({ report }: { report: Report }) {
  if (report.skills.length === 0) return null;
  return (
    <section aria-labelledby="skills-title">
      <h2 id="skills-title" className="mb-h2 mb-h2--spaced">
        {t("report.bySkill")}
      </h2>
      <ul className="mb-list">
        {report.skills.map((skill) => {
          const total = skill.correct + skill.wrong + skill.blank;
          return (
            <li key={skill.skill_code} className="mb-skillrow">
              <div>
                <strong>{skillName({ en: skill.name, si: skill.name_si })}</strong>
              </div>
              <span
                className="mb-split"
                role="img"
                aria-label={t("report.splitAria", {
                  correct: skill.correct,
                  wrong: skill.wrong,
                  blank: skill.blank,
                })}
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
      alt={t("report.photoAlt", { n: item.position })}
    />
  ) : (
    <p className="mb-fineprint">{t("report.photoRemoved")}</p>
  );
  return (
    <li className={`mb-card mb-mistake mb-q--${item.result}`}>
      <div className="mb-row">
        <h3 className="mb-h3">{t("review.question", { n: item.position })}</h3>
        <Chip tone={tone} icon={right ? <Tick className="mb-chip__tick" /> : undefined}>
          {resultLabel(item.result)}
        </Chip>
      </div>
      <p className="mb-muted">
        {item.skill_name ? skillName({ en: item.skill_name, si: item.skill_name_si }) : item.skill_code}
      </p>
      {right ? (
        <details className="mb-photo">
          <summary>{t("report.seePhoto")}</summary>
          {photo}
        </details>
      ) : (
        photo
      )}
      <p className="mb-read">
        {t("report.written")}{" "}
        <strong>
          {item.written.map((part) => part.text ?? t("report.nothing")).join(" · ") || t("report.nothing")}
        </strong>
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
    { value: "all", label: t("report.filter.all", { n: marked.length }) },
    { value: "right", label: t("report.filter.right", { n: right }) },
    { value: "practise", label: t("report.filter.practise", { n: practise }) },
  ];
  return (
    <section aria-labelledby="questions-title">
      <h2 id="questions-title" className="mb-h2 mb-h2--spaced">
        {t("report.qbq")}
      </h2>
      {practise === 0 ? (
        <div className="mb-note mb-note--mint">
          <p>{t("report.noMistakes")}</p>
        </div>
      ) : null}
      <fieldset className="mb-seg mb-seg--filter">
        <legend className="mb-visually-hidden">{t("report.show")}</legend>
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
        {t("report.answerList")}
      </h2>
      <p className="mb-fineprint">{t("report.answerListNote")}</p>
      <dl>
        {report.answer_list.map((entry) => (
          <div key={entry.position} className="mb-answers__row">
            <dt>{t("report.qShort", { n: entry.position })}</dt>
            <dd>{entry.answers.map((a) => (a.label ? `${a.label}: ${a.answer}` : a.answer)).join("  ·  ")}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

export function ReportScreen({ paperId }: { paperId: string }) {
  useLanguage();
  const report = useAsync(() => getReport(paperId), `report:${paperId}`);
  const paper = useAsync(() => getPaper(paperId), `report-paper:${paperId}`);
  const data = report.state.status === "ready" ? report.state.data : null;
  const waiting =
    paper.state.status === "ready"
      ? (paper.state.data.pages ?? []).filter((p) => p.submission_status === "needs_review")
      : [];

  return (
    <>
      <ScreenHeader
        title={t("report.title")}
        kicker={data ? t("home.weekOf", { date: dayLabel(data.week_start) }) : undefined}
        back={{
          href: hrefFor({ name: "paper", id: paperId }),
          label: t("report.back"),
        }}
      />
      <div className="mb-body-pad">
        {report.state.status === "loading" ? <Loading label={t("report.gathering")} /> : null}
        {report.state.status === "error" ? <ErrorBox message={report.state.message} onRetry={report.reload} /> : null}

        {data ? (
          <>
            {waiting.length > 0 ? (
              <div className="mb-note mb-note--rose">
                <p>{tn("report.waiting", data.summary.waiting_for_parent)}</p>
                {waiting.map((page) =>
                  page.submission_id ? (
                    <a
                      key={page.page}
                      className="mb-btn mb-btn--small"
                      href={hrefFor({ name: "review", id: page.submission_id })}
                    >
                      {t("report.reviewPage", { n: page.page })}
                    </a>
                  ) : null,
                )}
              </div>
            ) : null}
            {data.summary.not_uploaded > 0 ? (
              <p className="mb-fineprint">{t("report.notUploaded", { n: data.summary.not_uploaded })}</p>
            ) : null}

            {data.summary.marked > 0 ? (
              <Summary report={data} />
            ) : (
              <p className="mb-muted">{t("report.nothingMarked")}</p>
            )}
            <Skills report={data} />
            <Questions report={data} />
            <AnswerList report={data} />

            <p className="mb-fineprint">
              {data.photos_kept_until ? `${t("report.photosKept", { date: shortDate(data.photos_kept_until) })} ` : ""}
              {t("report.nextPaper", { date: dayLabel(data.next_paper_date) })}
            </p>
          </>
        ) : null}
      </div>
    </>
  );
}
