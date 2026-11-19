import { useEffect, useRef, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { MissionOutcome } from "../../../mobile-learning-flow/landscape/useHardFirstEpisode";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { SNACK_ART } from "./cafeArt";
import {
	Art,
	DigitPad,
	type MonsterMood,
	Monsters,
	OrderBoard,
	StoryPick,
} from "./cafeParts";
import {
	type CafeOrder,
	cafeResponse,
	canOpen,
	digitsOf,
	operands,
	type Source,
} from "./cafeRules";
import { cafeSounds } from "./cafeSounds";

type Ticket = {
	top: Source | null;
	opens: number[];
	digits: Array<number | null>;
};

const emptyTicket = (width: number): Ticket => ({
	top: null,
	opens: [],
	digits: Array.from({ length: width }, () => null),
});

/**
 * Monster Order Mayhem: the café order board. The child opens packs where a column has too few
 * snacks (like writing a borrow mark), then fills in what is left, column by column. For a
 * two-monster order the child first puts the bigger order on top. Nothing on the board says right
 * or wrong; the monsters react only after the order is sent.
 */
export function MonsterOrderMission({
	order,
	prompt,
	returning,
	outcome,
	busy,
	evidence,
	onSubmit,
}: {
	order: CafeOrder;
	prompt: string;
	returning: boolean;
	outcome: MissionOutcome;
	busy: boolean;
	evidence: ReturnType<typeof useMoveEvidence>;
	onSubmit(response: ConstructedResponse): void;
}) {
	const width = order.places.length;
	const [ticket, setTicketState] = useState<Ticket>(() => emptyTicket(width));
	const current = useRef(ticket);
	const setTicket = (next: Ticket) => {
		current.current = next;
		setTicketState(next);
	};
	const [selected, setSelectedState] = useState<number>(width - 1);
	const picked = useRef(width - 1);
	const setSelected = (column: number) => {
		picked.current = column;
		setSelectedState(column);
	};
	const playing = outcome === "playing";
	const numbers = operands(order, ticket.top);
	const response = cafeResponse(order, ticket.top, ticket.digits, ticket.opens);
	const [mood, setMood] = useState<MonsterMood>("idle");

	useEffect(() => {
		if (outcome === "correct") setMood("happy");
		if (outcome === "wrong") setMood("puzzled");
	}, [outcome]);

	const pickTop = (source: Source) => {
		if (!playing) return;
		cafeSounds.play("pick");
		evidence.note("move");
		// Swapping the orders starts the working again: the columns change.
		setTicket({ ...emptyTicket(width), top: source });
		setSelected(width - 1);
	};
	const toggleOpen = (column: number) => {
		const now = current.current;
		if (!playing || !numbers) return;
		const opened = now.opens.includes(column);
		if (!opened && !canOpen(digitsOf(numbers.top, width), now.opens, column)) {
			cafeSounds.play("boing");
			return;
		}
		evidence.note("carry");
		cafeSounds.play(opened ? "back" : "unwrap");
		setTicket({
			...now,
			opens: opened
				? now.opens.filter((at) => at !== column)
				: [...now.opens, column],
		});
	};
	const enterDigit = (digit: number) => {
		if (!playing) return;
		const now = current.current;
		const column = picked.current;
		evidence.note("digit", column);
		cafeSounds.play("digit");
		const digits = [...now.digits];
		digits[column] = digit;
		setTicket({ ...now, digits });
		// Work from the ones leftwards: the next empty column to the left, if any.
		const next = digits.slice(0, column).lastIndexOf(null);
		if (next !== -1) setSelected(next);
	};
	const startOver = () => {
		if (!playing) return;
		cafeSounds.play("back");
		setTicket({ ...emptyTicket(width), top: current.current.top });
		setSelected(width - 1);
	};

	const story = order.story;
	const instruction =
		outcome === "correct"
			? "නියමයි! රාක්ෂයෝ සතුටින් නටනවා!"
			: outcome === "wrong"
				? "අපොයි! ගණන ටිකක් පැටලුණා."
				: story && !ticket.top
					? "කාගේ ඇණවුම ලොකුද? ඒක උඩට දාන්න!"
					: prompt;
	const labels = story
		? {
				top:
					story.quantities.find((row) => row.source === ticket.top)?.label ??
					"?",
				bottom:
					story.quantities.find((row) => row.source !== ticket.top)?.label ??
					"?",
			}
		: { top: "තිබුණා", bottom: "කෑවා" };

	return (
		<div className="cafe-orders" data-outcome={outcome}>
			<p className="cafe-scroll" role="status">
				{returning && playing ? "අලුත් ඇණවුමක්! " : ""}
				{instruction}
			</p>
			<Art art="nimoChef" className="cafe-nimo" />
			<Monsters mood={mood} />
			<div className="cafe-ticket">
				<span className="cafe-ticket-snack" aria-hidden="true">
					<Art art={SNACK_ART[order.snack]} />
				</span>
				<StoryPick
					order={order}
					top={ticket.top}
					disabled={!playing}
					onPick={pickTop}
				/>
				<OrderBoard
					places={order.places}
					top={numbers?.top ?? null}
					bottom={numbers?.bottom ?? null}
					topLabel={story ? labels.top : "තිබුණා"}
					bottomLabel={story ? labels.bottom : "කෑවා"}
					opens={ticket.opens}
					digits={ticket.digits}
					selected={playing ? selected : null}
					disabled={!playing || !numbers}
					onOpen={toggleOpen}
					onSelect={(column) => {
						cafeSounds.play("tap");
						setSelected(column);
					}}
				/>
			</div>
			<DigitPad disabled={!playing || !numbers} onDigit={enterDigit} />
			<div className="cafe-actions">
				<button
					type="button"
					className="cafe-again"
					disabled={
						!playing ||
						(ticket.opens.length === 0 &&
							ticket.digits.every((digit) => digit === null))
					}
					onClick={startOver}
				>
					↺ මුල ඉඳන්
				</button>
				<button
					type="button"
					className="game-action cafe-send"
					disabled={busy || !response || !playing}
					onClick={() => {
						if (!response) return;
						cafeSounds.play("shelf");
						onSubmit(response);
					}}
				>
					{story ? "ඇණවුම යවමු!" : "රාක්කයට යවමු!"}
				</button>
			</div>
		</div>
	);
}
