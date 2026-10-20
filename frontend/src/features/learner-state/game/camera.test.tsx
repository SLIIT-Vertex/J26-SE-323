import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { VisualPipelineStatus } from "../useVisualFeatures";
import { CameraConsentCard } from "./CameraConsentCard";
import { CameraStatusBadge } from "./CameraStatusBadge";
import { CAMERA_FALLBACK_SI, CAMERA_PROBLEM_SI } from "./cameraText";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
	host = document.createElement("div");
	document.body.append(host);
	root = createRoot(host);
});

afterEach(() => {
	act(() => root.unmount());
	host.remove();
});

describe("CameraStatusBadge", () => {
	it.each([
		[{ state: "requesting-permission" }, "කැමරා අවසරය ඉල්ලමින්…"],
		[{ state: "loading-model" }, "කැමරාව සූදානම් වෙමින්…"],
		[{ state: "running" }, "කැමරාව ක්‍රියාත්මකයි"],
		[{ state: "error", kind: "permission-denied" }, "කැමරාව නැතිව ක්‍රීඩා කරමු"],
	] as [VisualPipelineStatus, string][])("shows %o politely", (status, text) => {
		act(() => root.render(<CameraStatusBadge status={status} />));

		const badge = host.querySelector('[role="status"]');
		expect(badge?.textContent).toBe(text);
		expect(badge?.className).toContain(`camera-badge--${status.state}`);
	});

	it.each([[{ state: "idle" }], [{ state: "stopped" }]] as [VisualPipelineStatus][])(
		"shows nothing when the camera is %o",
		(status) => {
			act(() => root.render(<CameraStatusBadge status={status} />));
			expect(host.innerHTML).toBe("");
		},
	);
});

describe("CameraConsentCard", () => {
	function render(props: Partial<Parameters<typeof CameraConsentCard>[0]> = {}) {
		const onChange = vi.fn();
		act(() =>
			root.render(
				<CameraConsentCard
					granted={false}
					saving={false}
					saveFailed={false}
					problem={null}
					onChange={onChange}
					{...props}
				/>,
			),
		);
		const toggle = host.querySelector<HTMLInputElement>('input[role="switch"]');
		if (!toggle) throw new Error("camera switch missing");
		return { onChange, toggle };
	}

	it("explains the camera and reports the guardian's choice", () => {
		const { onChange, toggle } = render();

		expect(toggle.checked).toBe(false);
		expect(host.querySelectorAll(".camera-consent-facts li")).toHaveLength(5);
		expect(host.textContent).toContain("පිටතට නොයයි");
		act(() => toggle.click());
		expect(onChange).toHaveBeenCalledWith(true);
	});

	it("cannot be changed while the choice is being saved", () => {
		const { toggle } = render({ saving: true });
		expect(toggle.disabled).toBe(true);
	});

	it("says when the choice could not be saved", () => {
		render({ saveFailed: true });
		expect(host.querySelector('[role="alert"]')?.textContent).toContain("සුරැකීමට නොහැකි");
	});

	it("explains a camera problem only while the camera is allowed", () => {
		render({ granted: true, problem: "permission-denied" });
		expect(host.textContent).toContain(CAMERA_PROBLEM_SI["permission-denied"]);
		expect(host.textContent).toContain(CAMERA_FALLBACK_SI);

		render({ granted: false, problem: "permission-denied" });
		expect(host.textContent).not.toContain(CAMERA_PROBLEM_SI["permission-denied"]);
	});
});
