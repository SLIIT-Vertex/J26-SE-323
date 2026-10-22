import { useEffect, useRef, useState } from "react";
import type { SceneGameOptions } from "./createGame";

/**
 * Hosts one Phaser scene inside React. React keeps the DOM controls; the canvas is a mirror
 * and an extra input surface. The scene is created lazily and destroyed with every object,
 * timer, tween and listener when the surface unmounts or its key changes.
 */
export function PhaserSurface({
	scene,
	options,
	label,
	className,
	onReady,
}: {
	scene: () => Promise<import("phaser").Types.Scenes.SceneType>;
	options: SceneGameOptions;
	label: string;
	className?: string;
	onReady?(game: import("phaser").Game | null): void;
}) {
	const host = useRef<HTMLDivElement>(null);
	const [failed, setFailed] = useState(false);
	const ready = useRef(onReady);
	ready.current = onReady;
	// biome-ignore lint/correctness/useExhaustiveDependencies: a new scene needs a new surface key.
	useEffect(() => {
		const parent = host.current;
		if (!parent) return;
		let disposed = false;
		let game: import("phaser").Game | null = null;
		void (async () => {
			try {
				const [{ createSceneGame }, factory] = await Promise.all([
					import("./createGame"),
					scene(),
				]);
				if (disposed) return;
				game = await createSceneGame(parent, factory, options);
				if (disposed) game.destroy(true);
				else ready.current?.(game);
			} catch {
				// The accessible DOM controls remain fully usable without the canvas.
				setFailed(true);
			}
		})();
		return () => {
			disposed = true;
			ready.current?.(null);
			game?.destroy(true);
			game = null;
		};
	}, []);
	return (
		<div
			className={className}
			ref={host}
			aria-hidden="true"
			data-phaser-surface={failed ? "unavailable" : "active"}
			title={label}
		/>
	);
}
