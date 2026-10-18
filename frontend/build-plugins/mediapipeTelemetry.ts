// @mediapipe/tasks-vision 1.0.1 always starts a usage logger that POSTs task type, running mode,
// platform, library version and timing statistics to Google about once a minute. No images or
// landmarks are included, but learner sessions should not contact outside servers, so the
// logging endpoint is replaced at build time with an address that fetch() rejects without any
// network access. MediaPipe then disables its logger after the first failed attempt.

import type { Plugin } from "vite";

export const MEDIAPIPE_TELEMETRY_URL = "https://odml.pa.googleapis.com/v1/log";

/** Unknown URL scheme: fetch() rejects it immediately, nothing is sent. */
export const DISABLED_TELEMETRY_URL = "mindbridge-disabled-telemetry:mediapipe";

const MEDIAPIPE_BUNDLE = /@mediapipe[\\/]tasks-vision[\\/]vision_bundle\.m?js$/;

/** Queries that turn a file into data instead of executable code. */
const NON_CODE_QUERY = /(^|&)(raw|url|inline)(=|&|$)/;

/**
 * Only the executable MediaPipe bundle, including the dev server's `?v=<hash>` form;
 * never `?raw`, `?url` or `?inline` copies, never other files.
 */
export function isMediapipeBundle(id: string): boolean {
  const [path, query = ""] = id.split("?", 2);
  return MEDIAPIPE_BUNDLE.test(path) && !NON_CODE_QUERY.test(query);
}

export function disableMediapipeTelemetry(code: string): { code: string; replaced: number } {
  const parts = code.split(MEDIAPIPE_TELEMETRY_URL);
  return { code: parts.join(DISABLED_TELEMETRY_URL), replaced: parts.length - 1 };
}

export function mediapipeTelemetryPlugin(): Plugin {
  const replacedPerModule = new Map<string, number>();

  return {
    name: "mindbridge:disable-mediapipe-telemetry",
    enforce: "pre",
    transform(code, id) {
      if (!isMediapipeBundle(id)) return null;
      const result = disableMediapipeTelemetry(code);
      replacedPerModule.set(id, result.replaced);
      return { code: result.code, map: null };
    },
    buildEnd() {
      for (const [id, replaced] of replacedPerModule) {
        if (replaced !== 1) {
          this.error(
            `Expected exactly one MediaPipe telemetry URL in ${id}, found ${replaced}. ` +
              "Check the logger after changing the @mediapipe/tasks-vision version.",
          );
        }
      }
    },
  };
}
