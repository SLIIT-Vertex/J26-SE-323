import { useEffect, useRef, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { MissionOutcome } from "../../../mobile-learning-flow/landscape/useHardFirstEpisode";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import {
	GATE_RULES,
	knownTerms,
	type PatternBoard,
	patternResponse,
	type Rule,
	ringChoices,
	ruleLabel,
} from "./bubbleRules";
import {
	HEIGHT,
	laneYs,
	mountBubbleRush,
	RING_SIZE,
	RING_X,
	type RingKind,
	type RushHandle,
	WIDTH,
} from "./bubbleRushScene";
import { bubbleBlip, bubbleSounds } from "./bubbleSounds";

const percent = (value: number, of: number) => `${(value / of) * 100}%`;

type Race = { rule: Rule | null; picks: number[] };
type Junction = { kind: RingKind; labels: string[]; values: number[] };

/** What the submarine meets next: the rule gate, a junction of numbers, or the finish arch. */
export function junctionFor(board: PatternBoard, race: Race): Junction {
	if (!race.rule) {
		return {
			kind: "rule",
			labels: GATE_RULES.map(ruleLabel),
			values: GATE_RULES.map((_, lane) => lane),
		};
	}
	if (race.picks.length >= board.blanks.length)
		return { kind: "finish", labels: [], values: [] };
	const trail = [...knownTerms(board), ...race.picks];
	const previous = trail.at(-1) ?? 0;
	const before = trail.at(-2) ?? null;
	const values = ringChoices(previous, before);
	return { kind: "number", labels: values.map(String), values };
}

/**
 * Bubble Rush: the octopus's race. The submarine first swims through the bubble of the pattern's
 * rule, then through the ring with the next number at each junction, then to the finish. Nothing
 * on the course says right or wrong; the finish line does.
 */
export function BubbleRushMission({
	board,
	returning,
	outcome,
	busy,
	reducedMotion,
	evidence,
	onSubmit,
}: {
	board: PatternBoard;
	returning: boolean;
	outcome: MissionOutcome;
	busy: boolean;
	reducedMotion: boolean;
	evidence: ReturnType<typeof useMoveEvidence>;
	onSubmit(response: ConstructedResponse): void;
}) {
	const host = useRef<HTMLDivElement>(null);
	const scene = useRef<RushHandle | null>(null);
	const [race, setRaceState] = useState<Race>({ rule: null, picks: [] });
	const [moving, setMovingState] = useState(false);
	const current = useRef(race);
	const busyDriving = useRef(false);
	const setRace = (next: Race) => {
		current.current = next;
		setRaceState(next);
	};
	const setMoving = (next: boolean) => {
		busyDriving.current = next;
		setMovingState(next);
	};
	const playing = outcome === "playing";
	const junction = junctionFor(board, race);
	const response = patternResponse(race.rule, race.picks, board.blanks.length);
	const latest = useRef({ board, evidence, playing });
	latest.current = { board, evidence, playing };

	const choose = (lane: number) => {
		const { board: shown, evidence: moves, playing: open } = latest.current;
		if (!open || busyDriving.current) return;
		const before = current.current;
		const here = junctionFor(shown, before);
		if (here.kind === "finish") return;
		const next: Race =
			here.kind === "rule"
				? { rule: GATE_RULES[lane] ?? null, picks: [] }
				: {
						rule: before.rule,
						picks: [...before.picks, here.values[lane] ?? 0],
					};
		if (here.kind === "number" && here.values[lane] === undefined) return;
		moves.note("digit", before.rule ? before.picks.length + 1 : 0);
		bubbleSounds.play("pick");
		bubbleSounds.play("swoosh", { delay: 0.2, volume: 0.8 });
		setRace(next);
		const after = junctionFor(shown, next);
		if (scene.current) {
			setMoving(true);
			scene.current.drive(lane, after.labels, after.kind);
		}
	};
	const restart = () => {
		if (!latest.current.playing || busyDriving.current) return;
		bubbleSounds.play("tap");
		const fresh: Race = { rule: null, picks: [] };
		setRace(fresh);
		const gate = junctionFor(latest.current.board, fresh);
		scene.current?.showJunction(gate.labels, gate.kind);
	};
	const handlers = useRef({ choose });
	handlers.current = { choose };

	const boardKey = board.terms.join(",");
	useEffect(() => {
		const element = host.current;
		if (!element || !boardKey) return;
		let disposed = false;
		let handle: RushHandle | null = null;
		mountBubbleRush(element, {
			reducedMotion,
			onTapRing: (lane) => handlers.current.choose(lane),
			onPassed: () => {
				busyDriving.current = false;
				setMovingState(false);
				bubbleSounds.play("pop");
				bubbleBlip(4);
			},
		})
			.then((mounted) => {
				handle = mounted;
				if (disposed) mounted.destroy();
				else {
					scene.current = mounted;
					const shown = junctionFor(latest.current.board, current.current);
					mounted.showJunction(shown.labels, shown.kind);
				}
			})
			// No canvas (tests, very old browsers): the buttons still play the whole race.
			.catch(() => undefined);
		return () => {
			disposed = true;
			handle?.destroy();
			scene.current = null;
			element.replaceChildren();
		};
	}, [boardKey, reducedMotion]);

	useEffect(() => {
		if (outcome === "correct") scene.current?.celebrate();
		if (outcome === "wrong") scene.current?.puzzled();
	}, [outcome]);

	const filled = board.terms.map((value, index) => {
		if (value !== null) return { value: String(value), mine: false };
		const pick = race.picks[board.blanks.indexOf(index)];
		return { value: pick === undefined ? "?" : String(pick), mine: true };
	});
	const instruction =
		outcome === "correct"
			? "නියමයි! බුබුළු පාර හරි!"
			: outcome === "wrong"
				? "අපොයි! බුබුළු ටිකක් පැටලුණා."
				: junction.kind === "rule"
					? "රටාවේ රීතිය තියෙන බුබුළෙන් යමු!"
					: junction.kind === "number"
						? "ඊළඟ අංකය තියෙන බුබුළෙන් යමු!"
						: "අවසන් රේඛාවට යමු!";
	const ys = laneYs(junction.labels.length);

	return (
		<div
			className="bubble-rush"
			data-outcome={outcome}
			data-junction={junction.kind}
			data-moving={moving || undefined}
		>
			<div className="bubble-canvas" aria-hidden="true">
				<div ref={host} className="canvas-host" />
			</div>
			<ol className="bubble-trail" aria-label="සංඛ්‍යා රටාව">
				{filled.map((term, index) => (
					<li
						// biome-ignore lint/suspicious/noArrayIndexKey: term order is the identity.
						key={index}
						data-blank={term.mine || undefined}
						data-empty={term.value === "?" || undefined}
					>
						{term.value}
					</li>
				))}
			</ol>
			{race.rule && (
				<p className="bubble-rule-badge">
					<small>රීතිය</small>
					{ruleLabel(race.rule)}
				</p>
			)}
			<p className="bubble-scroll" role="status">
				{returning && playing && junction.kind === "rule"
					? "අලුත් රේස් එකක්! "
					: ""}
				{instruction}
			</p>
			{junction.kind !== "finish" &&
				junction.labels.map((label, lane) => (
					<button
						type="button"
						key={`${junction.kind}-${label}`}
						className="bubble-ring-hit"
						data-ring={label}
						disabled={!playing || moving}
						aria-label={
							junction.kind === "rule" ? `රීතිය ${label}` : `අංකය ${label}`
						}
						style={{
							left: percent(RING_X - RING_SIZE / 2, WIDTH),
							top: percent((ys[lane] ?? 600) - RING_SIZE / 2, HEIGHT),
						}}
						onClick={() => choose(lane)}
					/>
				))}
			<div className="bubble-actions">
				<button
					type="button"
					className="bubble-again"
					disabled={
						!playing || moving || (!race.rule && race.picks.length === 0)
					}
					onClick={restart}
				>
					↺ මුල ඉඳන්
				</button>
				<button
					type="button"
					className="game-action bubble-finish"
					disabled={busy || !response || !playing || moving}
					onClick={() => {
						if (!response) return;
						bubbleSounds.play("tap");
						onSubmit(response);
					}}
				>
					අවසන් රේඛාවට!
				</button>
			</div>
		</div>
	);
}
