const STORAGE_KEY = "mindbridge.research";

/**
 * The research dashboard shows model internals and answers, so it is never on in a child-facing
 * build: only in development, in a researcher build (`VITE_RESEARCH_MODE=1`, e.g. for the iOS
 * simulator, which has no address bar), with `?research=1`, or after a researcher turned it on.
 */
export function isResearchMode(): boolean {
	if (import.meta.env.DEV) return true;
	if (import.meta.env.VITE_RESEARCH_MODE === "1") return true;
	if (new URLSearchParams(window.location.search).get("research") === "1") {
		remember(true);
		return true;
	}
	try {
		return window.localStorage.getItem(STORAGE_KEY) === "1";
	} catch {
		return false;
	}
}

function remember(on: boolean) {
	try {
		if (on) window.localStorage.setItem(STORAGE_KEY, "1");
		else window.localStorage.removeItem(STORAGE_KEY);
	} catch {
		// Storage can be unavailable (private mode); the URL flag still works for this visit.
	}
}
