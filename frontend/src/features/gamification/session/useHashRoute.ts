import { useEffect, useState } from "react";

export type ShellRoute = "home" | "play" | "inspector" | "build" | "tutor";

export function useHashRoute(): ShellRoute {
  const [hash, setHash] = useState(() => window.location.hash);
  useEffect(() => {
    const onChange = () => setHash(window.location.hash);
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  if (hash.startsWith("#/play")) return "play";
  if (hash.startsWith("#/inspector")) return "inspector";
  if (hash.startsWith("#/build")) return "build";
  if (hash.startsWith("#/tutor")) return "tutor";
  return "home";
}
