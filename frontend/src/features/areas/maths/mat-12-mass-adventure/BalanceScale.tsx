import { type CSSProperties, type ReactNode, useEffect, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { Art, Box, NimoSays, Weight } from "./weighParts";
import {
	arithmeticResponse,
	balanceResponse,
	convertResponse,
	gramsOf,
	kilogramsOf,
	loadResponse,
	massText,
	STANDARD_MASSES,
	solvedWorking,
	type WeighTask,
	weightsFor,
} from "./weighRules";
import { weighSounds } from "./weighSounds";

type Evidence = ReturnType<typeof useMoveEvidence>;
type BoardProps = {
	task: WeighTask;
	demo?: boolean;
	hint?: boolean;
	evidence: Evidence;
	onResponse(response: ConstructedResponse | null): void;
};

const HALF_BEAM = 262;

/** Grams shown as weights under 1 kg (500 g pieces first), so 1000 g or more can be swapped. */
const gramPieces = (grams: number) => [
	...Array(Math.floor(grams / 500)).fill(500),
	...weightsFor(grams % 500),
];

/**
 * The two-pan balance: it tips towards the heavier pan (a little for a small difference, more for
 * a big one) and sits level when both sides weigh the same.
 */
function Balance({
	left,
	right,
	difference,
}: {
	left: ReactNode;
	right: ReactNode;
	/** Right minus left, in grams. */
	difference: number;
}) {
	const tilt =
		difference === 0
			? 0
			: Math.sign(difference) *
				Math.min(14, 4 + Math.log10(Math.abs(difference)) * 3);
	const lift = Math.sin((tilt * Math.PI) / 180) * HALF_BEAM;
	return (
		<div
			className="balance"
			data-level={difference === 0 || undefined}
			style={{ "--tilt": `${tilt}deg`, "--lift": lift } as CSSProperties}
		>
			<Art art="balanceStand" className="balance-stand" />
			<Art art="balanceBeam" className="balance-beam" />
			<div className="balance-pan" data-side="left">
				<span className="balance-pan-load">{left}</span>
				<Art art="balancePan" className="balance-pan-art" />
			</div>
			<div className="balance-pan" data-side="right">
				<span className="balance-pan-load">{right}</span>
				<Art art="balancePan" className="balance-pan-art" />
			</div>
		</div>
	);
}

/** The weights on a pan, drawn biggest first. */
function Stack({
	weights,
	onTake,
	disabled,
}: {
	weights: readonly number[];
	onTake?(at: number): void;
	disabled?: boolean;
}) {
	return (
		<span className="weight-stack">
			{weights
				.map((grams, at) => ({ grams, at }))
				.sort((a, b) => b.grams - a.grams)
				.map(({ grams, at }) =>
					onTake ? (
						<button
							key={at}
							type="button"
							className="weight-on-pan"
							disabled={disabled}
							aria-label={`${massText(grams)} ආපහු`}
							onClick={() => onTake(at)}
						>
							<Weight grams={grams} />
						</button>
					) : (
						<Weight key={at} grams={grams} />
					),
				)}
		</span>
	);
}

/** Every standard weight, to tap onto the pan. */
function WeightShelf({
	next,
	hint,
	disabled,
	onAdd,
}: {
	next: number | undefined;
	hint: boolean;
	disabled: boolean;
	onAdd(grams: number): void;
}) {
	return (
		<div className="weight-shelf">
			{STANDARD_MASSES.map((grams) => (
				<button
					key={grams}
					type="button"
					className="weight-pick"
					disabled={disabled}
					data-ghost={(hint && next === grams) || undefined}
					aria-label={`${massText(grams)} දාමු`}
					onClick={() => onAdd(grams)}
				>
					<Weight grams={grams} />
				</button>
			))}
		</div>
	);
}

/**
 * තරාදිය සම කරමු! The old two-pan balance. Balancing: put weights on the right pan until it is
 * level with the box. Changing: swap every 1000 g on the pan for a 1 kg weight. Cart sums: put both
 * boxes' weights on (1000 g swap for 1 kg), or take one box's weight off (opening 1 kg into 1000 g
 * when the grams run short). Loading: balance both boxes, then see how much more the cart takes.
 */
export function BalanceScale(props: BoardProps) {
	if (props.task.kind === "convert") return <SwapForKilograms {...props} />;
	if (props.task.kind === "add" || props.task.kind === "subtract")
		return <BalanceSum {...props} />;
	return <BalanceBox {...props} />;
}

function BalanceBox({
	task,
	demo = false,
	hint = false,
	evidence,
	onResponse,
}: BoardProps) {
	const loading = task.kind === "load";
	const target = loading ? task.left + task.right : task.target;
	const [weights, setWeights] = useState<number[]>(() =>
		demo ? weightsFor(target) : [],
	);
	const total = weights.reduce((sum, grams) => sum + grams, 0);
	const level = total === target;

	useEffect(() => {
		if (demo || weights.length === 0) return onResponse(null);
		onResponse(
			loading
				? level
					? loadResponse(
							task,
							solvedWorking({
								kind: "add",
								left: task.left,
								right: task.right,
							}),
							task.capacity - total,
							weights,
						)
					: null
				: balanceResponse(task, weights),
		);
	}, [demo, weights, loading, level, task, total, onResponse]);

	const add = (grams: number) => {
		if (demo) return;
		evidence.note("move");
		weighSounds.play("weight");
		weighSounds.play(total + grams === target ? "ding" : "creak", {
			delay: 0.2,
		});
		setWeights([...weights, grams]);
	};
	const take = (at: number) => {
		if (demo) return;
		evidence.note("move");
		weighSounds.play("back");
		setWeights(weights.filter((_, index) => index !== at));
	};
	const next = [...STANDARD_MASSES]
		.reverse()
		.find((grams) => grams <= target - total);
	const said = demo
		? `${weightsFor(target).map(massText).join(" + ")} = ${massText(target)}`
		: level
			? loading
				? `හරියටම හරි! මුළු බර ${massText(total)}. කරත්තේට තව ${massText(task.capacity - total)}ක් දාන්න පුළුවන්!`
				: "හරියටම හරි! දැන් දෙපැත්තම සමානයි!"
			: total > target
				? "බර වැඩියි! බර කෑල්ලක් ආපහු ගමු."
				: weights.length === 0
					? "තරාදියේ දෙපැත්ත සම කරමු!"
					: "තව බර ඕනේ! බර කෑලි එකතු කරමු.";

	return (
		<div
			className="balance-game"
			data-demo={demo || undefined}
			data-done={level || undefined}
		>
			<NimoSays
				mood={level ? "cheer" : total > target ? "think" : "idle"}
				className="help-nimo"
			>
				{said}
			</NimoSays>
			<Balance
				difference={total - target}
				left={
					loading ? (
						<span className="pan-boxes">
							<Box grams={null} className="pan-box" />
							<Box grams={null} className="pan-box" />
						</span>
					) : (
						<Box grams={task.target} className="pan-box" />
					)
				}
				right={<Stack weights={weights} onTake={take} disabled={demo} />}
			/>
			<p className="balance-total">
				බර කෑලි: <strong>{massText(total)}</strong>
			</p>
			{!demo && (
				<WeightShelf
					next={next}
					hint={hint}
					disabled={level && !loading}
					onAdd={add}
				/>
			)}
		</div>
	);
}

function SwapForKilograms({
	task,
	demo = false,
	hint = false,
	evidence,
	onResponse,
}: BoardProps) {
	const [kilograms, setKilograms] = useState(
		demo ? kilogramsOf(task.source) : 0,
	);
	const [done, setDone] = useState(demo);
	const [nudge, setNudge] = useState<string | null>(null);
	const left = task.source - kilograms * 1000;

	useEffect(() => {
		onResponse(demo || !done ? null : convertResponse(task, kilograms, left));
	}, [demo, done, task, kilograms, left, onResponse]);

	const swap = () => {
		if (demo || done) return;
		if (left < 1000) {
			weighSounds.play("wobble");
			setNudge("1000ට අඩුයි! ඉතිරි ටික ග්‍රෑම් විදියටම තියමු.");
			return;
		}
		evidence.note("carry");
		weighSounds.play("exchange");
		setNudge("බලන්න! 1 kg කියන්නේ 1000 g!");
		setKilograms(kilograms + 1);
	};
	const undo = () => {
		if (demo || done || kilograms === 0) return;
		weighSounds.play("back");
		setKilograms(kilograms - 1);
	};
	const finish = () => {
		if (demo || done) return;
		evidence.note("move");
		weighSounds.play("ding");
		setDone(true);
	};
	const said = demo
		? `${task.source} g = ${massText(task.source)}`
		: done
			? `නියමයි! ${task.source} g = ${kilograms} kg ${left} g`
			: (nudge ??
				`ග්‍රෑම් ${task.source}ක් තියෙනවා. 1000 g බැගින් 1 kg කෑලිවලට මාරු කරමු!`);

	return (
		<div
			className="balance-game"
			data-demo={demo || undefined}
			data-done={done || undefined}
		>
			<NimoSays
				mood={done ? "cheer" : nudge?.includes("අඩුයි") ? "think" : "idle"}
				className="help-nimo"
			>
				{said}
			</NimoSays>
			<div className="swap-pools">
				<div className="swap-pool">
					<small>කිලෝ කෑලි</small>
					<Stack weights={Array(kilograms).fill(1000)} />
					<strong>{kilograms} kg</strong>
				</div>
				<div className="swap-pool" data-full={left >= 1000 || undefined}>
					<small>ග්‍රෑම්</small>
					<Stack weights={gramPieces(left)} />
					<strong>{left} g</strong>
				</div>
			</div>
			{!demo && !done && (
				<div className="balance-buttons">
					<button
						type="button"
						className="balance-swap"
						data-ghost={(hint && left >= 1000) || undefined}
						onClick={swap}
					>
						🔁 1000 g → 1 kg
					</button>
					{kilograms > 0 && (
						<button
							type="button"
							className="balance-back"
							aria-label="1 kg ආපහු"
							onClick={undo}
						>
							↩
						</button>
					)}
					<button
						type="button"
						className="balance-finish"
						data-ghost={(hint && left < 1000) || undefined}
						onClick={finish}
					>
						✓ ඉවරයි
					</button>
				</div>
			)}
		</div>
	);
}

type Pans = { kg: number; g: number };

function BalanceSum({
	task,
	demo = false,
	hint = false,
	evidence,
	onResponse,
}: BoardProps) {
	const adding = task.kind === "add";
	const solved = solvedWorking(task);
	const [pans, setPans] = useState<Pans>(() =>
		demo
			? {
					kg: solved.kg,
					g: adding && solved.exchanged ? solved.g - 1000 : solved.g,
				}
			: adding
				? { kg: 0, g: 0 }
				: { kg: kilogramsOf(task.left), g: gramsOf(task.left) },
	);
	const [done, setDone] = useState<Record<string, boolean>>(
		demo ? { left: true, right: true, g: true, kg: true } : {},
	);
	const [exchanged, setExchanged] = useState(demo && solved.exchanged);
	const [nudge, setNudge] = useState<string | null>(null);
	const finished = adding
		? Boolean(done.left && done.right) && pans.g < 1000
		: Boolean(done.g && done.kg);

	useEffect(() => {
		onResponse(
			demo || !finished
				? null
				: arithmeticResponse(task, {
						operation: adding ? "add" : "subtract",
						g: adding ? gramsOf(task.left) + gramsOf(task.right) : pans.g,
						exchanged,
						kg: pans.kg,
					}),
		);
	}, [demo, finished, task, adding, pans, exchanged, onResponse]);

	const put = (side: "left" | "right") => {
		if (demo || done[side]) return;
		const grams = side === "left" ? task.left : task.right;
		evidence.note("move");
		weighSounds.play("weight");
		setNudge(null);
		setDone({ ...done, [side]: true });
		setPans({ kg: pans.kg + kilogramsOf(grams), g: pans.g + gramsOf(grams) });
	};
	const take = (part: "g" | "kg") => {
		if (demo || done[part]) return;
		const need = part === "g" ? gramsOf(task.right) : kilogramsOf(task.right);
		if (pans[part] < need) {
			weighSounds.play("wobble");
			setNudge("ග්‍රෑම් මදිද? කිලෝ එකක් මාරු කරමු!");
			return;
		}
		evidence.note("move");
		weighSounds.play("back");
		setNudge(null);
		setDone({ ...done, [part]: true });
		setPans({ ...pans, [part]: pans[part] - need });
	};
	const canExchange = adding
		? pans.g >= 1000
		: !done.g && !exchanged && pans.g < gramsOf(task.right) && pans.kg > 0;
	const exchange = () => {
		if (demo || !canExchange) return;
		evidence.note("carry");
		weighSounds.play("exchange");
		setExchanged(true);
		setNudge("බලන්න! 1 kg කියන්නේ 1000 g!");
		setPans(
			adding
				? { kg: pans.kg + 1, g: pans.g - 1000 }
				: { kg: pans.kg - 1, g: pans.g + 1000 },
		);
	};
	const next = finished
		? null
		: canExchange
			? "exchange"
			: adding
				? done.left
					? "right"
					: "left"
				: done.g
					? "kg"
					: "g";
	const said = demo
		? `${massText(task.left)} ${adding ? "+" : "−"} ${massText(task.right)} = ${massText(pans.kg * 1000 + pans.g)}`
		: nudge
			? nudge
			: finished
				? "හරියටම හරි! දැන් දෙපැත්තම සමානයි!"
				: adding
					? pans.g >= 1000
						? "ග්‍රෑම් 1000ට වඩා! 1 kg කෑල්ලකට මාරු කරමු."
						: "මේ බර කෑලි ටික එකතු කරමු!"
					: `${massText(task.right)} අයින් කරමු!`;

	return (
		<div
			className="balance-game"
			data-demo={demo || undefined}
			data-done={finished || undefined}
		>
			<NimoSays
				mood={finished ? "cheer" : nudge?.includes("මදි") ? "think" : "idle"}
				className="help-nimo"
			>
				{said}
			</NimoSays>
			<div className="swap-pools">
				<div className="swap-pool">
					<small>කිලෝ කෑලි</small>
					<Stack weights={Array(Math.min(pans.kg, 9)).fill(1000)} />
					<strong>{pans.kg} kg</strong>
				</div>
				<div className="swap-pool" data-full={pans.g >= 1000 || undefined}>
					<small>ග්‍රෑම්</small>
					<Stack weights={gramPieces(pans.g)} />
					<strong>{pans.g} g</strong>
				</div>
			</div>
			{!demo && !finished && (
				<div className="balance-buttons">
					{adding
						? (["left", "right"] as const).map((side) => (
								<button
									key={side}
									type="button"
									className="balance-put"
									disabled={done[side]}
									data-ghost={(hint && next === side) || undefined}
									onClick={() => put(side)}
								>
									📦 {massText(side === "left" ? task.left : task.right)} දාමු
								</button>
							))
						: (["g", "kg"] as const).map((part) => (
								<button
									key={part}
									type="button"
									className="balance-put"
									disabled={done[part]}
									data-ghost={(hint && next === part) || undefined}
									onClick={() => take(part)}
								>
									{part === "g"
										? `${gramsOf(task.right)} g අයින් කරමු`
										: `${kilogramsOf(task.right)} kg අයින් කරමු`}
								</button>
							))}
					<button
						type="button"
						className="balance-swap"
						disabled={!canExchange}
						data-ghost={(hint && next === "exchange") || undefined}
						onClick={exchange}
					>
						{adding ? "🔁 1000 g → 1 kg" : "🔁 1 kg → 1000 g"}
					</button>
				</div>
			)}
		</div>
	);
}
