import { useEffect, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { Money, NimoSays } from "./shopParts";
import {
	composeResponse,
	DENOMINATION_BY_ID,
	DENOMINATIONS,
	type MoneyType,
	moneyText,
	recognitionResponse,
	type ShopTask,
} from "./shopRules";
import { shopSounds } from "./shopSounds";

type Evidence = ReturnType<typeof useMoveEvidence>;
type BoardProps = {
	task: ShopTask;
	demo?: boolean;
	hint?: boolean;
	evidence: Evidence;
	onResponse(response: ConstructedResponse | null): void;
};

/**
 * කාසි පෙට්ටිය! The wooden coin box at the play shop. Sorting: put every coin in the coin side
 * and every note in the note side, smallest first. Making an amount: drop coins and notes in until
 * the box holds the price on the toy's tag.
 */
export function CoinBox(props: BoardProps) {
	return props.task.kind === "recognize" ? (
		<SortMoney {...props} />
	) : (
		<MakeAmount {...props} />
	);
}

type Placed = { id: string; side: MoneyType };

function SortMoney({
	task,
	demo = false,
	hint = false,
	evidence,
	onResponse,
}: BoardProps) {
	const sorted = [...task.tokens].sort((a, b) => a.value - b.value);
	const [placed, setPlaced] = useState<Placed[]>(() =>
		demo ? sorted.map((token) => ({ id: token.id, side: token.type })) : [],
	);
	const [chosen, setChosen] = useState<string | null>(null);
	const left = task.tokens.filter(
		(token) => !placed.some((item) => item.id === token.id),
	);
	const done = left.length === 0 && placed.length > 0;

	useEffect(() => {
		onResponse(demo || !done ? null : recognitionResponse(placed));
	}, [demo, done, placed, onResponse]);

	const pick = (id: string) => {
		if (demo) return;
		shopSounds.play("pick");
		setChosen(id === chosen ? null : id);
	};
	const drop = (side: MoneyType) => {
		if (demo || !chosen) return;
		evidence.note("move");
		shopSounds.play(side === "coin" ? "coin" : "note");
		setPlaced([...placed, { id: chosen, side }]);
		setChosen(null);
	};
	const undo = () => {
		if (demo || placed.length === 0) return;
		shopSounds.play("back");
		setPlaced(placed.slice(0, -1));
	};
	// The next right token, shown faintly on a help stage.
	const nextId = sorted.find(
		(token) => !placed.some((item) => item.id === token.id),
	)?.id;
	const nextSide = chosen ? DENOMINATION_BY_ID[chosen]?.type : undefined;
	const said = demo
		? "පොඩිම ගාණ මුලින්ම: කාසි කාසි පැත්තට, නෝට්ටු නෝට්ටු පැත්තට."
		: done
			? "හරියටම හරි! ඔයා ගණන් කළා!"
			: chosen
				? "කාසියක්ද, නෝට්ටුවක්ද? හරි පැත්තට දාමු!"
				: placed.length === 0
					? "පොඩිම ගාණ මුලින්ම! ඒක තෝරමු."
					: "ඊළඟට පොඩිම ගාණ කීයද?";

	return (
		<div
			className="coin-box"
			data-demo={demo || undefined}
			data-done={done || undefined}
		>
			<NimoSays mood={done ? "cheer" : "idle"} className="help-nimo">
				{said}
			</NimoSays>
			<div className="coin-tray">
				{left.map((token) => (
					<button
						key={token.id}
						type="button"
						className="coin-tray-token"
						data-chosen={chosen === token.id || undefined}
						data-ghost={(hint && !chosen && nextId === token.id) || undefined}
						aria-label={`${moneyText(token.value)} තෝරන්න`}
						onClick={() => pick(token.id)}
					>
						<Money id={token.id} />
					</button>
				))}
			</div>
			<div className="coin-box-sides">
				{(["coin", "note"] as const).map((side) => (
					<button
						key={side}
						type="button"
						className="coin-box-side"
						data-side={side}
						disabled={demo || !chosen}
						data-ghost={(hint && nextSide === side) || undefined}
						aria-label={side === "coin" ? "කාසි පැත්තට" : "නෝට්ටු පැත්තට"}
						onClick={() => drop(side)}
					>
						<small>{side === "coin" ? "🪙 කාසි" : "💵 නෝට්ටු"}</small>
						<span className="coin-box-inside">
							{placed.map((item, at) =>
								item.side === side ? (
									<span key={item.id} className="coin-box-placed">
										<Money id={item.id} />
										<i>{at + 1}</i>
									</span>
								) : null,
							)}
						</span>
					</button>
				))}
			</div>
			{!demo && placed.length > 0 && !done && (
				<button
					type="button"
					className="coin-undo"
					aria-label="අන්තිම එක ආපහු"
					onClick={undo}
				>
					↩
				</button>
			)}
		</div>
	);
}

/** Coins and notes for making amounts: Rs. 1, 2, 5, 10 coins and Rs. 20, 50, 100 notes. */
const SUPPLY = DENOMINATIONS.slice(0, 7);

function MakeAmount({
	task,
	demo = false,
	hint = false,
	evidence,
	onResponse,
}: BoardProps) {
	const greedy = () => {
		const picks: string[] = [];
		let rest = task.target;
		for (const row of [...SUPPLY].reverse())
			while (row.value <= rest) {
				picks.push(row.id);
				rest -= row.value;
			}
		return picks;
	};
	const [inBox, setInBox] = useState<string[]>(() => (demo ? greedy() : []));
	const total = inBox.reduce(
		(sum, id) => sum + (DENOMINATION_BY_ID[id]?.value ?? 0),
		0,
	);
	const done = total >= task.target && inBox.length > 0;

	useEffect(() => {
		onResponse(demo || !done ? null : composeResponse(task, inBox));
	}, [demo, done, task, inBox, onResponse]);

	const add = (id: string) => {
		if (demo || done) return;
		evidence.note("move");
		shopSounds.play(DENOMINATION_BY_ID[id]?.type === "note" ? "note" : "coin");
		setInBox([...inBox, id]);
	};
	const remove = (at: number) => {
		if (demo) return;
		evidence.note("move");
		shopSounds.play("back");
		setInBox(inBox.filter((_, index) => index !== at));
	};
	const rest = task.target - total;
	const next = [...SUPPLY].reverse().find((row) => row.value <= rest)?.id;
	const said = demo
		? `${inBox.map((id) => (DENOMINATION_BY_ID[id]?.value ?? 0) / 100).join(" + ")} = ${task.target / 100}`
		: total === task.target
			? "හරියටම හරි! ඔයා ගණන් කළා!"
			: total > task.target
				? "අපොයි, වැඩියි! එකක් ආපහු ගමු."
				: `${moneyText(task.target)}ක් හදමු! කාසි ටික පෙට්ටියට දාමු!`;

	return (
		<div
			className="coin-box"
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
			<span className="toy-price">🧸 {moneyText(task.target)}</span>
			<div className="coin-box-sides coin-box-make">
				<div className="coin-box-side" data-side="all">
					<span className="coin-box-inside">
						{inBox.map((id, at) => (
							<button
								// biome-ignore lint/suspicious/noArrayIndexKey: the drop order is the identity.
								key={`${id}-${at}`}
								type="button"
								className="coin-box-placed"
								disabled={demo}
								aria-label={`${moneyText(DENOMINATION_BY_ID[id]?.value ?? 0)} ආපහු`}
								onClick={() => remove(at)}
							>
								<Money id={id} />
							</button>
						))}
					</span>
				</div>
			</div>
			<p className="coin-sum">
				{inBox.length > 0
					? inBox
							.map((id) => (DENOMINATION_BY_ID[id]?.value ?? 0) / 100)
							.join(" + ")
					: "0"}{" "}
				= <strong>{total / 100}</strong>
			</p>
			{!demo && (
				<div className="coin-tray">
					{SUPPLY.map((row) => (
						<button
							key={row.id}
							type="button"
							className="coin-tray-token"
							disabled={done}
							data-ghost={(hint && next === row.id) || undefined}
							aria-label={`${moneyText(row.value)} දාමු`}
							onClick={() => add(row.id)}
						>
							<Money id={row.id} />
						</button>
					))}
				</div>
			)}
		</div>
	);
}
