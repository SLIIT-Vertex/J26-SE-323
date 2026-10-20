// Sinhala wording for the learner-state camera in the child app (Grade 4–5, guardian settings).
// It describes the camera, never the child: no wording says a child is confused or not paying
// attention.

import type { VisualPipelineStatus } from "../useVisualFeatures";

export type CameraProblem = Extract<VisualPipelineStatus, { state: "error" }>["kind"];

/** Why the camera could not be used, for the guardian in settings. */
export const CAMERA_PROBLEM_SI: Record<CameraProblem, string> = {
	"permission-denied":
		"කැමරා අවසරය ලබා දී නැත. බ්‍රව්සරයේ හෝ දුරකථනයේ සැකසුම් වලින් අවසර දෙන්න.",
	"no-camera": "මෙම උපාංගයේ කැමරාවක් හමු නොවීය.",
	"camera-busy": "කැමරාව දැනට වෙනත් යෙදුමක් භාවිත කරයි.",
	"insecure-context": "කැමරාවට ආරක්ෂිත සම්බන්ධතාවක් (HTTPS) අවශ්‍යයි.",
	unsupported: "මෙම බ්‍රව්සරය හෝ උපාංගය කැමරාවට සහාය නොදක්වයි.",
	"model-load-failed": "කැමරා සැකසුම පූරණය කළ නොහැකි විය.",
	unknown: "කැමරාව ආරම්භ කළ නොහැකි විය.",
};

export const CAMERA_FALLBACK_SI = "ක්‍රීඩා කැමරාව නොමැතිව සාමාන්‍ය ලෙස ක්‍රියා කරයි.";

/** Short status shown in a game while the camera is enabled, or null when nothing is shown. */
export function cameraBadgeText(status: VisualPipelineStatus): string | null {
	switch (status.state) {
		case "requesting-permission":
			return "කැමරා අවසරය ඉල්ලමින්…";
		case "loading-model":
			return "කැමරාව සූදානම් වෙමින්…";
		case "running":
			return "කැමරාව ක්‍රියාත්මකයි";
		case "error":
			return "කැමරාව නැතිව ක්‍රීඩා කරමු";
		default:
			return null;
	}
}
