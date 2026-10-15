import react from "@vitejs/plugin-react";

import { mediapipeTelemetryPlugin } from "./build-plugins/mediapipeTelemetry";

export default {
  plugins: [react(), mediapipeTelemetryPlugin()],
  // MediaPipe model files (learner-state face landmarker) are bundled as static assets.
  assetsInclude: ["**/*.task"],
  // Serve MediaPipe unbundled in development too, so the telemetry plugin always applies to it.
  optimizeDeps: { exclude: ["@mediapipe/tasks-vision"] },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx", "build-plugins/**/*.test.ts"],
    setupFiles: ["src/test/setup.ts"],
  },
};
