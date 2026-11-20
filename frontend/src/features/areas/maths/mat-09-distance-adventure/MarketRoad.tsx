import { type PointerEvent, useRef, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { MissionOutcome } from "../../../mobile-learning-flow/landscape/useHardFirstEpisode";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import {
	type BoardDigits,
	DistanceBoard,
	emptyDigits,
	workingOf,
} from "./DistanceBoard";
import { Art, DistanceTag } from "./villageParts";
import {
	type Distance,
	type Operation,
	roadResponse,
	type VillageTask,
} from "./villageRules";
import { villageSounds } from "./villageSounds";

type Slot = "a" | "b";
type Piece = { slot: Slot; distance: Distance };

/** Joining roads: both pieces go on the map. What's left: Nimo walked the first piece already. */
function piecesOf(task: VillageTask): Piece[] {
	return task.operation === "add"
		? [
				{ slot: "b", distance: task.right },
				{ slot: "a", distance: task.left },
			]
		: [{ slot: "a", distance: task.right }];
}

const PLACES = [
	{ id: "home", name: "ගෙදර" },
	{ id: "shop", name: "කඩේ" },
	{ id: "market", name: "පොළ" },
] as const;

/**
 * අපේ පොළට යමු! The village map shows home, the little shop and the market; road pieces wait
 * at the bottom. The child drags (or taps) each piece onto the gap of the same shape, then works
 * out the distance on the wooden board, metres first. Nothing is checked until Nimo walks: he
 * reaches the market, or stops on the road and scratches his head.
 */
export function MarketRoad({
	task,
	prompt,
	returning,
	outcome,
	busy,
	evidence,
	onSubmit,
}: {
	task: VillageTask;
	prompt: string;
	returning: boolean;
	outcome: MissionOutcome;
	busy: boolean;
	evidence: ReturnType<typeof useMoveEvidence>;
	onSubmit(response: ConstructedResponse): void;
}) {
	const pieces = piecesOf(task);
	const [placed, setPlaced] = useState<Slot[]>([]);
	const [missed, setMissed] = useState<Slot | null>(null);
	const [chosen, setChosen] = useState<Operation | null>(
		task.kind === "story" ? null : task.operation,
	);
	const [digits, setDigits] = useState<BoardDigits>(() =>
		emptyDigits(task.operation),
	);
	const [exchanged, setExchanged] = useState(false);
	const [touched, setTouched] = useState(false);
	const [drag, setDrag] = useState<{ slot: Slot; x: number; y: number } | null>(
		null,
	);
	const start = useRef<{ x: number; y: number; moved: boolean } | null>(null);
	const slots = useRef<Partial<Record<Slot, HTMLDivElement | null>>>({});
	const playing = outcome === "playing";
	const roadDone = placed.length === pieces.length;
	const operation = chosen ?? task.operation;
	const nimo =
		outcome === "correct"
			? "nimoCheer"
			: outcome === "wrong"
				? "nimoThink"
				: "nimoIdle";

	const place = (slot: Slot, target: Slot | null) => {
		if (!playing || placed.includes(slot)) return;
		evidence.note("move");
		if (target !== null && target !== slot) {
			villageSounds.play("boing");
			setMissed(target);
			return;
		}
		villageSounds.play("place");
		setMissed(null);
		setPlaced([...placed, slot]);
	};
	const slotUnder = (x: number, y: number): Slot | null => {
		for (const slot of ["a", "b"] as const) {
			const box = slots.current[slot]?.getBoundingClientRect();
			if (
				box &&
				x >= box.left &&
				x <= box.right &&
				y >= box.top &&
				y <= box.bottom
			)
				return slot;
		}
		return null;
	};
	const grab = (slot: Slot) => ({
		onPointerDown: (event: PointerEvent<HTMLButtonElement>) => {
			if (!playing) return;
			event.currentTarget.setPointerCapture?.(event.pointerId);
			start.current = { x: event.clientX, y: event.clientY, moved: false };
			villageSounds.play("pick");
		},
		onPointerMove: (event: PointerEvent<HTMLButtonElement>) => {
			const from = start.current;
			if (!from) return;
			const x = event.clientX - from.x;
			const y = event.clientY - from.y;
			if (Math.hypot(x, y) > 8) from.moved = true;
			if (from.moved) setDrag({ slot, x, y });
		},
		onPointerUp: (event: PointerEvent<HTMLButtonElement>) => {
			const from = start.current;
			setDrag(null);
			if (!from?.moved) return;
			const target = slotUnder(event.clientX, event.clientY);
			if (target) place(slot, target);
		},
		onClick: () => {
			// A tap (no drag) sends the piece to its own gap; the click after a drag is ignored.
			const dragged = start.current?.moved;
			start.current = null;
			if (!dragged) place(slot, null);
		},
	});

	const instruction =
		outcome === "correct"
			? "හරියටම හරි! දැන් පොළට යමු!"
			: outcome === "wrong"
				? "අපොයි! පාරේ දුර පැටලුණා."
				: `${returning ? "අලුත් ගමනක්! " : ""}${prompt}`;
	const boardTitle =
		operation === "add" ? "පොළට යන්න මුළු දුර කීයද?" : "පොළට තව කීයද?";
	const remaining = pieces.length === 1;

	return (
		<div
			className="market-road"
			data-outcome={outcome}
			data-road-done={roadDone || undefined}
		>
			<p className="village-scroll" role="status">
				{instruction}
			</p>
			<div className="village-map">
				{PLACES.map(({ id, name }) => (
					<span key={id} className="map-place" data-place={id}>
						<Art art="placeNode" className="map-node" />
						<span className="map-pin">📍 {name}</span>
					</span>
				))}
				{remaining && (
					<span className="route-sign">
						ගෙදර → පොළ: <DistanceTag km={task.left.km} m={task.left.m} />
					</span>
				)}
				{(["a", "b"] as const).map((slot) => {
					const piece = pieces.find((item) => item.slot === slot);
					const filled = placed.includes(slot);
					return (
						<div
							key={slot}
							ref={(element) => {
								slots.current[slot] = element;
							}}
							className="road-slot"
							data-slot={slot}
							data-filled={filled || !piece || undefined}
							data-missed={missed === slot || undefined}
							onAnimationEnd={() => setMissed(null)}
						>
							{piece ? (
								filled && (
									<>
										<Art
											art={slot === "a" ? "roadStraight" : "roadBend"}
											className="road-art"
										/>
										<DistanceTag km={piece.distance.km} m={piece.distance.m} />
									</>
								)
							) : (
								<span className="road-unknown">?</span>
							)}
						</div>
					);
				})}
				<Art art={nimo} className="map-nimo" />
			</div>
			<div className="piece-tray">
				{!roadDone && <small>පාර කෑලි එකතු කරලා පොළට යමු!</small>}
				{pieces.map(({ slot, distance }, at) =>
					placed.includes(slot) ? null : (
						<button
							key={slot}
							type="button"
							className="road-piece"
							data-slot={slot}
							data-dragging={drag?.slot === slot || undefined}
							style={
								drag?.slot === slot
									? { transform: `translate(${drag.x}px, ${drag.y}px)` }
									: undefined
							}
							aria-label={`පාර කෑල්ල ${distance.km} km ${distance.m} m`}
							{...grab(slot)}
						>
							<Art
								art={slot === "a" ? "roadStraight" : "roadBend"}
								className="road-art"
							/>
							<DistanceTag km={distance.km} m={distance.m} />
							{placed.length === 0 && at === 0 && (
								<span className="road-hand" aria-hidden="true">
									👆
								</span>
							)}
						</button>
					),
				)}
				{roadDone && task.kind === "story" && (
					<div className="story-choice">
						<span>එකතු කරමුද, අඩු කරමුද?</span>
						{(
							[
								["add", "➕ පාරවල් එකතු"],
								["subtract", "➖ ඉතිරි දුර"],
							] as const
						).map(([value, label]) => (
							<button
								key={value}
								type="button"
								className="story-op"
								data-chosen={chosen === value || undefined}
								disabled={!playing}
								onClick={() => {
									villageSounds.play("tap");
									evidence.note("move");
									setChosen(value);
									setDigits(emptyDigits(value));
									setExchanged(false);
								}}
							>
								{label}
							</button>
						))}
					</div>
				)}
			</div>
			<DistanceBoard
				operation={operation}
				left={task.left}
				right={task.right}
				digits={digits}
				exchanged={exchanged}
				disabled={!playing || !roadDone || chosen === null}
				title={boardTitle}
				onDigits={(next, column) => {
					evidence.note("digit", column);
					setTouched(true);
					setDigits(next);
				}}
				onExchange={(next) => {
					evidence.note("carry");
					setTouched(true);
					setExchanged(next);
				}}
			/>
			{roadDone && (
				<button
					type="button"
					className="game-action market-walk"
					disabled={busy || !touched || !playing || chosen === null}
					onClick={() => {
						villageSounds.play("step");
						onSubmit(
							roadResponse(task, workingOf(operation, digits, exchanged)),
						);
					}}
				>
					🚶 නිමෝ යමු!
				</button>
			)}
		</div>
	);
}
