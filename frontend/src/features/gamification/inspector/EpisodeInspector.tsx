import { useState } from "react";

import type { ReconstructionView } from "../api/generated";
import { PilotApiError, PilotClient } from "../api/pilotClient";

export function EpisodeInspector({ client = new PilotClient() }: { client?: PilotClient }) {
  const [episodeId, setEpisodeId] = useState(
    () => sessionStorage.getItem("pilot-episode-id") ?? "",
  );
  const [evidence, setEvidence] = useState<ReconstructionView | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    try {
      setEvidence(await client.reconstruct(episodeId));
    } catch (caught) {
      setEvidence(null);
      setError(caught instanceof PilotApiError ? caught.code : "REQUEST_FAILED");
    }
  }

  return (
    <section>
      <p className="eyebrow">Researcher only</p>
      <h2>Episode inspector</h2>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void load();
        }}
      >
        <label>
          Episode id
          <input value={episodeId} onChange={(event) => setEpisodeId(event.target.value)} />
        </label>
        <button type="submit">Reconstruct</button>
      </form>
      {error ? <p role="alert">{error}</p> : null}
      {evidence ? <Reconstruction evidence={evidence} /> : null}
    </section>
  );
}

function Reconstruction({ evidence }: { evidence: ReconstructionView }) {
  return (
    <div className="inspector">
      <p>Phase: {evidence.phase}</p>
      <p>Delivered scaffold: {String(evidence.delivered_scaffold_id)}</p>
      <p>Baseline score: {String(evidence.baseline_score)}</p>
      <p>Verification score: {String(evidence.verification_score)}</p>
      <p>Independence gain: {String(evidence.independence_gain)}</p>
      <p>Validity: {String(evidence.validity)}</p>
      <h3>Beliefs</h3>
      <ul>
        {evidence.beliefs.map((belief) => (
          <li key={belief.code}>
            {belief.code}: {belief.probability}
          </li>
        ))}
      </ul>
      <h3>Candidates</h3>
      <ul>
        {evidence.candidates.map((candidate) => (
          <li key={candidate.action_id}>
            {candidate.action_id} propensity {candidate.propensity} predicted{" "}
            {String(candidate.predicted_reward)} eligible {String(candidate.eligible)}
          </li>
        ))}
      </ul>
    </div>
  );
}
