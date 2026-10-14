import { useEffect, useRef } from "react";

import type { ManifestView } from "../../../api/generated";
import { GameEventBridge } from "../../bridge/GameEventBridge";
import { createFractionBarGame } from "../../createGame";
import { BuildManipulateSceneController } from "./sceneController";

type BuildManipulateProps = {
  manifest: ManifestView;
  reducedMotion: boolean;
  onSelect: (optionId: string) => void;
};

export function BuildManipulate({ manifest, reducedMotion, onSelect }: BuildManipulateProps) {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const parent = host.current;
    if (!parent) return;
    const bridge = new GameEventBridge();
    const controller = new BuildManipulateSceneController(bridge);
    controller.apply({ type: "LOAD_MANIFEST", manifest });
    const game = createFractionBarGame(parent, controller, manifest, reducedMotion);
    const unsubscribe = bridge.subscribe((event) => onSelect(event.optionId));
    return () => {
      controller.apply({ type: "DISPOSE" });
      unsubscribe();
      game.destroy(true);
    };
  }, [manifest, onSelect, reducedMotion]);

  return <div ref={host} className={reducedMotion ? "reduced-motion" : undefined} />;
}
