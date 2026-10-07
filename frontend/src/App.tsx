import { HealthStatus } from "./features/health/HealthStatus";

export default function App() {
  return (
    <main>
      <p className="eyebrow">Shared foundation</p>
      <h1>MindBridge</h1>
      <p>Learning support for Sri Lankan Grade 4–5 scholarship learners.</p>
      <HealthStatus />
    </main>
  );
}
