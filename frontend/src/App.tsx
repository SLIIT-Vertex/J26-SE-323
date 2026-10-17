import { MobileLearningApp } from "./features/mobile-learning-flow/MobileLearningApp";

/** One MindBridge app: mobile learning shell hosts Papers as its practice tab. */
export default function App() {
  return <MobileLearningApp enableOnboarding />;
}
