import { useEffect, useMemo, useRef, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { bubbleArtReady, bubbleArtUrl } from "./bubbleArt";
import {
	knownTerms,
	type PatternBoard,
	patternResponse,
	patternRule,
	SHELL_MULTIPLIERS,
	solvePattern,
} from "./bubbleRules";
import { bubbleRun, bubbleSounds } from "./bubbleSounds";

type Evidence = ReturnType<typeof useMoveEvidence>;

/** Up to this many jellyfish are drawn one by one; a bigger group is one jellyfish with a badge. */
const COUNTABLE = 10;
const WOBBLE_MS = 1100;

/**
 * Jellyfish Copy Party (multiplying patterns). Jelly's group swims into a magic shell and comes out
 * as copies. First the child finds the shell that turns the first number into the second (a wrong
 * shell makes the jellyfish giggle and swim back), then uses it to fill each blank.
 */
export function JellyfishParty({
	board,
	demo = false,
	hint = false,
	evidence,
	onResponse,
}: {
	board: PatternBoard;
	demo?: boolean;
	hint?: boolean;
	evidence: Evidence;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const rule = useMemo(() => patternRule(board), [board]);
	const known = knownTerms(board);
	const first = known[0] ?? 1;
	const second = known[1] ?? first;
	const [found, setFound] = useState<number | null>(() =>
		demo && rule ? rule.step : null,
	);
	const [fills, setFills] = useState<number[]>(() =>
		demo ? solvePattern(board) : [],
	);
	const [trying, setTrying] = useState<number | null>(null);
	/** The last clone the child made in the shell: what it started from and the copies. */
	const [lastClone, setLastClone] = useState<{
		from: number;
		times: number;
	} | null>(() => {
		if (!demo || !rule) return null;
		const solved = solvePattern(board);
		const from = solved.length > 1 ? solved.at(-2) : known.at(-1);
		return from === undefined ? null : { from, times: rule.step };
	});
	const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
	useEffect(() => () => clearTimeout(timer.current), []);

	useEffect(() => {
		onResponse(
			demo || found === null
				? null
				: patternResponse(
						{ operation: "multiply", step: found },
						fills,
						board.blanks.length,
					),
		);
	}, [demo, found, fills, board.blanks.length, onResponse]);

	const trail = [...known, ...fills];
	const source = found === null ? first : (trail.at(-1) ?? first);
	const done = fills.length >= board.blanks.length;
	const clone = trying !== null ? { from: first, times: trying } : lastClone;

	const pickShell = (multiplier: number) => {
		if (demo || done || trying !== null) return;
		evidence.note("digit", fills.length);
		bubbleSounds.play("magic", { volume: 0.8 });
		bubbleRun(Math.min(multiplier + 1, 6));
		if (found === null) {
			setTrying(multiplier);
			if (first * multiplier === second) {
				bubbleSounds.play("sparkle", { delay: 0.5, volume: 0.6 });
				timer.current = setTimeout(() => {
					setTrying(null);
					setFound(multiplier);
				}, WOBBLE_MS);
			} else {
				bubbleSounds.play("boing", { delay: 0.5 });
				timer.current = setTimeout(() => setTrying(null), WOBBLE_MS);
			}
			return;
		}
		if (multiplier !== found) {
			bubbleSounds.play("boing");
			return;
		}
		setLastClone({ from: source, times: multiplier });
		setFills([...fills, source * multiplier]);
	};
	const startOver = () => {
		if (demo) return;
		bubbleSounds.play("tap");
		setFound(null);
		setFills([]);
		setLastClone(null);
	};

	const testing = found === null;
	const made = clone === null ? null : clone.from * clone.times;
	const wrongTry = testing && trying !== null && first * trying !== second;
	const message = demo
		? "මැජික් කටුව එකම විදියට නැවත නැවත වැඩ කරනවා."
		: done
			? "නියමයි! රටාව සම්පූර්ණයි."
			: testing
				? wrongTry
					? "හිහි! ඒ කටුව නෙවෙයි. වෙන එකක් බලමු."
					: `ජෙලි මාළු ${first} ක් ${second} ක් කරන්න මැජික් කටුව තෝරන්න!`
				: `ඒ කටුවම ආයෙත් පාවිච්චි කරමු! ජෙලි මාළු ${source} ක් කටුවට දාන්න.`;

	return (
		<div
			className="jelly-party"
			data-demo={demo || undefined}
			data-testing={testing || undefined}
		>
			<PatternStrip terms={board.terms} blanks={board.blanks} fills={fills} />
			<p className="jelly-message" role="status">
				{message}
			</p>
			<div className="jelly-stage">
				<JellyGroup value={source} copies={1} label={`ජෙලි ${source}`} />
				<span className="jelly-arrow" aria-hidden="true">
					➜
				</span>
				<div
					className="jelly-shell-slot"
					data-active={(trying ?? found) !== null || undefined}
				>
					<Shell multiplier={trying ?? found} />
				</div>
				<span className="jelly-arrow" aria-hidden="true">
					➜
				</span>
				<div className="jelly-result" data-wrong={wrongTry || undefined}>
					{made === null ? (
						<span className="jelly-target">{testing ? second : "?"}</span>
					) : (
						<>
							<JellyGroup
								value={clone?.from ?? source}
								copies={clone?.times ?? 1}
								label={`ජෙලි ${made}`}
							/>
							<strong className="jelly-total">{made}</strong>
						</>
					)}
				</div>
			</div>
			<div className="jelly-shells">
				{SHELL_MULTIPLIERS.map((multiplier) => (
					<button
						type="button"
						key={multiplier}
						className="jelly-shell-button"
						data-shell={multiplier}
						data-found={found === multiplier || undefined}
						data-ghost={
							(hint && !demo && rule?.step === multiplier) || undefined
						}
						disabled={
							demo ||
							done ||
							trying !== null ||
							(found !== null && found !== multiplier)
						}
						aria-label={`× ${multiplier} මැජික් කටුව`}
						onClick={() => pickShell(multiplier)}
					>
						<Shell multiplier={multiplier} />
					</button>
				))}
				{!demo && (found !== null || fills.length > 0) && (
					<button type="button" className="jelly-again" onClick={startOver}>
						↺
					</button>
				)}
			</div>
		</div>
	);
}

/** The pattern as a row of small bubbles; filled blanks are the child's numbers. */
export function PatternStrip({
	terms,
	blanks,
	fills,
}: {
	terms: Array<number | null>;
	blanks: number[];
	fills: number[];
}) {
	return (
		<ol className="pattern-strip" aria-label="සංඛ්‍යා රටාව">
			{terms.map((value, index) => {
				const blank = blanks.indexOf(index);
				const text = value ?? fills[blank];
				return (
					<li
						// biome-ignore lint/suspicious/noArrayIndexKey: term order is the identity.
						key={index}
						data-blank={blank !== -1 || undefined}
						data-empty={text === undefined || undefined}
					>
						{text ?? "?"}
					</li>
				);
			})}
		</ol>
	);
}

function Shell({ multiplier }: { multiplier: number | null }) {
	return (
		<span className="jelly-shell" data-multiplier={multiplier ?? undefined}>
			{bubbleArtReady("magicShell") ? (
				<img src={bubbleArtUrl("magicShell")} alt="" />
			) : (
				<span className="jelly-shell-shape" />
			)}
			<span className="jelly-shell-tag">
				{multiplier ? `×${multiplier}` : "?"}
			</span>
		</span>
	);
}

/** A group of jellyfish in a bubble, `copies` times. */
function JellyGroup({
	value,
	copies,
	label,
}: {
	value: number;
	copies: number;
	label: string;
}) {
	return (
		<span
			className="jelly-groups"
			data-copies={copies}
			role="img"
			aria-label={label}
		>
			{Array.from({ length: copies }, (_, copy) => (
				<span
					// biome-ignore lint/suspicious/noArrayIndexKey: copies are interchangeable.
					key={copy}
					className="jelly-group"
					style={{ animationDelay: `${copy * 120}ms` }}
				>
					{value <= COUNTABLE ? (
						Array.from({ length: value }, (_, at) => (
							// biome-ignore lint/suspicious/noArrayIndexKey: jellyfish are interchangeable.
							<Jelly key={at} />
						))
					) : (
						<>
							<Jelly />
							<b>{value}</b>
						</>
					)}
				</span>
			))}
		</span>
	);
}

function Jelly() {
	return bubbleArtReady("jellyfish") ? (
		<img className="jelly" src={bubbleArtUrl("jellyfish")} alt="" />
	) : (
		<span className="jelly jelly-shape" />
	);
}
