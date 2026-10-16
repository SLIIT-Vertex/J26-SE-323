import { HealthStatus } from "./features/health/HealthStatus";
import { GameHost } from "./features/gamification/GameHost";
import { EpisodeInspector } from "./features/gamification/inspector/EpisodeInspector";
import { BuildPreview } from "./features/gamification/phaser/templates/build-manipulate/BuildPreview";
import { useHashRoute } from "./features/gamification/session/useHashRoute";
import { PapersApp } from "./features/papers/PapersApp";
import { usePapersRoute } from "./features/papers/router";

export default function App() {
  const route = useHashRoute();
  const papersRoute = usePapersRoute();
  if (papersRoute) return <PapersApp route={papersRoute} />;
  return (
    <main className={route === "home" ? undefined : "shell"}>
      <p className="eyebrow">Shared foundation</p>
      <h1 className={route === "home" ? undefined : "compact"}>MindBridge</h1>
      <p>Learning support for Sri Lankan Grade 4–5 scholarship learners.</p>
      <nav className="shell-nav">
        <a href="#/">Home</a>
        <a href="#/play">Play</a>
        <a href="#/inspector">Inspector</a>
        <a href="#/build">Fraction bar</a>
        <a href="#/papers">Papers &amp; progress</a>
      </nav>
      {route === "play" ? <GameHost /> : null}
      {route === "inspector" ? <EpisodeInspector /> : null}
      {route === "build" ? <BuildPreview /> : null}
      {route === "home" ? <HealthStatus /> : null}
    </main>
  );
}
