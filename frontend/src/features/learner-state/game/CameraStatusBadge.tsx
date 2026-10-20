// Small camera status in a game screen, so a child and guardian always see when the camera is on.
// It never blocks a tap (pointer-events: none) and is announced politely to screen readers.

import "./camera.css";

import type { VisualPipelineStatus } from "../useVisualFeatures";
import { cameraBadgeText } from "./cameraText";

export function CameraStatusBadge({ status }: { status: VisualPipelineStatus }) {
	const text = cameraBadgeText(status);
	if (text === null) return null;
	return (
		<div className={`camera-badge camera-badge--${status.state}`} role="status">
			<span className="camera-badge__dot" aria-hidden="true" />
			{text}
		</div>
	);
}
