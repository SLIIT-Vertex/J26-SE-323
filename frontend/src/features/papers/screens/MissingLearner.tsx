import { t } from "../i18n";
import { ScreenHeader } from "../ui";

/**
 * Shown when the shared development learner is not in this database yet. The game and the papers
 * both point at that learner, so nothing can be saved until it exists.
 */
export function MissingLearner({ learnerId }: { learnerId: string }) {
  return (
    <>
      <ScreenHeader title={t("missing.title")} kicker={t("missing.kicker")} />
      <div className="mb-body-pad">
        <section className="mb-card" aria-labelledby="missing-title">
          <h2 id="missing-title" className="mb-h2">
            {t("missing.heading")}
          </h2>
          <p>{t("missing.body")}</p>
          <p className="mb-code mb-code--id">{learnerId}</p>
          <p>{t("missing.create")}</p>
          <p className="mb-command">python -m scripts.seed_dev_learner</p>
          <p className="mb-fineprint">{t("missing.other")}</p>
        </section>
      </div>
    </>
  );
}
