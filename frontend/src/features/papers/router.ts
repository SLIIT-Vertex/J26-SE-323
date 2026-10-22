import { useEffect, useMemo, useState } from "react";

// Hash routes, in the same style as the rest of the app: #/papers, #/papers/<id>, ...

export type Route =
  | { name: "papers" }
  | { name: "history" }
  | { name: "paper"; id: string }
  | { name: "report"; id: string }
  | { name: "review"; id: string }
  | { name: "mastery" };

const ID = "([0-9a-fA-F-]{36})";

/** The route for a hash, or null when the hash belongs to another part of the app. */
export function parseRoute(hash: string): Route | null {
  const path = hash.replace(/^#/, "").split("?")[0].replace(/\/+$/, "");
  if (path === "/papers") return { name: "papers" };
  if (path === "/mastery") return { name: "mastery" };
  if (path === "/history") return { name: "history" };
  const report = new RegExp(`^/papers/${ID}/report$`).exec(path);
  if (report) return { name: "report", id: report[1] };
  const paper = new RegExp(`^/papers/${ID}$`).exec(path);
  if (paper) return { name: "paper", id: paper[1] };
  const review = new RegExp(`^/review/${ID}$`).exec(path);
  if (review) return { name: "review", id: review[1] };
  return null;
}

export function hrefFor(route: Route): string {
  switch (route.name) {
    case "papers":
      return "#/papers";
    case "history":
      return "#/history";
    case "mastery":
      return "#/mastery";
    case "paper":
      return `#/papers/${route.id}`;
    case "report":
      return `#/papers/${route.id}/report`;
    case "review":
      return `#/review/${route.id}`;
  }
}

export function go(route: Route): void {
  window.location.hash = hrefFor(route);
}

export function usePapersRoute(): Route | null {
  const [hash, setHash] = useState(() => window.location.hash);
  useEffect(() => {
    const onChange = () => {
      setHash(window.location.hash);
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  // Stable per hash: callers use the route as an effect dependency, and a new object on every
  // render made them re-run mid-navigation (e.g. snapping a bottom-tab press back to papers).
  return useMemo(() => parseRoute(hash), [hash]);
}
