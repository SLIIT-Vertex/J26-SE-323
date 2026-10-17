import { useState } from "react";

import { createLearner, friendlyMessage, listLearners } from "../api";
import { dayLabel, languageName, languageNative, shortId } from "../format";
import { setLearnerId, useAsync, useLearnerId } from "../hooks";
import { go } from "../router";
import { ErrorBox, Loading, ScreenHeader, Tick } from "../ui";

const AVATAR_TONES = ["sky", "rose", "mint", "sun"] as const;

function Avatar({ index }: { index: number }) {
  const tone = AVATAR_TONES[index % AVATAR_TONES.length];
  return (
    <svg className={`mb-avatar mb-avatar--${tone}`} viewBox="0 0 48 48" aria-hidden="true" focusable="false">
      <path className="mb-avatar__arch" d="M10 40V26a14 14 0 0 1 28 0v14" />
      <circle className="mb-avatar__sun" cx="24" cy="34" r="6" />
    </svg>
  );
}

export function WhoIsLearning() {
  const { state, reload } = useAsync(listLearners, "learners");
  const current = useLearnerId();
  const [grade, setGrade] = useState<4 | 5>(5);
  const [language, setLanguage] = useState<"si" | "ta">("si");
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function choose(id: string) {
    setLearnerId(id);
    go({ name: "papers" });
  }

  async function add() {
    setAdding(true);
    setError(null);
    try {
      const learner = await createLearner(grade, language);
      choose(learner.id);
    } catch (problem) {
      setError(friendlyMessage(problem));
      setAdding(false);
    }
  }

  return (
    <>
      <ScreenHeader title="Who is learning?" kicker="Choose a learner" />
      <div className="mb-body-pad">
        {state.status === "loading" ? <Loading label="Finding learners" /> : null}
        {state.status === "error" ? <ErrorBox message={state.message} onRetry={reload} /> : null}
        {state.status === "ready" && state.data.length === 0 ? (
          <p className="mb-muted">No learners yet. Add the first one below.</p>
        ) : null}
        {state.status === "ready" && state.data.length > 0 ? (
          <ul className="mb-list">
            {state.data.map((learner, index) => (
              <li key={learner.id}>
                <button type="button" className="mb-learner" onClick={() => choose(learner.id)}>
                  <Avatar index={index} />
                  <span className="mb-learner__text">
                    <strong>
                      Grade {learner.grade} · {languageName(learner.preferred_language)}{" "}
                      <span lang={learner.preferred_language}>({languageNative(learner.preferred_language)})</span>
                    </strong>
                    <small>
                      Joined {dayLabel(learner.created_at)} · ID {shortId(learner.id)}
                    </small>
                  </span>
                  {learner.id === current ? (
                    <span className="mb-learner__current">
                      <Tick />
                      Using
                    </span>
                  ) : null}
                </button>
              </li>
            ))}
          </ul>
        ) : null}

        <section className="mb-card" aria-labelledby="add-learner">
          <h2 id="add-learner" className="mb-h2">
            Add a learner
          </h2>
          <fieldset className="mb-seg">
            <legend>Grade</legend>
            {([4, 5] as const).map((value) => (
              <label key={value}>
                <input type="radio" name="grade" checked={grade === value} onChange={() => setGrade(value)} />
                <span>Grade {value}</span>
              </label>
            ))}
          </fieldset>
          <fieldset className="mb-seg">
            <legend>Question language</legend>
            {(["si", "ta"] as const).map((value) => (
              <label key={value}>
                <input type="radio" name="language" checked={language === value} onChange={() => setLanguage(value)} />
                <span lang={value}>{languageNative(value)}</span>
              </label>
            ))}
          </fieldset>
          {error ? <ErrorBox message={error} /> : null}
          <button type="button" className="mb-btn mb-btn--sun" onClick={add} disabled={adding}>
            {adding ? "Adding…" : "Add and continue"}
          </button>
        </section>

        <p className="mb-fineprint">
          Sign-in is not built yet, so this app remembers the learner on this phone. It will be replaced by the
          parent's login.
        </p>
      </div>
    </>
  );
}
