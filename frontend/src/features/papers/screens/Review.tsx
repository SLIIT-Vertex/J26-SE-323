import { useState } from "react";

import {
  type ReviewItem,
  confirmDecisions,
  friendlyMessage,
  getSubmission,
  pictureUrl,
} from "../api";
import { useAsync } from "../hooks";
import { type Choice, buildDecisions, decidedCount, isInstruction, isReadyToSubmit, itemKey, readingText } from "../reviewLogic";
import { go, hrefFor } from "../router";
import { Chip, ErrorBox, Loading, ScreenHeader, Tick } from "../ui";

// This screen never says whether an answer is right. The parent only says what the child wrote.
// (The server also never sends the answer key or the reason a reading was doubtful, because
// "close to an answer" would give the answer away.)

function Crop({ item }: { item: ReviewItem }) {
  const [open, setOpen] = useState(false);
  const [missing, setMissing] = useState(false);
  if (missing) return <p className="mb-note">This picture is no longer kept.</p>;
  return (
    <button
      type="button"
      className={`mb-crop${open ? " is-open" : ""}`}
      onClick={() => setOpen((now) => !now)}
      aria-label={open ? "Shrink the picture" : "Enlarge the picture"}
    >
      <img
        src={pictureUrl(item.crop_url)}
        alt={`Question ${item.position} as photographed`}
        onError={() => setMissing(true)}
      />
      <span className="mb-crop__hint">{open ? "Tap to shrink" : "Tap to enlarge"}</span>
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
          Yes
        </button>
        <button
          type="button"
          className="mb-choice"
          aria-pressed={choice?.instructionMet === false}
          onClick={() => onChange({ instructionMet: false })}
        >
          No
        </button>
      </fieldset>
    );
  }

  if (item.part_type === "mcq") {
    return (
      <fieldset className="mb-choices">
        <legend>Which option did your child mark?</legend>
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
          No answer
        </button>
      </fieldset>
    );
  }

  const reading = readingText(item);
  return (
    <div className="mb-choices">
      <label className="mb-label" htmlFor={`text-${itemKey(item)}`}>
        What did your child write?
      </label>
      <input
        id={`text-${itemKey(item)}`}
        className="mb-input"
        type="text"
        value={choice?.blank ? "" : (choice?.text ?? "")}
        disabled={choice?.blank === true}
        onChange={(event) => onChange({ text: event.target.value })}
        autoComplete="off"
        autoCapitalize="off"
      />
      <div className="mb-actions">
        {reading ? (
          <button type="button" className="mb-btn mb-btn--ghost mb-btn--small" onClick={() => onChange({ text: reading })}>
            Same as we read
          </button>
        ) : null}
        <button
          type="button"
          className="mb-choice"
          aria-pressed={choice?.blank === true}
          onClick={() => onChange(choice?.blank ? { text: "" } : { blank: true, text: "" })}
        >
          No answer
        </button>
      </div>
    </div>
  );
}

function ItemCard({
  item,
  parts,
  choice,
  onChange,
}: {
  item: ReviewItem;
  parts: number;
  choice: Choice | undefined;
  onChange: (next: Choice) => void;
}) {
  const reading = readingText(item);
  return (
    <li className="mb-card mb-review">
      <div className="mb-row">
        <h3 className="mb-h3">Question {item.position}</h3>
        {parts > 1 ? <Chip tone="sky">Answer {item.part_no}</Chip> : null}
      </div>
      <Crop item={item} />
      {!isInstruction(item) ? (
        <p className="mb-read">
          We read: <strong>{reading ?? "nothing clear"}</strong>
        </p>
      ) : null}
      <Decide item={item} choice={choice} onChange={onChange} />
    </li>
  );
}

export function Review({ submissionId }: { submissionId: string }) {
  const { state, reload } = useAsync(() => getSubmission(submissionId), `submission:${submissionId}`);
  const [choices, setChoices] = useState<Record<string, Choice>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submission = state.status === "ready" ? state.data : null;
  const items = submission?.review_items ?? [];
  const back = submission
    ? { href: hrefFor({ name: "paper", id: submission.paper_id }), label: "Back to the paper" }
    : { href: hrefFor({ name: "papers" }), label: "Papers" };
  const partsAt = (position: number) => items.filter((i) => i.position === position).length;
  const ready = isReadyToSubmit(items, choices);

  async function save() {
    if (!submission) return;
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
      <ScreenHeader title="Unclear answers" kicker={submission ? `Page ${submission.page}` : undefined} back={back} />
      <div className="mb-body-pad mb-body-pad--bar">
        {state.status === "loading" ? <Loading label="Opening the page" /> : null}
        {state.status === "error" ? <ErrorBox message={state.message} onRetry={reload} /> : null}

        {submission && items.length === 0 ? (
          <div className="mb-note mb-note--mint">
            <p>Nothing is waiting for you on this page.</p>
            <a className="mb-btn mb-btn--small" href={back.href}>
              Back to the paper
            </a>
          </div>
        ) : null}

        {items.length > 0 ? (
          <>
            <p className="mb-lead">
              A few answers were hard to read. Tell us what your child wrote. We will not show right or wrong until you
              decide.
            </p>
            <ul className="mb-list mb-list--loose">
              {items.map((item) => (
                <ItemCard
                  key={itemKey(item)}
                  item={item}
                  parts={partsAt(item.position)}
                  choice={choices[itemKey(item)]}
                  onChange={(next) => setChoices((now) => ({ ...now, [itemKey(item)]: next }))}
                />
              ))}
            </ul>
          </>
        ) : null}
      </div>

      {items.length > 0 ? (
        <div className="mb-savebar">
          <div className="mb-savebar__text" aria-live="polite">
            {ready ? (
              <>
                <Tick className="mb-savebar__tick" /> All decided
              </>
            ) : (
              `${decidedCount(items, choices)} of ${items.length} decided`
            )}
            {error ? <span className="mb-savebar__error"> · {error}</span> : null}
          </div>
          <button type="button" className="mb-btn" disabled={!ready || saving} onClick={save}>
            {saving ? "Saving…" : "Save answers"}
          </button>
        </div>
      ) : null}
    </>
  );
}
