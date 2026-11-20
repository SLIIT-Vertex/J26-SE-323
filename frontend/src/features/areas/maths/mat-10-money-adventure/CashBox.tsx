import { useEffect, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { SACKS } from "./shopArt";
import { Art, CentCoin, Money, NimoSays, Pile } from "./shopParts";
import {
	arithmeticResponse,
	centsOf,
	moneyText,
	rupeesOf,
	type ShopTask,
	shopResponse,
	solvedWorking,
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

/** The two drawers of the cash box: whole rupees, and cents (which may pile past 100). */
function Drawers({ rupees, cents }: { rupees: number; cents: number }) {
	return (
		<div className="cash-drawers">
			<div className="cash-drawer">
				<small>රුපියල්</small>
				<span className="cash-drawer-money">
					{Math.floor(rupees / 100) > 0 && (
						<Pile count={Math.floor(rupees / 100)} kind="note">
							<Money id="note-100" />
						</Pile>
					)}
					{Math.floor((rupees % 100) / 10) > 0 && (
						<Pile count={Math.floor((rupees % 100) / 10)} max={4}>
							<Money id="coin-10" />
						</Pile>
					)}
					{rupees % 10 > 0 && (
						<Pile count={rupees % 10} max={4}>
							<Money id="coin-1" />
						</Pile>
					)}
				</span>
				<strong>රු. {rupees}</strong>
			</div>
			<div
				className="cash-drawer cash-drawer-cents"
				data-full={cents >= 100 || undefined}
			>
				<small>සත</small>
				<span className="cash-drawer-money">
					{Math.floor(cents / 10) > 0 && (
						<Pile count={Math.floor(cents / 10)} max={5}>
							<CentCoin value={10} />
						</Pile>
					)}
					{cents % 10 > 0 && (
						<Pile count={cents % 10} max={5}>
							<CentCoin value={1} />
						</Pile>
					)}
				</span>
				<strong>සත {cents}</strong>
			</div>
		</div>
	);
}

/** The cash box itself: it wobbles when money goes in and cheers when the sum is done. */
function TheBox({ happy, bump }: { happy: boolean; bump: number }) {
	return (
		<span className="the-cash-box" key={bump} data-bump={bump > 0 || undefined}>
			<Art
				art={happy ? "cashboxHappy" : "cashboxIdle"}
				className="cash-box-art"
			/>
			{bump > 0 && <Art art="sparkle" className="cash-sparkle" />}
		</span>
	);
}

/**
 * සල්ලි මාරු කරමු! The talking cash box at the shop counter. Adding: pour both amounts in;
 * when the cents drawer reaches 100, the box swaps them for Rs. 1. Taking away: take the cents and
 * the rupees out; when the cents are too few, the box opens Rs. 1 into 100 cents. Shopping: put
 * each kilo's price in, pay, and the box gives back the change.
 */
export function CashBox(props: BoardProps) {
	return props.task.kind === "shop" ? (
		<ShopTill {...props} />
	) : (
		<CentSum {...props} />
	);
}

type Drawer = { rupees: number; cents: number };

function CentSum({
	task,
	demo = false,
	hint = false,
	evidence,
	onResponse,
}: BoardProps) {
	const adding = task.kind !== "subtract";
	const solved = solvedWorking(task);
	const [drawer, setDrawer] = useState<Drawer>(() =>
		demo
			? {
					rupees: solved.rupees,
					cents: adding && solved.exchanged ? solved.cents - 100 : solved.cents,
				}
			: adding
				? { rupees: 0, cents: 0 }
				: { rupees: rupeesOf(task.left), cents: centsOf(task.left) },
	);
	/** Adding: the bags poured in. Taking away: the parts taken out. */
	const [done, setDone] = useState<Record<string, boolean>>(
		demo ? { left: true, right: true, cents: true, rupees: true } : {},
	);
	const [exchanged, setExchanged] = useState(demo && solved.exchanged);
	const [nudge, setNudge] = useState<string | null>(null);
	const [bump, setBump] = useState(0);
	const finished = adding
		? Boolean(done.left && done.right) && drawer.cents < 100
		: Boolean(done.cents && done.rupees);

	useEffect(() => {
		onResponse(
			demo || !finished
				? null
				: arithmeticResponse(task, {
						operation: adding ? "add" : "subtract",
						cents: adding
							? centsOf(task.left) + centsOf(task.right)
							: drawer.cents,
						exchanged,
						rupees: drawer.rupees,
					}),
		);
	}, [demo, finished, task, adding, drawer, exchanged, onResponse]);

	const wobble = () => setBump(bump + 1);
	const pour = (side: "left" | "right") => {
		if (demo || done[side]) return;
		const amount = side === "left" ? task.left : task.right;
		evidence.note("move");
		shopSounds.play("coin");
		wobble();
		setNudge(null);
		setDone({ ...done, [side]: true });
		setDrawer({
			rupees: drawer.rupees + rupeesOf(amount),
			cents: drawer.cents + centsOf(amount),
		});
	};
	const take = (part: "cents" | "rupees") => {
		if (demo || done[part]) return;
		const need = part === "cents" ? centsOf(task.right) : rupeesOf(task.right);
		if (drawer[part] < need) {
			shopSounds.play("boing");
			setNudge("සත මදි! රු. 1ක් සත 100කට මාරු කරමු.");
			return;
		}
		evidence.note("move");
		shopSounds.play("drop");
		setNudge(null);
		setDone({ ...done, [part]: true });
		setDrawer({ ...drawer, [part]: drawer[part] - need });
	};
	const canExchange = adding
		? drawer.cents >= 100
		: !done.cents &&
			!exchanged &&
			drawer.cents < centsOf(task.right) &&
			drawer.rupees > 0;
	const exchange = () => {
		if (demo || !canExchange) return;
		evidence.note("carry");
		shopSounds.play("exchange");
		shopSounds.play("spit", { delay: 0.3 });
		wobble();
		setExchanged(true);
		setNudge("සත 100ක් කියන්නේ රු. 1යි!");
		setDrawer(
			adding
				? { rupees: drawer.rupees + 1, cents: drawer.cents - 100 }
				: { rupees: drawer.rupees - 1, cents: drawer.cents + 100 },
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
				: done.cents
					? "rupees"
					: "cents";
	const said = demo
		? `${moneyText(task.left)} ${adding ? "+" : "−"} ${moneyText(task.right)} = ${moneyText(drawer.rupees * 100 + drawer.cents)}`
		: nudge
			? nudge
			: finished
				? "නියමයි! දෙපැත්තේම ගණන සමානයි!"
				: adding
					? drawer.cents >= 100
						? "සත 100ට වඩා! රු. 1කට මාරු කරමු."
						: "සල්ලි ටික පෙට්ටියට දාමු!"
					: `${moneyText(task.right)} එළියට ගමු!`;

	return (
		<div
			className="cash-box"
			data-demo={demo || undefined}
			data-done={finished || undefined}
		>
			<NimoSays
				mood={finished ? "cheer" : nudge ? "think" : "idle"}
				className="help-nimo"
			>
				{said}
			</NimoSays>
			<TheBox happy={finished} bump={bump} />
			<Drawers rupees={drawer.rupees} cents={drawer.cents} />
			{!demo && !finished && (
				<div className="cash-buttons">
					{adding
						? (["left", "right"] as const).map((side) => (
								<button
									key={side}
									type="button"
									className="cash-pour"
									disabled={done[side]}
									data-ghost={(hint && next === side) || undefined}
									onClick={() => pour(side)}
								>
									💰 {moneyText(side === "left" ? task.left : task.right)} දාමු
								</button>
							))
						: (["cents", "rupees"] as const).map((part) => (
								<button
									key={part}
									type="button"
									className="cash-pour"
									disabled={done[part]}
									data-ghost={(hint && next === part) || undefined}
									onClick={() => take(part)}
								>
									{part === "cents"
										? `සත ${centsOf(task.right)} ගමු`
										: `රු. ${rupeesOf(task.right)} ගමු`}
								</button>
							))}
					<button
						type="button"
						className="cash-exchange"
						disabled={!canExchange}
						data-ghost={(hint && next === "exchange") || undefined}
						onClick={exchange}
					>
						{adding ? "🔁 සත 100 → රු. 1" : "🔁 රු. 1 → සත 100"}
					</button>
				</div>
			)}
		</div>
	);
}

/** Each product's line total: its price for every kilo put in. */
const linesOf = (task: ShopTask, counts: Record<string, number>) =>
	Object.fromEntries(
		task.products.map((product) => [
			product.id,
			product.price * (counts[product.id] ?? 0),
		]),
	);

function ShopTill({
	task,
	demo = false,
	hint = false,
	evidence,
	onResponse,
}: BoardProps) {
	const [counts, setCounts] = useState<Record<string, number>>(() =>
		demo ? { ...task.wanted } : {},
	);
	const [paid, setPaid] = useState(demo);
	const [bump, setBump] = useState(0);
	const lines = linesOf(task, counts);
	const total = Object.values(lines).reduce((sum, line) => sum + line, 0);
	const change = Math.max(0, task.paid - total);

	useEffect(() => {
		onResponse(
			demo || !paid
				? null
				: shopResponse(task, counts, linesOf(task, counts), total, change),
		);
	}, [demo, paid, task, counts, total, change, onResponse]);

	const add = (id: string, step: 1 | -1) => {
		if (demo || paid) return;
		const next = Math.max(0, Math.min(9, (counts[id] ?? 0) + step));
		evidence.note("move");
		shopSounds.play(step > 0 ? "coin" : "back");
		if (step > 0) setBump(bump + 1);
		setCounts({ ...counts, [id]: next });
	};
	const pay = () => {
		if (demo || total === 0) return;
		evidence.note("move");
		shopSounds.play("note");
		if (task.requiresChange) shopSounds.play("spit", { delay: 0.5 });
		setBump(bump + 1);
		setPaid(true);
	};
	const next = task.products.find(
		(product) => (counts[product.id] ?? 0) < (task.wanted[product.id] ?? 0),
	);
	const said = paid
		? task.requiresChange
			? `නියමයි! ඉතිරි ${moneyText(change)} ආපහු ආවා!`
			: "නියමයි! හරියටම ගෙව්වා!"
		: "හැම kg එකකටම සල්ලි පෙට්ටියට දාමු!";

	return (
		<div
			className="cash-box cash-till"
			data-demo={demo || undefined}
			data-done={paid || undefined}
		>
			<NimoSays mood={paid ? "cheer" : "idle"} className="help-nimo">
				{said}
			</NimoSays>
			<TheBox happy={paid} bump={bump} />
			<div className="till-rows">
				{task.products
					.filter(
						(product) =>
							(task.wanted[product.id] ?? 0) > 0 ||
							(counts[product.id] ?? 0) > 0,
					)
					.map((product) => (
						<div key={product.id} className="till-row">
							<Art
								art={SACKS[product.id] ?? "sackRice"}
								className="till-sack"
							/>
							<span className="till-name">
								{product.name.split(" ")[0]} {task.wanted[product.id] ?? 0} kg
							</span>
							<button
								type="button"
								className="till-add"
								disabled={demo || paid}
								data-ghost={(hint && next?.id === product.id) || undefined}
								aria-label={`${product.name} ${moneyText(product.price)} දාමු`}
								onClick={() => add(product.id, 1)}
							>
								➕ {moneyText(product.price)}
							</button>
							<span className="till-line">
								× {counts[product.id] ?? 0} ={" "}
								<b>{moneyText(lines[product.id] ?? 0)}</b>
							</span>
							{!demo && !paid && (counts[product.id] ?? 0) > 0 && (
								<button
									type="button"
									className="till-back"
									aria-label={`${product.name} එකක් ආපහු`}
									onClick={() => add(product.id, -1)}
								>
									↩
								</button>
							)}
						</div>
					))}
			</div>
			<div className="till-foot">
				<strong className="till-total">මුළු ගණන {moneyText(total)}</strong>
				{task.requiresChange && (
					<span className="till-paid">
						<Money id="note-1000" /> {paid && <b>ඉතිරි {moneyText(change)}</b>}
					</span>
				)}
				{!demo && !paid && (
					<button
						type="button"
						className="till-pay"
						disabled={total === 0}
						data-ghost={(hint && !next && total > 0) || undefined}
						onClick={pay}
					>
						💰 ගෙවමු!
					</button>
				)}
			</div>
		</div>
	);
}
