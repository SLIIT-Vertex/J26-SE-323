import "@fontsource-variable/fredoka";
import "@fontsource-variable/nunito";
import "./papers.css";

import { useEffect } from "react";

import { type Learner, getLearner } from "./api";
import { languageName, languageNative } from "./format";
import { isNotFound, setLearnerId, useAsync, useBodyClass, useLearnerId } from "./hooks";
import { type Route, hrefFor } from "./router";
import { MasteryScreen } from "./screens/MasteryScreen";
import { PaperDetail } from "./screens/PaperDetail";
import { PapersHome } from "./screens/PapersHome";
import { Review } from "./screens/Review";
import { ReportScreen } from "./screens/ReportScreen";
import { HistoryScreen } from "./screens/HistoryScreen";
import { WhoIsLearning } from "./screens/WhoIsLearning";
import { GrowthIcon, HistoryIcon, PaperIcon } from "./ui";

function TopBar({ learner }: { learner: Learner | null }) {
  return (
    <div className="mb-topbar">
      <a className="mb-brand" href="#/" aria-label="MindBridge home">
        <img className="mb-brand__wordmark" src="/primary_logo.png" alt="MindBridge" />
      </a>
      <a className="mb-pill" href={hrefFor({ name: "who" })}>
        {learner ? (
          <>
            Grade {learner.grade} · <span lang={learner.preferred_language}>{languageNative(learner.preferred_language)}</span>
            <span className="mb-visually-hidden"> ({languageName(learner.preferred_language)}). Change learner</span>
          </>
        ) : (
          "Choose learner"
        )}
      </a>
    </div>
  );
}

function TabBar({ route }: { route: Route }) {
  const papers = route.name === "papers" || route.name === "paper" || route.name === "report" || route.name === "review";
  const history = route.name === "history";
  const progress = route.name === "mastery";
  return (
    <nav className="mb-tabs" aria-label="Main">
      <a className="mb-tab" href={hrefFor({ name: "papers" })} aria-current={papers ? "page" : undefined}>
        <span className="mb-tab__icon">
          <PaperIcon />
        </span>
        Papers
      </a>
      <a className="mb-tab" href={hrefFor({ name: "history" })} aria-current={history ? "page" : undefined}>
        <span className="mb-tab__icon">
          <HistoryIcon />
        </span>
        Past papers
      </a>
      <a className="mb-tab" href={hrefFor({ name: "mastery" })} aria-current={progress ? "page" : undefined}>
        <span className="mb-tab__icon">
          <GrowthIcon />
        </span>
        Progress
      </a>
    </nav>
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
    case "who":
      return <WhoIsLearning />;
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
  const learner = useAsync(
    async () => (learnerId ? await getLearner(learnerId) : null),
    `learner:${learnerId ?? "none"}`,
  );

  // A remembered learner that no longer exists (for example after the database was reset)
  const gone = learner.state.status === "error" && isNotFound(learner.state.error);
  useEffect(() => {
    if (gone) setLearnerId(null);
  }, [gone]);

  const known = learner.state.status === "ready" ? learner.state.data : null;
  const effective: Route = learnerId ? route : { name: "who" };

  return (
    <div className={embedded ? "mb mb--embedded" : "mb"}>
      <div className="mb-frame">
        {embedded ? null : <TopBar learner={known} />}
        <main className="mb-main">
          <Screen route={effective} learnerId={learnerId ?? ""} />
        </main>
        {learnerId ? <TabBar route={effective} /> : null}
      </div>
    </div>
  );
}
