import { useState } from "react";

import { confirmDecisions, friendlyMessage, getSubmission, pictureUrl, type ReviewItem } from "../api";
import { useAsync } from "../hooks";
import { t, tn, useLanguage } from "../i18n";
import {
  blankCount,
  buildDecisions,
  type Choice,
  decidedCount,
  groupByQuestion,
  isInstruction,
  isReadyToSubmit,
  itemKey,
  partTitle,
  type QuestionGroup,
  readingText,
  toggleBlank,
} from "../reviewLogic";
import { go, hrefFor } from "../router";
import { ErrorBox, Loading, ScreenHeader, Tick } from "../ui";

// This screen never says whether an answer is right. The parent only says what the child wrote.
// (The server also never sends the answer key or the reason a reading was doubtful, because
// "close to an answer" would give the answer away.)

function Crop({ item }: { item: ReviewItem }) {
  const [open, setOpen] = useState(false);
  const [missing, setMissing] = useState(false);
  if (missing) return <p className="mb-note">{t("review.pictureGone")}</p>;
  return (
    <button
      type="button"
      className={`mb-crop${open ? " is-open" : ""}`}
      onClick={() => setOpen((now) => !now)}
      aria-label={open ? t("review.shrink") : t("review.enlarge")}
    >
      <img
        src={pictureUrl(item.crop_url)}
        alt={t("review.pictureAlt", { n: item.position })}
        onError={() => setMissing(true)}
      />
      <span className="mb-crop__hint">{open ? t("review.hintShrink") : t("review.hintEnlarge")}</span>
    </button>
  );
}

function Decide({
  item,
  choice,
  onChange,
}: {
  item: ReviewItem;
  choice: Choice | undefined;
  onChange: (next: Choice) => void;
}) {
  if (isInstruction(item)) {
    return (
      <fieldset className="mb-choices">
        <legend>{item.ask}</legend>
        <button
          type="button"
          className="mb-choice"
          aria-pressed={choice?.instructionMet === true}
          onClick={() => onChange({ instructionMet: true })}
        >
          {t("review.yes")}
        </button>
        <button
          type="button"
          className="mb-choice"
          aria-pressed={choice?.instructionMet === false}
          onClick={() => onChange({ instructionMet: false })}
        >
          {t("review.no")}
        </button>
      </fieldset>
    );
  }

  if (item.part_type === "mcq") {
    return (
      <fieldset className="mb-choices">
        <legend>{t("review.whichOption")}</legend>
        {(item.options ?? []).map((option) => (
          <button
            key={option}
            type="button"
            className="mb-choice mb-choice--round"
            aria-pressed={choice?.selected === option}
            onClick={() => onChange({ selected: option })}
          >
            {option}
          </button>
        ))}
        <button
          type="button"
          className="mb-choice"
          aria-pressed={choice?.selected === null}
          onClick={() => onChange({ selected: null })}
        >
          {t("review.noAnswer")}
        </button>
      </fieldset>
    );
  }

  const reading = readingText(item);
  return (
    <div className="mb-choices">
      <label className="mb-label" htmlFor={`text-${itemKey(item)}`}>
        {t("review.whatWrote")}
      </label>
      <input
        id={`text-${itemKey(item)}`}
        className="mb-input"
        type="text"
        value={choice?.text ?? ""}
        disabled={choice?.blank === true}
        onChange={(event) => onChange({ text: event.target.value })}
        autoComplete="off"
        autoCapitalize="off"
      />
      <div className="mb-actions">
        {reading ? (
          <button
            type="button"
            className="mb-btn mb-btn--ghost mb-btn--small"
            onClick={() => onChange({ text: reading })}
          >
            {t("review.sameAsRead")}
          </button>
        ) : null}
        <button
          type="button"
          className="mb-choice"
          aria-pressed={choice?.blank === true}
          onClick={() => onChange(toggleBlank(choice))}
        >
          {t("review.noAnswer")}
        </button>
      </div>
    </div>
  );
}

function PartFields({
  item,
  many,
  choice,
  onChange,
}: {
  item: ReviewItem;
  many: boolean;
  choice: Choice | undefined;
  onChange: (next: Choice) => void;
}) {
  const reading = readingText(item);
  return (
    <div className={many ? "mb-part" : undefined}>
      {many ? <h4 className="mb-part__title">{partTitle(item)}</h4> : null}
      {!isInstruction(item) ? (
        <p className="mb-read">
          {t("review.weRead")} <strong>{reading ?? t("review.nothingClear")}</strong>
        </p>
      ) : null}
      <Decide item={item} choice={choice} onChange={onChange} />
    </div>
  );
}

// One card per question, with one picture and one labelled box for each answer it needs.
function QuestionCard({
  group,
  choices,
  onChange,
}: {
  group: QuestionGroup;
  choices: Record<string, Choice>;
  onChange: (key: string, next: Choice) => void;
}) {
  const many = group.partCount > 1;
  const first = group.items[0];
  return (
    <li className="mb-card mb-review">
      <h3 className="mb-h3">{t("review.question", { n: group.position })}</h3>
      <Crop item={first} />
      {many ? (
        <p className="mb-fineprint">
          {t("review.manyAnswers", { n: group.partCount })}
          {group.items.length < group.partCount ? t("review.othersClear") : ""}
        </p>
      ) : null}
      {group.items.map((item) => (
        <PartFields
          key={itemKey(item)}
          item={item}
          many={many}
          choice={choices[itemKey(item)]}
          onChange={(next) => onChange(itemKey(item), next)}
        />
      ))}
    </li>
  );
}

export function Review({ submissionId }: { submissionId: string }) {
  useLanguage();
  const { state, reload } = useAsync(() => getSubmission(submissionId), `submission:${submissionId}`);
  const [choices, setChoices] = useState<Record<string, Choice>>({});
  const [saving, setSaving] = useState(false);
  const [confirmBlanks, setConfirmBlanks] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submission = state.status === "ready" ? state.data : null;
  const items = submission?.review_items ?? [];
  const groups = groupByQuestion(items);
  const back = submission
    ? {
        href: hrefFor({ name: "paper", id: submission.paper_id }),
        label: t("review.backToPaper"),
      }
    : { href: hrefFor({ name: "papers" }), label: t("common.practice") };
  const ready = isReadyToSubmit(items, choices);
  const blanks = blankCount(items, choices);

  function change(key: string, next: Choice) {
    setChoices((now) => ({ ...now, [key]: next }));
    setConfirmBlanks(false);
  }

  async function save() {
    if (!submission) return;
    if (blanks > 0 && !confirmBlanks) {
      setConfirmBlanks(true); // answers marked "No answer" are checked once before they are saved
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await confirmDecisions(submission.submission_id, buildDecisions(items, choices));
      go({ name: "paper", id: submission.paper_id });
    } catch (problem) {
      setError(friendlyMessage(problem));
      setSaving(false);
    }
  }

  return (
    <>
      <ScreenHeader
        title={t("review.title")}
        kicker={submission ? t("review.pageKicker", { n: submission.page }) : undefined}
        back={back}
      />
      <div className="mb-body-pad mb-body-pad--bar">
        {state.status === "loading" ? <Loading label={t("review.opening")} /> : null}
        {state.status === "error" ? <ErrorBox message={state.message} onRetry={reload} /> : null}

        {submission && items.length === 0 ? (
          <div className="mb-note mb-note--mint">
            <p>{t("review.nothingWaiting")}</p>
            <a className="mb-btn mb-btn--small" href={back.href}>
              {t("review.backToPaper")}
            </a>
          </div>
        ) : null}

        {items.length > 0 ? (
          <>
            <p className="mb-lead">{t("review.intro")}</p>
            <ul className="mb-list mb-list--loose">
              {groups.map((group) => (
                <QuestionCard key={group.paperItemId} group={group} choices={choices} onChange={change} />
              ))}
            </ul>
          </>
        ) : null}
      </div>

      {items.length > 0 ? (
        <div className="mb-savebar">
          <div className="mb-savebar__text" aria-live="polite">
            {confirmBlanks ? (
              tn("review.confirmBlanks", blanks)
            ) : ready ? (
              <>
                <Tick className="mb-savebar__tick" /> {t("review.allDecided")}
              </>
            ) : (
              t("review.decided", {
                n: decidedCount(items, choices),
                total: items.length,
              })
            )}
            {error ? <span className="mb-savebar__error"> · {error}</span> : null}
          </div>
          <div className="mb-savebar__buttons">
            {confirmBlanks ? (
              <button
                type="button"
                className="mb-btn mb-btn--ghost mb-btn--small"
                onClick={() => setConfirmBlanks(false)}
              >
                {t("review.goBack")}
              </button>
            ) : null}
            <button type="button" className="mb-btn" disabled={!ready || saving} onClick={save}>
              {saving ? t("review.saving") : confirmBlanks ? t("review.saveAnyway") : t("review.save")}
            </button>
          </div>
        </div>
      ) : null}
    </>
  );
}
