import "./papers.css";

import { type Learner, getLearner } from "./api";
import { languageName, languageNative } from "./format";
import { isNotFound, useAsync, useBodyClass, useLearnerId } from "./hooks";
import type { Route } from "./router";
import { MasteryScreen } from "./screens/MasteryScreen";
import { PaperDetail } from "./screens/PaperDetail";
import { PapersHome } from "./screens/PapersHome";
import { Review } from "./screens/Review";
import { ReportScreen } from "./screens/ReportScreen";
import { HistoryScreen } from "./screens/HistoryScreen";
import { MissingLearner } from "./screens/MissingLearner";

function TopBar({ learner }: { learner: Learner | null }) {
  return (
    <div className="mb-topbar">
      <a className="mb-brand" href="#/" aria-label="MindBridge home">
        <img className="mb-brand__wordmark" src="/primary_logo.png" alt="MindBridge" />
      </a>
      <span className="mb-pill">
        {learner ? (
          <>
            Grade {learner.grade} · <span lang={learner.preferred_language}>{languageNative(learner.preferred_language)}</span>
            <span className="mb-visually-hidden"> ({languageName(learner.preferred_language)})</span>
          </>
        ) : (
          "Learner"
        )}
      </span>
    </div>
  );
}

function Screen({ route, learnerId }: { route: Route; learnerId: string }) {
  switch (route.name) {
    case "papers":
      return <PapersHome learnerId={learnerId} />;
    case "paper":
      return <PaperDetail paperId={route.id} />;
    case "report":
      return <ReportScreen paperId={route.id} />;
    case "review":
      return <Review submissionId={route.id} />;
    case "history":
      return <HistoryScreen learnerId={learnerId} />;
    case "mastery":
      return <MasteryScreen learnerId={learnerId} />;
  }
}

export function PapersApp({
  route,
  embedded = false,
}: {
  route: Route;
  /** Hosted inside MobileLearningApp practice tab — drop the standalone top brand bar. */
  embedded?: boolean;
}) {
  useBodyClass("mb-body");
  const learnerId = useLearnerId();
  const learner = useAsync(() => getLearner(learnerId), `learner:${learnerId}`);

  // The shared learner has to exist in the database (the game and the papers both point at it)
  const missing = learner.state.status === "error" && isNotFound(learner.state.error);
  const known = learner.state.status === "ready" ? learner.state.data : null;

  return (
    <div className={embedded ? "mb mb--embedded" : "mb"}>
      <div className="mb-frame">
        {embedded ? null : <TopBar learner={known} />}
        <main className="mb-main">
          {missing ? <MissingLearner learnerId={learnerId} /> : <Screen route={route} learnerId={learnerId} />}
        </main>
      </div>
    </div>
  );
}
