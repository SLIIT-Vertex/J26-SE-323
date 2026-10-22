import { createContext, useContext, useMemo } from "react";
import { PhaserBoard } from "../phaser-board/PhaserBoard";
import { sceneFor } from "../phaser-board/scenes";
import type { BoardTarget } from "../phaser-board/types";

export const WordDropMotionContext = createContext(false);

export type WordCard = { id: string; label: string; emoji?: string };
export type WordTarget = {
	id: string;
	label: string;
	emoji?: string;
	visual?: string;
	count?: number;
	hint?: string;
};
export type WordLink = { source: string; target: string; sequence: number };
export type WordDropState = {
	links: WordLink[];
	trace: string[];
	usedTap: boolean;
	invalidDrops: number;
};
export function placeWord(
	links: WordLink[],
	source: string,
	target: string,
	single: boolean,
) {
	return [
		...links.filter(
			(link) => link.source !== source && (!single || link.target !== target),
		),
		{ source, target, sequence: 0 },
	].map((link, index) => ({ ...link, sequence: index + 1 }));
}

const PLANT_ROOT = "/curriculum/game/G5-AREA-ENG-03";
const YOUNG_PLANT = `${PLANT_ROOT}/plant-parts-young-plant.png`;
const TREE = `${PLANT_ROOT}/plant-parts-tree.png`;

/** Where each part sits on the two plant illustrations, in percent of the picture. */
const PLANT_POINTS: Record<string, { x: number; y: number; emoji?: string }> = {
	roots: { x: 52, y: 80 },
	stem: { x: 52, y: 55 },
	leaves: { x: 22, y: 42 },
	bud: { x: 72, y: 15 },
	petals: { x: 32, y: 24 },
	flowers: { x: 34, y: 20 },
	// The young plant is drawn without fruit, so its fruit marker carries one.
	fruit: { x: 80, y: 46, emoji: "🥭" },
};
const TREE_POINTS: Record<string, { x: number; y: number }> = {
	roots: { x: 50, y: 86 },
	trunk: { x: 52, y: 66 },
	branches: { x: 66, y: 40 },
	leaves: { x: 12, y: 40 },
	flowers: { x: 73, y: 18 },
	fruits: { x: 37, y: 32 },
};

/** The one-or-many plant photos the game already ships. */
const PLANT_PHOTOS = new Set(["leaf", "bud", "branch"]);

/**
 * The word-drop games (Plants and Food) on the shared Phaser board: drag or tap words onto
 * pictures, baskets, or the labelled parts of a plant illustration.
 */
export function WordDropBoard({
	cards,
	targets,
	onChange,
	instruction,
	single = true,
	theme = "garden",
	diagram,
	reducedMotion,
}: {
	cards: WordCard[];
	targets: WordTarget[];
	onChange(state: WordDropState): void;
	instruction: string;
	single?: boolean;
	theme?: "garden" | "market";
	diagram?: boolean | "tree";
	reducedMotion?: boolean;
}) {
	const motionSetting = useContext(WordDropMotionContext);
	const calm = reducedMotion ?? motionSetting;
	const tree = diagram === "tree";
	const boardCards = useMemo(
		() =>
			cards.map((card) => ({
				id: card.id,
				label: card.label,
				picture: card.emoji ? { emoji: card.emoji } : undefined,
			})),
		[cards],
	);
	const boardTargets = useMemo<BoardTarget[]>(
		() =>
			targets.map((target, index) => {
				if (diagram) {
					const key = (target.visual ?? "")
						.replace(/^plant-/, "")
						.replace(/-slot$/, "");
					const point = (tree ? TREE_POINTS : PLANT_POINTS)[key] ?? {
						x: 50,
						y: 50,
					};
					return {
						id: target.id,
						x: point.x,
						y: point.y,
						marker: String(index + 1),
						picture:
							"emoji" in point && typeof point.emoji === "string"
								? { emoji: point.emoji }
								: undefined,
					};
				}
				const many = (target.count ?? 1) > 1;
				const photo = target.visual && PLANT_PHOTOS.has(target.visual);
				return {
					id: target.id,
					// "Picture 1" says nothing a child needs; the picture speaks for itself.
					label: /^Picture \d+$/.test(target.label) ? undefined : target.label,
					capacity: single ? 1 : cards.length,
					picture: photo
						? {
								image: `${PLANT_ROOT}/${target.visual}-${many ? "multiple" : "single"}.png`,
							}
						: { emoji: target.emoji ?? "🧺" },
				};
			}),
		[targets, diagram, tree, single, cards.length],
	);
	return (
		<section className={`word-drop word-drop--${theme}`}>
			<PhaserBoard
				layout={diagram ? "hotspots" : single ? "grid" : "bins"}
				theme={theme === "market" ? "market" : "meadow"}
				scene={
					diagram
						? undefined
						: sceneFor(theme === "market" ? "G5-AREA-ENG-06" : "G5-AREA-ENG-03")
				}
				background={
					diagram
						? { image: tree ? TREE : YOUNG_PLANT, aspect: 1024 / 1536 }
						: undefined
				}
				cards={boardCards}
				targets={boardTargets}
				instruction={instruction}
				reducedMotion={calm}
				onChange={(state) =>
					onChange({
						links: state.links,
						trace: state.trace,
						usedTap: state.usedTap,
						invalidDrops: state.invalidDrops,
					})
				}
			/>
		</section>
	);
}
