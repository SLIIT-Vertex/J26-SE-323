import { useEffect, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { Art, Jug, NimoSays } from "./waterParts";
import {
	arithmeticResponse,
	convertResponse,
	fillResponse,
	litresOf,
	restOf,
	solvedWorking,
	type WaterTask,
	waterText,
} from "./waterRules";
import { waterSounds } from "./waterSounds";

type Evidence = ReturnType<typeof useMoveEvidence>;
type BoardProps = {
	task: WaterTask;
	demo?: boolean;
	hint?: boolean;
	evidence: Evidence;
	onResponse(response: ConstructedResponse | null): void;
};

/** The fountain: calm while it waits, dancing when the water is right. */
function Fountain({ dancing }: { dancing: boolean }) {
	return (
		<span className="the-fountain" data-dancing={dancing || undefined}>
			<Art
				art={dancing ? "fountainDancing" : "fountainCalm"}
				className="fountain-art"
			/>
			{dancing && <Art art="sparkle" className="fountain-sparkle" />}
		</span>
	);
}

/** Litre bottles (drawn up to `max`) and the loose millilitres in a jug, each with its number. */
function Pools({ litres, ml }: { litres: number; ml: number }) {
	const shown = Math.min(6, litres);
	return (
		<div className="fountain-pools">
			<div className="fountain-pool">
				<small>ලීටර් බෝතල්</small>
				<span className="fountain-bottles">
					{Array.from({ length: shown }, (_, at) => (
						// biome-ignore lint/suspicious/noArrayIndexKey: the bottles are interchangeable.
						<span key={at} className="fountain-bottle">
							<span className="fountain-bottle-water" />
							<Art art="bottle" className="fountain-bottle-art" />
						</span>
					))}
					{litres > shown && <b>+{litres - shown}</b>}
				</span>
				<strong>{litres} l</strong>
			</div>
			<div className="fountain-pool" data-full={ml >= 1000 || undefined}>
				<small>මිලිලීටර්</small>
				<Jug
					size={1000}
					level={Math.min(1, ml / 1000)}
					className="fountain-jug"
				/>
				<strong>{ml} ml</strong>
			</div>
		</div>
	);
}

/**
 * නටන වතුර මල! Litres and millilitres at the garden fountain. Changing: pour the millilitres into
 * 1 l bottles, 1000 ml at a time. Tank sums: pour both in (when the jug passes 1000 ml it fills a
 * bottle), or take water out (when the millilitres are too few, a bottle opens into 1000 ml).
 * Filling: pour jugs into the fountain until it holds the amount asked for.
 */
export function DancingFountain(props: BoardProps) {
	if (props.task.kind === "convert") return <PourIntoBottles {...props} />;
	if (props.task.kind === "fill") return <FillFountain {...props} />;
	return <FountainSum {...props} />;
}

function PourIntoBottles({
	task,
	demo = false,
	hint = false,
	evidence,
	onResponse,
}: BoardProps) {
	const [bottles, setBottles] = useState(demo ? litresOf(task.source) : 0);
	const [done, setDone] = useState(demo);
	const [nudge, setNudge] = useState<string | null>(null);
	const left = task.source - bottles * 1000;

	useEffect(() => {
		onResponse(demo || !done ? null : convertResponse(task, bottles, left));
	}, [demo, done, task, bottles, left, onResponse]);

	const fillBottle = () => {
		if (demo || done) return;
		if (left < 1000) {
			waterSounds.play("wobble");
			setNudge("1000ට අඩුයි! ඉතිරි ටික මිලිලීටර් විදියටම තියමු.");
			return;
		}
		evidence.note("carry");
		waterSounds.play("pour");
		waterSounds.play("glass", { delay: 0.3 });
		setNudge("බලන්න! ලීටර් 1ක් කියන්නේ මිලිලීටර් 1000ක්!");
		setBottles(bottles + 1);
	};
	const emptyBottle = () => {
		if (demo || done || bottles === 0) return;
		waterSounds.play("back");
		setBottles(bottles - 1);
	};
	const finish = () => {
		if (demo || done) return;
		evidence.note("move");
		waterSounds.play("splash");
		setDone(true);
	};
	const said = demo
		? `${task.source} ml = ${waterText(task.source)}`
		: done
			? `නියමයි! ${task.source} ml = ${bottles} l ${left} ml. වතුර මල නටනවා!`
			: (nudge ?? `මිලිලීටර් ${task.source}ක් තියෙනවා. 1000 බැගින් බෝතල්වලට දාමු!`);

	return (
		<div
			className="fountain"
			data-demo={demo || undefined}
			data-done={done || undefined}
		>
			<NimoSays
				mood={done ? "cheer" : nudge?.includes("අඩුයි") ? "think" : "idle"}
				className="help-nimo"
			>
				{said}
			</NimoSays>
			<Fountain dancing={done} />
			<Pools litres={bottles} ml={left} />
			{!demo && !done && (
				<div className="fountain-buttons">
					<button
						type="button"
						className="fountain-pour"
						data-ghost={(hint && left >= 1000) || undefined}
						onClick={fillBottle}
					>
						🍶 1000 ml → 1 l බෝතලයට
					</button>
					{bottles > 0 && (
						<button
							type="button"
							className="fountain-back"
							aria-label="බෝතලයක් ආපහු"
							onClick={emptyBottle}
						>
							↩
						</button>
					)}
					<button
						type="button"
						className="fountain-finish"
						data-ghost={(hint && left < 1000) || undefined}
						onClick={finish}
					>
						⛲ වතුර මලට දාමු
					</button>
				</div>
			)}
		</div>
	);
}

type Pool = { litres: number; ml: number };

function FountainSum({
	task,
	demo = false,
	hint = false,
	evidence,
	onResponse,
}: BoardProps) {
	const adding = task.kind !== "subtract";
	const solved = solvedWorking(task);
	const [pool, setPool] = useState<Pool>(() =>
		demo
			? {
					litres: solved.litres,
					ml: adding && solved.exchanged ? solved.ml - 1000 : solved.ml,
				}
			: adding
				? { litres: 0, ml: 0 }
				: { litres: litresOf(task.left), ml: restOf(task.left) },
	);
	const [done, setDone] = useState<Record<string, boolean>>(
		demo ? { left: true, right: true, ml: true, litres: true } : {},
	);
	const [exchanged, setExchanged] = useState(demo && solved.exchanged);
	const [nudge, setNudge] = useState<string | null>(null);
	const finished = adding
		? Boolean(done.left && done.right) && pool.ml < 1000
		: Boolean(done.ml && done.litres);

	useEffect(() => {
		onResponse(
			demo || !finished
				? null
				: arithmeticResponse(task, {
						operation: adding ? "add" : "subtract",
						ml: adding ? restOf(task.left) + restOf(task.right) : pool.ml,
						exchanged,
						litres: pool.litres,
					}),
		);
	}, [demo, finished, task, adding, pool, exchanged, onResponse]);

	const pour = (side: "left" | "right") => {
		if (demo || done[side]) return;
		const amount = side === "left" ? task.left : task.right;
		evidence.note("move");
		waterSounds.play("pour");
		setNudge(null);
		setDone({ ...done, [side]: true });
		setPool({
			litres: pool.litres + litresOf(amount),
			ml: pool.ml + restOf(amount),
		});
	};
	const take = (part: "ml" | "litres") => {
		if (demo || done[part]) return;
		const need = part === "ml" ? restOf(task.right) : litresOf(task.right);
		if (pool[part] < need) {
			waterSounds.play("wobble");
			setNudge("මිලිලීටර් මදිද? ලීටරයක් මාරු කරමු!");
			return;
		}
		evidence.note("move");
		waterSounds.play("pour");
		setNudge(null);
		setDone({ ...done, [part]: true });
		setPool({ ...pool, [part]: pool[part] - need });
	};
	const canExchange = adding
		? pool.ml >= 1000
		: !done.ml && !exchanged && pool.ml < restOf(task.right) && pool.litres > 0;
	const exchange = () => {
		if (demo || !canExchange) return;
		evidence.note("carry");
		waterSounds.play("exchange");
		setExchanged(true);
		setNudge("බලන්න! ලීටර් 1ක් කියන්නේ මිලිලීටර් 1000ක්!");
		setPool(
			adding
				? { litres: pool.litres + 1, ml: pool.ml - 1000 }
				: { litres: pool.litres - 1, ml: pool.ml + 1000 },
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
				: done.ml
					? "litres"
					: "ml";
	const said = demo
		? `${waterText(task.left)} ${adding ? "+" : "−"} ${waterText(task.right)} = ${waterText(pool.litres * 1000 + pool.ml)}`
		: nudge
			? nudge
			: finished
				? "නියමයි! වතුර මල නටනවා!"
				: adding
					? pool.ml >= 1000
						? "මිලිලීටර් 1000ට වඩා! බෝතලයකට මාරු කරමු."
						: "වතුර මලට වතුර පුරවමු!"
					: `${waterText(task.right)} වතුර එළියට ගමු!`;

	return (
		<div
			className="fountain"
			data-demo={demo || undefined}
			data-done={finished || undefined}
		>
			<NimoSays
				mood={finished ? "cheer" : nudge?.includes("මදි") ? "think" : "idle"}
				className="help-nimo"
			>
				{said}
			</NimoSays>
			<Fountain dancing={finished} />
			<Pools litres={pool.litres} ml={pool.ml} />
			{!demo && !finished && (
				<div className="fountain-buttons">
					{adding
						? (["left", "right"] as const).map((side) => (
								<button
									key={side}
									type="button"
									className="fountain-pour"
									disabled={done[side]}
									data-ghost={(hint && next === side) || undefined}
									onClick={() => pour(side)}
								>
									🪣 {waterText(side === "left" ? task.left : task.right)} දාමු
								</button>
							))
						: (["ml", "litres"] as const).map((part) => (
								<button
									key={part}
									type="button"
									className="fountain-pour"
									disabled={done[part]}
									data-ghost={(hint && next === part) || undefined}
									onClick={() => take(part)}
								>
									{part === "ml"
										? `${restOf(task.right)} ml ගමු`
										: `${litresOf(task.right)} l ගමු`}
								</button>
							))}
					<button
						type="button"
						className="fountain-exchange"
						disabled={!canExchange}
						data-ghost={(hint && next === "exchange") || undefined}
						onClick={exchange}
					>
						{adding ? "🔁 1000 ml → 1 l" : "🔁 1 l → 1000 ml"}
					</button>
				</div>
			)}
		</div>
	);
}

function FillFountain({
	task,
	demo = false,
	hint = false,
	evidence,
	onResponse,
}: BoardProps) {
	const greedy = () => {
		const picks: number[] = [];
		let rest = task.target;
		for (const jug of [...task.jugs].sort((a, b) => b - a))
			while (jug <= rest) {
				picks.push(jug);
				rest -= jug;
			}
		return picks;
	};
	const [poured, setPoured] = useState<number[]>(() => (demo ? greedy() : []));
	const total = poured.reduce((sum, jug) => sum + jug, 0);
	const done = total >= task.target && poured.length > 0;

	useEffect(() => {
		onResponse(demo || !done ? null : fillResponse(task, poured));
	}, [demo, done, task, poured, onResponse]);

	const pour = (jug: number) => {
		if (demo || done) return;
		evidence.note("move");
		waterSounds.play("pour");
		setPoured([...poured, jug]);
	};
	const back = () => {
		if (demo || poured.length === 0) return;
		waterSounds.play("back");
		setPoured(poured.slice(0, -1));
	};
	const rest = task.target - total;
	const next = [...task.jugs].sort((a, b) => b - a).find((jug) => jug <= rest);
	const said = demo
		? `${poured.map(waterText).join(" + ")} = ${waterText(task.target)}`
		: total === task.target
			? "නියමයි! වතුර මල නටනවා!"
			: total > task.target
				? "අපොයි, වැඩියි! ජෝගුවක් ආපහු ගමු."
				: `වතුර මලට ${waterText(task.target)} පුරවමු!`;

	return (
		<div
			className="fountain"
			data-demo={demo || undefined}
			data-done={total === task.target || undefined}
		>
			<NimoSays
				mood={
					total === task.target
						? "cheer"
						: total > task.target
							? "think"
							: "idle"
				}
				className="help-nimo"
			>
				{said}
			</NimoSays>
			<Fountain dancing={total === task.target} />
			<p className="fountain-total">
				දැන් <strong>{waterText(total)}</strong> · ඕනේ{" "}
				<strong>{waterText(task.target)}</strong>
			</p>
			{!demo && (
				<div className="fountain-buttons">
					{task.jugs.map((jug) => (
						<button
							key={jug}
							type="button"
							className="fountain-jug-button"
							disabled={done}
							data-ghost={(hint && next === jug) || undefined}
							aria-label={`${waterText(jug)} වත් කරන්න`}
							onClick={() => pour(jug)}
						>
							<Jug size={jug} level={0.8} />
						</button>
					))}
					{poured.length > 0 && (
						<button
							type="button"
							className="fountain-back"
							aria-label="අන්තිම ජෝගුව ආපහු"
							onClick={back}
						>
							↩
						</button>
					)}
				</div>
			)}
		</div>
	);
}
