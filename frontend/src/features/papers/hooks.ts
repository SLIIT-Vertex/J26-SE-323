import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

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
export function useAsync<T>(
  load: () => Promise<T>,
  key: string,
): { state: Loaded<T>; reload: () => void } {
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
      .catch(
        (error: unknown) =>
          alive && setState({ status: "error", error, message: friendlyMessage(error) }),
      );
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
// There is no login yet, so the app remembers the chosen learner on this device.

const STORAGE_KEY = "mindbridge.learnerId";
let memory: string | null = null;
const listeners = new Set<() => void>();

export function getLearnerId(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return memory;
  }
}

export function setLearnerId(id: string | null): void {
  memory = id;
  try {
    if (id === null) window.localStorage.removeItem(STORAGE_KEY);
    else window.localStorage.setItem(STORAGE_KEY, id);
  } catch {
    // storage blocked: the choice lasts until the page is closed
  }
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

export function useLearnerId(): string | null {
  return useSyncExternalStore(subscribe, getLearnerId);
}

// ---- the page body ------------------------------------------------------------------------------

/** Adds a class to <body> while a screen is shown (the shared styles centre the body). */
export function useBodyClass(name: string): void {
  useEffect(() => {
    document.body.classList.add(name);
    return () => document.body.classList.remove(name);
  }, [name]);
}
