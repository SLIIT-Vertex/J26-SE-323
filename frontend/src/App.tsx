import { lazy, Suspense } from "react";

import { MobileLearningApp } from "./features/mobile-learning-flow/MobileLearningApp";

// Developer-only learner-state page (?dev=learner-state). Excluded from production builds.
const LearnerStateDevPage = import.meta.env.DEV
  ? lazy(() => import("./features/learner-state/dev/LearnerStateDevPage"))
  : null;

/** One MindBridge app: mobile learning shell hosts Papers as its practice tab. */
export default function App() {
  if (LearnerStateDevPage && new URLSearchParams(window.location.search).get("dev") === "learner-state") {
    return (
      <Suspense fallback={<p>Loading…</p>}>
        <LearnerStateDevPage />
      </Suspense>
    );
  }

  return <MobileLearningApp enableOnboarding />;
}
