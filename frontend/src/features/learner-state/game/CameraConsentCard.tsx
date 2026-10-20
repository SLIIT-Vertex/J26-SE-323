// The guardian's camera decision in settings: what the camera does, what it never does, and why
// it may not be working.

import "./camera.css";

import { CAMERA_FALLBACK_SI, CAMERA_PROBLEM_SI, type CameraProblem } from "./cameraText";

export function CameraConsentCard({
	granted,
	saving,
	saveFailed,
	problem,
	onChange,
}: {
	granted: boolean;
	saving: boolean;
	saveFailed: boolean;
	/** The last camera problem in a game, if any. */
	problem: CameraProblem | null;
	onChange(granted: boolean): void;
}) {
	return (
		<section className="camera-consent-card" aria-labelledby="camera-consent-title">
			<p className="eyebrow">වැඩිහිටියෙකු සඳහා</p>
			<h2 id="camera-consent-title">ඉගෙනුම් කැමරාව</h2>
			<label className="camera-consent-switch">
				<input
					type="checkbox"
					role="switch"
					aria-checked={granted}
					aria-describedby="camera-consent-facts"
					checked={granted}
					disabled={saving}
					onChange={(event) => onChange(event.target.checked)}
				/>
				<span>ඉගෙනීමට උදව් වීමට කැමරාව භාවිත කරන්න</span>
			</label>
			<ul className="camera-consent-facts" id="camera-consent-facts">
				<li>ගණිත ක්‍රීඩා අතරතුර පමණක් ක්‍රියාත්මක වේ.</li>
				<li>කැමරා රූප මෙම උපාංගයෙන් පිටතට නොයයි; ගබඩා කරන්නේද නැත.</li>
				<li>ඇස් සහ හිසෙහි පිහිටීම පිළිබඳ අංක 11ක් පමණක් පිළිතුරු සමඟ යවයි.</li>
				<li>මුහුණ හඳුනා ගැනීමක් සිදු නොකෙරේ.</li>
				<li>ඕනෑම වේලාවක මෙය අක්‍රිය කළ හැක.</li>
			</ul>
			{saveFailed ? (
				<p className="camera-consent-message camera-consent-message--error" role="alert">
					තේරීම සුරැකීමට නොහැකි විය. සම්බන්ධතාව පරීක්ෂා කර නැවත උත්සාහ කරන්න.
				</p>
			) : null}
			{granted && problem ? (
				<p className="camera-consent-message" role="status">
					{CAMERA_PROBLEM_SI[problem]} {CAMERA_FALLBACK_SI}
				</p>
			) : null}
		</section>
	);
}
