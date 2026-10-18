import { ScreenHeader } from "../ui";

/**
 * Shown when the shared development learner is not in this database yet. The game and the papers
 * both point at that learner, so nothing can be saved until it exists.
 */
export function MissingLearner({ learnerId }: { learnerId: string }) {
  return (
    <>
      <ScreenHeader title="Learner not set up" kicker="Development setup" />
      <div className="mb-body-pad">
        <section className="mb-card" aria-labelledby="missing-title">
          <h2 id="missing-title" className="mb-h2">
            This database has no learner with this id
          </h2>
          <p>
            Until there is a login, the game and the papers share one development learner. It has to
            exist in the database before either can save anything.
          </p>
          <p className="mb-code mb-code--id">{learnerId}</p>
          <p>Create it once, in the backend folder:</p>
          <p className="mb-command">python -m scripts.seed_dev_learner</p>
          <p className="mb-fineprint">
            To use another learner for both the game and the papers, set VITE_MOBILE_LEARNING_LEARNER_ID
            and restart the frontend.
          </p>
        </section>
      </div>
    </>
  );
}
