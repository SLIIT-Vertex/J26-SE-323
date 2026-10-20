import { type ResearchTutorApi, researchTutorApi } from "./api";
import { ResearchInteraction } from "./ResearchInteraction";

/** Adaptive Tutor entry point: the local research chat, standalone or inside the learner shell. */
export function TutorDemo({
  api = researchTutorApi,
  embedded = false,
}: {
  api?: ResearchTutorApi;
  embedded?: boolean;
}) {
  const workspace = (
    <div className="tutor-workspace">
      <ResearchInteraction api={api} standalone={!embedded} />
    </div>
  );

  return embedded ? workspace : <main className="mobile-shell tutor-shell">{workspace}</main>;
}
