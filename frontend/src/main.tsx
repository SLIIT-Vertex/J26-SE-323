import { Capacitor } from "@capacitor/core";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { lockOrientation } from "./features/mobile-learning-flow/landscape/orientation";
import "./styles.css";
import "./features/mobile-learning-flow/navigation-refresh.css";
import "./features/mobile-learning-flow/game-play-surface.css";

const root = document.getElementById("root");
if (!root) throw new Error("Missing #root element");

// The phone apps allow landscape for full-screen games only; everything else stays portrait.
if (Capacitor.isNativePlatform()) void lockOrientation("portrait");

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
