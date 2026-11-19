import {
	type CSSProperties,
	useEffect,
	useMemo,
	useRef,
	useState,
} from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { bubbleArtReady, bubbleArtUrl } from "./bubbleArt";
import {
	applyRule,
	knownTerms,
	type PatternBoard,
	patternResponse,
	patternRule,
	type Rule,
	ringChoices,
	ruleLabel,
	solvePattern,
} from "./bubbleRules";
import { bubbleBlip, bubbleSounds } from "./bubbleSounds";

type Evidence = ReturnType<typeof useMoveEvidence>;

const HOP_MS = 520;
const WOBBLE_MS = 900;

/** Tiki's call for each rule, shown above the shells. */
export function tikiCall(rule: Rule | null): string {
	if (!rule) return "ටිකී එක්ක පනිමු!";
	if (rule.operation === "add" && rule.step === 2) return "දෙක බැගින් පනිමු!";
	if (rule.operation === "subtract" && rule.step === 2)
		return "දෙක බැගින් ආපස්සට පනිමු!";
	if (rule.operation === "multiply" && rule.step === 2)
		return "හැම පැනීමකදීම දෙගුණයක්!";
	if (rule.operation === "multiply" && rule.step === 5)
		return "හැම පැනීමකදීම පස්ගුණයක්!";
	return `${ruleLabel(rule)} බැගින් පනිමු!`;
}

/**
 * Crab's Bubble Steps (the most visible help): numbered shells in a row with Tiki's jump written
 * over every hop. The child watches Tiki hop the known shells, then picks the number Tiki lands on
 * next. A wrong number makes Tiki wobble and stay put.
 */
export function TikiSteps({
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
	const [landed, setLanded] = useState<number[]>(() =>
		demo ? solvePattern(board) : [],
	);
	const [tikiAt, setTikiAt] = useState(() =>
		demo ? board.terms.length - 1 : Math.max(0, known.length - 1),
	);
	const [hopping, setHopping] = useState(false);
	const [wobble, setWobble] = useState(false);
	const timers = useRef<Array<ReturnType<typeof setTimeout>>>([]);
	useEffect(
		() => () => {
			for (const timer of timers.current) clearTimeout(timer);
		},
		[],
	);
	const later = (ms: number, run: () => void) => {
		timers.current.push(setTimeout(run, ms));
	};

	useEffect(() => {
		onResponse(
			demo ? null : patternResponse(rule, landed, board.blanks.length),
		);
	}, [demo, rule, landed, board.blanks.length, onResponse]);

	const trail = [...known, ...landed];
	const done = landed.length >= board.blanks.length;
	const previous = trail.at(-1) ?? 0;
	const choices = done ? [] : ringChoices(previous, trail.at(-2) ?? null);
	const next = rule ? applyRule(rule, previous) : null;

	/** Tiki hops over the known shells from the first one, showing each jump. */
	const watch = () => {
		if (demo || hopping) return;
		bubbleSounds.play("tap");
		setHopping(true);
		setTikiAt(0);
		const last = known.length - 1 + landed.length;
		for (let shell = 1; shell <= last; shell++) {
			later(shell * HOP_MS, () => {
				setTikiAt(shell);
				bubbleBlip(shell + 2);
			});
		}
		later((last + 1) * HOP_MS, () => setHopping(false));
	};
	const jump = (value: number) => {
		if (demo || done || hopping || wobble) return;
		evidence.note("digit", landed.length);
		if (value !== next) {
			bubbleSounds.play("boing");
			setWobble(true);
			later(WOBBLE_MS, () => setWobble(false));
			return;
		}
		bubbleSounds.play("splash", { volume: 0.7 });
		bubbleBlip(landed.length + 6, 0.15);
		setLanded([...landed, value]);
		setTikiAt(known.length + landed.length);
	};

	const shells = board.terms.map((value, index) => {
		const blank = board.blanks.indexOf(index);
		return blank === -1 ? value : (landed[blank] ?? null);
	});

	return (
		<div
			className="tiki-steps"
			data-demo={demo || undefined}
			data-wobble={wobble || undefined}
			style={{ "--shells": shells.length } as CSSProperties}
		>
			<p className="tiki-call" role="status">
				{done && !demo ? "නියමයි! ටිකී පැනලා ඉවරයි!" : tikiCall(rule)}
			</p>
			<ol className="tiki-path" aria-label="ටිකීගේ බෙලි කටු">
				{shells.map((value, index) => (
					<li
						// biome-ignore lint/suspicious/noArrayIndexKey: shell order is the identity.
						key={index}
						className="tiki-shell"
						data-blank={board.blanks.includes(index) || undefined}
						data-next={
							(!done && index === known.length + landed.length) || undefined
						}
					>
						{index > 0 && rule && shells[index] !== null && (
							<span className="tiki-hop" aria-hidden="true">
								{ruleLabel(rule)}
							</span>
						)}
						{bubbleArtReady("stepShell") ? (
							<img
								className="tiki-shell-art"
								src={bubbleArtUrl("stepShell")}
								alt=""
							/>
						) : (
							<span className="tiki-shell-shape" />
						)}
						<b>{value ?? "?"}</b>
						{tikiAt === index && <Tiki jumping={hopping} />}
					</li>
				))}
			</ol>
			{!demo && !done && (
				<div className="tiki-choices">
					<span>ටිකී ඊළඟට පනින්නේ කොහෙටද?</span>
					{choices.map((value) => (
						<button
							type="button"
							key={value}
							className="tiki-choice"
							data-ghost={(hint && value === next) || undefined}
							disabled={hopping || wobble}
							aria-label={`${value} ට පනින්න`}
							onClick={() => jump(value)}
						>
							{value}
						</button>
					))}
				</div>
			)}
			{!demo && (
				<button
					type="button"
					className="tiki-watch"
					disabled={hopping}
					onClick={watch}
				>
					ටිකී පනින හැටි බලමු
				</button>
			)}
		</div>
	);
}

function Tiki({ jumping }: { jumping: boolean }) {
	const key = jumping ? "tikiJump" : "tikiIdle";
	return bubbleArtReady(key) ? (
		<img className="tiki" src={bubbleArtUrl(key)} alt="ටිකී" />
	) : (
		<span className="tiki tiki-shape" role="img" aria-label="ටිකී" />
	);
}
