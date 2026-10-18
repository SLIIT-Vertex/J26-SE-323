import { afterEach, beforeEach } from "vitest";

import { setLanguage } from "../features/papers/i18n";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

// the practice screens default to Sinhala; the existing assertions read English
beforeEach(() => {
  setLanguage("en", { remember: false });
});

afterEach(() => {
  document.body.replaceChildren();
  localStorage.clear();
  sessionStorage.clear();
  window.location.hash = "";
});

if (!globalThis.crypto?.randomUUID) {
  Object.defineProperty(globalThis, "crypto", {
    value: { randomUUID: () => "00000000-0000-4000-8000-000000000001" },
  });
}
