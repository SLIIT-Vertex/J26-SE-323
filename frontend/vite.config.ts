import react from "@vitejs/plugin-react";

import { mediapipeTelemetryPlugin } from "./build-plugins/mediapipeTelemetry.ts";

export default {
	plugins: [react(), mediapipeTelemetryPlugin()],
	// MediaPipe model files (learner-state face landmarker) are bundled as static assets.
	assetsInclude: ["**/*.task"],
	// Serve MediaPipe unbundled in development too, so the telemetry plugin always applies to it.
	optimizeDeps: { exclude: ["@mediapipe/tasks-vision"] },
	build: {
		// Phaser is already an on-demand vendor chunk (~1.19 MB minified, ~318 kB gzip).
		// Keep the limit just above that intentional boundary while warning on app regressions.
		chunkSizeWarningLimit: 1_200,
	},
	test: {
		environment: "jsdom",
		include: [
			"src/**/*.test.ts",
			"src/**/*.test.tsx",
			"build-plugins/**/*.test.ts",
		],
		setupFiles: ["src/test/setup.ts"],
	},
};
