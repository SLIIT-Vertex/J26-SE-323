import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, friendlyMessage } from "./api";

// ---- loading data ------------------------------------------------------------------------------

export type Loaded<T> =
  | { status: "loading" }
  | { status: "ready"; data: T }
  | { status: "error"; error: unknown; message: string };

/**
 * Runs `load` again whenever `key` changes (or `reload` is called). While reloading, data that
 * was already shown stays on screen, so a refresh does not flash the page empty.
 */
export function useAsync<T>(load: () => Promise<T>, key: string): { state: Loaded<T>; reload: () => void } {
  const loadRef = useRef(load);
  loadRef.current = load;
  const [state, setState] = useState<Loaded<T>>({ status: "loading" });
  const [tick, setTick] = useState(0);

  // biome-ignore lint/correctness/useExhaustiveDependencies: `key` and `tick` are what restart the load
  useEffect(() => {
    let alive = true;
    setState((now) => (now.status === "ready" ? now : { status: "loading" }));
    loadRef
      .current()
      .then((data) => alive && setState({ status: "ready", data }))
      .catch((error: unknown) => alive && setState({ status: "error", error, message: friendlyMessage(error) }));
    return () => {
      alive = false;
    };
  }, [key, tick]);

  const reload = useCallback(() => setTick((n) => n + 1), []);
  return { state, reload };
}

/** Calls `callback` every `ms` milliseconds, or never when `ms` is null. */
export function useInterval(callback: () => void, ms: number | null): void {
  const saved = useRef(callback);
  saved.current = callback;
  useEffect(() => {
    if (ms === null) return;
    const id = window.setInterval(() => saved.current(), ms);
    return () => window.clearInterval(id);
  }, [ms]);
}

export function isNotFound(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}

// ---- which child is using the app ---------------------------------------------------------------
// There is no login or user management yet, so the practice screens and the game share ONE
// development learner. A child's game answers and paper answers then belong to the same learner.
// This is the same setting and the same default as the game (MobileLearningApp), so changing
// VITE_MOBILE_LEARNING_LEARNER_ID switches both at once. Once there is a login, both should take
// the signed-in child's id instead.

export const DEFAULT_SHARED_LEARNER_ID = "00000000-0000-4000-8000-000000000721";

export const SHARED_LEARNER_ID: string = import.meta.env.VITE_MOBILE_LEARNING_LEARNER_ID ?? DEFAULT_SHARED_LEARNER_ID;

export function useLearnerId(): string {
  return SHARED_LEARNER_ID;
}

// ---- the page body ------------------------------------------------------------------------------

/** Adds a class to <body> while a screen is shown (the shared styles centre the body). */
export function useBodyClass(name: string): void {
  useEffect(() => {
    document.body.classList.add(name);
    return () => document.body.classList.remove(name);
  }, [name]);
}
