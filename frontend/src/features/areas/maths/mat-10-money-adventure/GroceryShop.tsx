import { useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { MissionOutcome } from "../../../mobile-learning-flow/landscape/useHardFirstEpisode";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { MoneyBoard } from "./MoneyBoard";
import { ITEMS, SACKS, type ShopArtKey } from "./shopArt";
import { AmountCell, Art, Keypad, NimoSays, typeDigit } from "./shopParts";
import {
	arithmeticResponse,
	moneyText,
	type ShopTask,
	shopResponse,
} from "./shopRules";
import { shopSounds } from "./shopSounds";

type Shelf = { id: string; art: ShopArtKey; price: number; tag: string };

/** What stands on the shelf: the grocery sacks, two things to add up, or the one thing bought. */
function shelfOf(task: ShopTask): Shelf[] {
	if (task.kind === "shop")
		return task.products.map((product) => ({
			id: product.id,
			art: SACKS[product.id] ?? "sackRice",
			price: product.price,
			tag: product.name,
		}));
	const first = ITEMS[task.left % ITEMS.length] ?? "itemTeapot";
	const second = ITEMS[(task.left + 1) % ITEMS.length] ?? "itemPot";
	return task.kind === "add"
		? [
				{ id: "a", art: first, price: task.left, tag: "" },
				{ id: "b", art: second, price: task.right, tag: "" },
			]
		: [{ id: "b", art: first, price: task.right, tag: "" }];
}

const NAME = (tag: string) => tag.split(" ")[0] ?? tag;

/**
 * බඩු මල්ල පුරවමු! The shelf holds the shop's things with price tags. The child taps each thing
 * into the basket (a sack gives one 1 kg packet a tap), then works out the bill on the cash
 * register: each line and the total, or a rupees-and-cents sum with the 100 cents ⇄ Rs. 1
 * exchange. Nothing is checked until Nimo pays; then he packs his bag, or scratches his head.
 */
export function GroceryShop({
	task,
	prompt,
	returning,
	outcome,
	busy,
	evidence,
	onSubmit,
}: {
	task: ShopTask;
	prompt: string;
	returning: boolean;
	outcome: MissionOutcome;
	busy: boolean;
	evidence: ReturnType<typeof useMoveEvidence>;
	onSubmit(response: ConstructedResponse): void;
}) {
	const shelf = shelfOf(task);
	const shopping = task.kind === "shop";
	const [basket, setBasket] = useState<Record<string, number>>({});
	const [cells, setCells] = useState<Record<string, string>>({});
	const [exchanged, setExchanged] = useState(false);
	const [picked, setPicked] = useState<string | null>(null);
	const [touched, setTouched] = useState(false);
	const playing = outcome === "playing";
	const inBasket = shelf.filter((thing) => (basket[thing.id] ?? 0) > 0);
	const ready = shopping
		? inBasket.length > 0
		: inBasket.length === shelf.length;
	const cellIds = shopping
		? [
				...inBasket.map((thing) => `line:${thing.id}`),
				"total",
				...(task.requiresChange ? ["change"] : []),
			]
		: ["cents", "rupees"];
	const selected =
		picked && cellIds.includes(picked) ? picked : (cellIds[0] ?? null);
	const value = (id: string) => Number(cells[id] || "0");
	const mood =
		outcome === "correct" ? "cheer" : outcome === "wrong" ? "think" : "idle";

	const put = (thing: Shelf, step: 1 | -1) => {
		if (!playing) return;
		const now = basket[thing.id] ?? 0;
		const next = Math.max(0, Math.min(shopping ? 9 : 1, now + step));
		if (next === now) return;
		evidence.note("move");
		shopSounds.play(step > 0 ? "basket" : "back");
		setBasket({ ...basket, [thing.id]: next });
	};
	const type = (digit: number) => {
		if (!selected) return;
		evidence.note("digit", cellIds.indexOf(selected));
		setTouched(true);
		setCells({
			...cells,
			[selected]: typeDigit(
				cells[selected] ?? "",
				digit,
				selected === "cents" ? 3 : 5,
			),
		});
	};
	const rubOut = () => {
		if (!selected) return;
		setCells({ ...cells, [selected]: (cells[selected] ?? "").slice(0, -1) });
	};
	const pay = () => {
		shopSounds.play("pay");
		if (shopping) {
			const lines = Object.fromEntries(
				inBasket.map((thing) => [thing.id, value(`line:${thing.id}`) * 100]),
			);
			onSubmit(
				shopResponse(
					task,
					basket,
					lines,
					value("total") * 100,
					value("change") * 100,
				),
			);
			return;
		}
		onSubmit(
			arithmeticResponse(task, {
				operation: task.kind === "subtract" ? "subtract" : "add",
				cents: value("cents"),
				exchanged,
				rupees: value("rupees"),
			}),
		);
	};

	const said =
		outcome === "correct"
			? "හරියටම හරි! බඩු ටික මල්ලට දාමු!"
			: outcome === "wrong"
				? "අපොයි! ගණන පොඩ්ඩක් පැටලුණා."
				: `${returning ? "අලුත් ලැයිස්තුවක්! " : ""}${prompt}`;
	const cellProps = (id: string, label: string) => ({
		id,
		value: cells[id] ?? "",
		selected: selected === id,
		disabled: !playing || !ready,
		label,
		onSelect: setPicked,
	});

	return (
		<div
			className="grocery-shop"
			data-kind={task.kind}
			data-outcome={outcome}
			data-ready={ready || undefined}
		>
			<NimoSays mood={mood} className="shop-nimo">
				{said}
			</NimoSays>
			<div className="shop-shelf">
				{task.kind === "subtract" && (
					<span className="shop-wallet">
						<Art art="wallet" className="shop-wallet-art" />
						<b>{moneyText(task.left)}</b>
					</span>
				)}
				{shelf.map((thing) => (
					<button
						key={thing.id}
						type="button"
						className="shelf-thing"
						disabled={!playing || (!shopping && (basket[thing.id] ?? 0) > 0)}
						aria-label={`${thing.tag ? NAME(thing.tag) : "බඩුව"} කූඩෙට`}
						onClick={() => put(thing, 1)}
					>
						<span className="shelf-picture">
							<Art art={thing.art} className="shelf-art" />
							{shopping && <b className="sack-label">{NAME(thing.tag)}</b>}
						</span>
						<span className="price-tag">
							{thing.tag && <small>{thing.tag} –</small>}
							{moneyText(thing.price)}
						</span>
					</button>
				))}
			</div>
			<div
				className="shop-basket"
				data-packed={outcome === "correct" || undefined}
			>
				<Art art="basket" className="basket-art" />
				<div className="basket-things">
					{inBasket.flatMap((thing) =>
						Array.from({ length: basket[thing.id] ?? 0 }, (_, at) => (
							<button
								// biome-ignore lint/suspicious/noArrayIndexKey: packets of one product are interchangeable.
								key={`${thing.id}-${at}`}
								type="button"
								className="basket-thing"
								disabled={!playing}
								aria-label={`${thing.tag ? NAME(thing.tag) : "බඩුව"} ආපහු`}
								onClick={() => put(thing, -1)}
							>
								<span className="shelf-picture">
									<Art art={thing.art} className="basket-thing-art" />
									{shopping && <b className="sack-label">{NAME(thing.tag)}</b>}
								</span>
								{shopping && <small>1 kg</small>}
							</button>
						)),
					)}
				</div>
				{inBasket.length === 0 && (
					<span className="basket-hint" aria-hidden="true">
						👆 බඩු කූඩෙට දාමු
					</span>
				)}
			</div>
			<div className="shop-register" data-locked={!ready || undefined}>
				{shopping ? (
					<div className="bill">
						<strong className="bill-title">🧾 බිල</strong>
						{inBasket.map((thing) => (
							<div key={thing.id} className="bill-row">
								<span>
									{NAME(thing.tag)} {basket[thing.id]} kg ×{" "}
									{moneyText(thing.price)}
								</span>
								<AmountCell
									{...cellProps(`line:${thing.id}`, `${NAME(thing.tag)} ගණන`)}
									unit="රු."
								/>
							</div>
						))}
						<div className="bill-row bill-total">
							<span>මුළු ගණන</span>
							<AmountCell {...cellProps("total", "මුළු ගණන")} unit="රු." />
						</div>
						{task.requiresChange && (
							<div className="bill-row bill-change">
								<span>නිමෝ දෙන්නේ {moneyText(task.paid)} · ඉතිරි</span>
								<AmountCell {...cellProps("change", "ඉතිරි")} unit="රු." />
							</div>
						)}
					</div>
				) : (
					<MoneyBoard
						operation={task.kind === "subtract" ? "subtract" : "add"}
						left={task.left}
						right={task.right}
						exchanged={exchanged}
						cents={value("cents")}
						disabled={!playing || !ready}
						title={task.kind === "subtract" ? "ඉතිරි කීයද?" : "දෙකටම කීයද?"}
						rupeesCell={<AmountCell {...cellProps("rupees", "රුපියල්")} />}
						centsCell={<AmountCell {...cellProps("cents", "සත")} />}
						onExchange={(next) => {
							evidence.note("carry");
							setTouched(true);
							setExchanged(next);
						}}
					/>
				)}
				<Keypad
					disabled={!playing || !ready}
					onDigit={type}
					onRubOut={rubOut}
				/>
			</div>
			{ready && (
				<button
					type="button"
					className="game-action shop-pay"
					disabled={busy || !touched || !playing}
					onClick={pay}
				>
					💰 ගෙවමු!
				</button>
			)}
		</div>
	);
}
