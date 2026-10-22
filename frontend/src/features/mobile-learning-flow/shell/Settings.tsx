// biome-ignore-all lint/a11y/useButtonType: this application contains no HTML forms; all buttons are application actions.

import { CameraConsentCard } from "../../learner-state/game/CameraConsentCard";
import type { CameraProblem } from "../../learner-state/game/cameraText";
import { Back } from "./common";

export type SyncState = "synced" | "pending" | "offline" | "conflict";
export const labels: Record<SyncState, string> = {
	synced: "සමමුහුර්තයි",
	pending: "සමමුහුර්ත වෙමින්",
	offline: "අන්තර්ජාලය නොමැත",
	conflict: "නැවත සම්බන්ධ කිරීම අවශ්‍යයි",
};

export function Settings({
	syncState,
	onSync,
	reducedMotion,
	setReducedMotion,
	cameraConsent,
	cameraConsentSaving,
	cameraConsentFailed,
	cameraProblem,
	onCameraConsent,
	onBack,
}: {
	syncState: SyncState;
	onSync(): void;
	reducedMotion: boolean;
	setReducedMotion(value: boolean): void;
	cameraConsent: boolean;
	cameraConsentSaving: boolean;
	cameraConsentFailed: boolean;
	cameraProblem: CameraProblem | null;
	onCameraConsent(granted: boolean): void;
	onBack(): void;
}) {
	return (
		<section>
			<Back onClick={onBack} />
			<p className="eyebrow">වැඩිහිටි සැකසුම්</p>
			<h1>යෙදුම් තත්ත්වය</h1>
			<label className="toggle">
				<input
					type="checkbox"
					checked={reducedMotion}
					onChange={(event) => setReducedMotion(event.target.checked)}
				/>{" "}
				චලනය අඩු කරන්න
			</label>
			<CameraConsentCard
				granted={cameraConsent}
				saving={cameraConsentSaving}
				saveFailed={cameraConsentFailed}
				problem={cameraProblem}
				onChange={onCameraConsent}
			/>
			<p role="status">
				සමමුහුර්ත තත්ත්වය: <strong>{labels[syncState]}</strong>
			</p>
			<button className="secondary-action" onClick={onSync}>
				දැන් සමමුහුර්ත කරන්න
			</button>
		</section>
	);
}
export function Failure({
	code,
	onSafePractice,
}: {
	code: string;
	onSafePractice(): void;
}) {
	const copy = code.includes("AUTH")
		? "පැතිකඩ තහවුරු කළ නොහැක."
		: code.includes("CONTENT") || code.includes("APPROVAL")
			? "මෙම ඉගෙනුම් අන්තර්ගතය තවම ලබා දිය නොහැක."
			: code.includes("SEQUENCE") || code.includes("CONTAMINATED")
				? "මෙම උත්සාහය ප්‍රගති සාක්ෂියක් ලෙස භාවිතා නොවේ."
				: "දැන් සේවාවට සම්බන්ධ විය නොහැක.";
	return (
		<section className="center-screen" data-failure-code={code}>
			<div className="mascot" aria-hidden="true">
				☁
			</div>
			<h1>මොහොතක් රැඳී සිටිමු</h1>
			<p>{copy}</p>
			<p>ආරක්ෂිත පුහුණුවට ආපසු යා හැක. මෙය නිල ප්‍රගති ප්‍රතිඵලයක් නොවේ.</p>
			<button className="primary-action" onClick={onSafePractice}>
				මුල් පිටුවට
			</button>
		</section>
	);
}
