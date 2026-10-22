/** A picture for a card or target: an emoji drawn large, or a curriculum image. */
export type BoardPicture = {
	emoji?: string;
	image?: string;
	/** Width over height of the image; a hotspot picture is laid out to exactly this shape. */
	aspect?: number;
};

/** Something the child moves: a word, phrase or tile. */
export type BoardCard = { id: string; label: string; picture?: BoardPicture };

/** Somewhere a card goes. */
export type BoardTarget = {
	id: string;
	/** Text on the target. Leave it out when the text would give the answer away. */
	label?: string;
	picture?: BoardPicture;
	/** How many cards it takes. One replaces the previous card; more collect a group. */
	capacity?: number;
	/** Hotspots only: where the marker sits on the picture, in percent. */
	x?: number;
	y?: number;
	/** Hotspots only: the number on the marker. */
	marker?: string;
};

/**
 * - `grid`: picture cards to match, one word each.
 * - `bins`: headings or baskets that collect several words.
 * - `slots`: an ordered row, for building a name, a question or a dialogue.
 * - `hotspots`: numbered markers on one big picture (an elephant's body parts).
 */
export type BoardLayout = "grid" | "bins" | "slots" | "hotspots";

export type BoardLink = { source: string; target: string; sequence: number };

export type BoardState = {
	links: BoardLink[];
	trace: string[];
	usedTap: boolean;
	invalidDrops: number;
};

export const EMPTY_BOARD: BoardState = {
	links: [],
	trace: [],
	usedTap: false,
	invalidDrops: 0,
};

/** Place a card, keeping each target within its capacity and each card in one place. */
export function placeCard(
	links: BoardLink[],
	source: string,
	target: string,
	capacity: number,
): BoardLink[] {
	const others = links.filter((link) => link.source !== source);
	const inTarget = others.filter((link) => link.target === target);
	// A full target gives up its oldest card to make room.
	const evicted =
		inTarget.length >= capacity
			? new Set(
					inTarget
						.slice(0, inTarget.length - capacity + 1)
						.map((l) => l.source),
				)
			: new Set<string>();
	return [
		...others.filter((link) => !evicted.has(link.source)),
		{ source, target, sequence: 0 },
	].map((link, index) => ({ ...link, sequence: index + 1 }));
}

export function removeCard(links: BoardLink[], source: string): BoardLink[] {
	return links
		.filter((link) => link.source !== source)
		.map((link, index) => ({ ...link, sequence: index + 1 }));
}

/** Slots in their order, each with the card placed in it (or null). */
export function slotOrder(
	links: BoardLink[],
	slots: readonly { id: string }[],
): (string | null)[] {
	return slots.map(
		(slot) => links.find((link) => link.target === slot.id)?.source ?? null,
	);
}
