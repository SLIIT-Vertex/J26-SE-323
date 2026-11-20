import { type CSSProperties, useEffect, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { Art, Jug, NimoSays } from "./waterParts";
import {
	composeResponse,
	readResponse,
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

/** A water balloon that grows with the water in it and wobbles when it holds too much. */
function Balloon({
	fill,
	over,
	launched,
}: {
	fill: number;
	over: boolean;
	launched: boolean;
}) {
	return (
		<span
			className="balloon"
			data-over={over || undefined}
			data-launched={launched || undefined}
			style={{ "--fill": Math.min(1.25, fill) } as CSSProperties}
		>
			<Art art="balloon" className="balloon-art" />
			{launched && <Art art="splash" className="balloon-splash" />}
		</span>
	);
}

/**
 * බැලුම්වලට වතුර පුරවමු! Small amounts of water in the garden. Reading: pour 100 ml at a time
 * until the jug's water reaches the mark asked for, then tap that mark. Making 1 l: pour the little
 * jugs into the balloon until it holds the amount; too much and it wobbles.
 */
export function WaterBalloons(props: BoardProps) {
	return props.task.kind === "read" ? (
		<ReadTheJug {...props} />
	) : (
		<FillBalloon {...props} />
	);
}

const MARKS = Array.from({ length: 10 }, (_, at) => (10 - at) * 100);

function ReadTheJug({
	task,
	demo = false,
	hint = false,
	evidence,
	onResponse,
}: BoardProps) {
	const [level, setLevel] = useState(demo ? task.target : task.start);
	const [levels, setLevels] = useState<number[]>(() => {
		if (!demo) return [];
		const step = task.target > task.start ? 100 : -100;
		const out: number[] = [];
		for (
			let at = task.start + step;
			step > 0 ? at <= task.target : at >= task.target;
			at += step
		)
			out.push(at);
		return out;
	});
	const [mark, setMark] = useState<number | null>(demo ? task.target : null);
	const right = mark === task.target && level === task.target;

	useEffect(() => {
		onResponse(
			demo || mark === null ? null : readResponse(task, levels, level, mark),
		);
	}, [demo, mark, task, levels, level, onResponse]);

	const change = (step: 100 | -100) => {
		if (demo) return;
		const next = level + step;
		if (next < 100 || next > 1000) return;
		evidence.note("move");
		waterSounds.play(step > 0 ? "pour" : "back");
		setMark(null);
		setLevel(next);
		setLevels([...levels, next]);
	};
	const choose = (value: number) => {
		if (demo) return;
		evidence.note("move");
		waterSounds.play("tap");
		setMark(value);
	};
	const said = demo
		? `වතුර ${task.target} ml ඉර ළඟ!`
		: mark !== null
			? right
				? "හරියටම හරි! දැන් බැලුම යවමු!"
				: `ඔයා තේරුවේ ${mark} ml. වතුර ඉර බලමුද?`
			: level === task.target
				? "දැන් වතුර තියෙන ඉර තට්ටු කරමු!"
				: `ජෝගුවේ වතුර ${task.target} ml ඉරට එනකම් වත් කරමු!`;

	return (
		<div
			className="balloons"
			data-demo={demo || undefined}
			data-done={right || undefined}
		>
			<NimoSays mood={right ? "cheer" : "idle"} className="help-nimo">
				{said}
			</NimoSays>
			<div className="read-stage">
				<span className="read-jug">
					<span className="read-water" style={{ height: `${level / 10}%` }} />
					<Art art="jug" className="read-jug-art" />
				</span>
				<div className="read-marks">
					{MARKS.map((value) => (
						<button
							key={value}
							type="button"
							className="read-mark"
							disabled={demo}
							data-chosen={mark === value || undefined}
							data-ghost={
								(hint && level === task.target && value === task.target) ||
								undefined
							}
							aria-label={`${value} ml ඉර`}
							onClick={() => choose(value)}
						>
							— {value} ml
						</button>
					))}
				</div>
				<Balloon
					fill={right ? 1 : 0.25}
					over={false}
					launched={right && !demo}
				/>
			</div>
			{!demo && (
				<div className="balloon-buttons">
					<button
						type="button"
						className="balloon-pour"
						data-ghost={(hint && level < task.target) || undefined}
						disabled={level >= 1000}
						onClick={() => change(100)}
					>
						💧 100 ml වත් කරමු
					</button>
					<button
						type="button"
						className="balloon-pour"
						data-ghost={(hint && level > task.target) || undefined}
						disabled={level <= 100}
						onClick={() => change(-100)}
					>
						🫗 100 ml හලමු
					</button>
				</div>
			)}
		</div>
	);
}

function FillBalloon({
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
		onResponse(demo || !done ? null : composeResponse(task, poured));
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
	const right = total === task.target;
	const said = demo
		? `${poured.map(waterText).join(" + ")} = ${waterText(task.target)}`
		: right
			? "හරියටම හරි! දැන් බැලුම යවමු!"
			: total > task.target
				? "අපොයි! බැලුම පුපුරන්න වගේ. ජෝගුවක් ආපහු ගමු."
				: `බැලුමට වතුර ${waterText(task.target)} පුරවමු! ජෝගුවක් තෝරමු.`;

	return (
		<div
			className="balloons"
			data-demo={demo || undefined}
			data-done={right || undefined}
		>
			<NimoSays
				mood={right ? "cheer" : total > task.target ? "think" : "idle"}
				className="help-nimo"
			>
				{said}
			</NimoSays>
			<div className="fill-stage">
				<Balloon
					fill={total / task.target}
					over={total > task.target}
					launched={right && !demo}
				/>
				<p className="balloon-total">
					{poured.length > 0 ? poured.map(waterText).join(" + ") : "0 ml"} ={" "}
					<strong>{waterText(total)}</strong>
				</p>
			</div>
			{!demo && (
				<div className="balloon-buttons">
					{task.jugs.map((jug) => (
						<button
							key={jug}
							type="button"
							className="balloon-jug-button"
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
							className="balloon-back"
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
