import { type CSSProperties, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { MissionOutcome } from "../../../mobile-learning-flow/landscape/useHardFirstEpisode";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { MassBoard } from "./MassBoard";
import { SURPRISES } from "./weighArt";
import {
	AmountCell,
	Art,
	Box,
	Keypad,
	NimoSays,
	typeDigit,
} from "./weighParts";
import {
	arithmeticResponse,
	loadResponse,
	massText,
	type WeighTask,
} from "./weighRules";
import { weighSounds } from "./weighSounds";

type Spot = "ground" | "scale" | "cart";

/**
 * කරත්තේ පෙට්ටි පටවමු! Mystery boxes wait beside the big platform scale and Nimo's cart. Tap a
 * box: it goes on the scale (its weight lights up), then into the cart, which sinks a little.
 * Unloading: the cart is full and one box comes off. Then the child works out the weight on the
 * kg | g board (and, when loading, how much more the cart can take). Nothing is checked until the
 * cart sets off; then it rolls away and a box pops open, or it wobbles while Nimo thinks.
 */
export function ParcelCart({
	task,
	prompt,
	returning,
	outcome,
	busy,
	evidence,
	onSubmit,
}: {
	task: WeighTask;
	prompt: string;
	returning: boolean;
	outcome: MissionOutcome;
	busy: boolean;
	evidence: ReturnType<typeof useMoveEvidence>;
	onSubmit(response: ConstructedResponse): void;
}) {
	const unloading = task.kind === "subtract";
	const loading = task.kind === "load";
	const [spots, setSpots] = useState<Record<"a" | "b", Spot>>(() =>
		unloading ? { a: "cart", b: "cart" } : { a: "ground", b: "ground" },
	);
	const [cells, setCells] = useState<Record<string, string>>({});
	const [picked, setPicked] = useState("g");
	const [exchanged, setExchanged] = useState(false);
	const [touched, setTouched] = useState(false);
	const playing = outcome === "playing";
	const ready = unloading
		? spots.b === "ground"
		: spots.a === "cart" && spots.b === "cart";
	const onScale = (["a", "b"] as const).find((box) => spots[box] === "scale");
	const weightOf = (box: "a" | "b") =>
		unloading
			? box === "a"
				? task.left - task.right
				: task.right
			: box === "a"
				? task.left
				: task.right;
	const inCart = (["a", "b"] as const).filter(
		(box) => spots[box] === "cart",
	).length;
	const value = (id: string) => Number(cells[id] || "0");
	const mood =
		outcome === "correct" ? "cheer" : outcome === "wrong" ? "think" : "idle";
	const surprise = SURPRISES[(task.left + task.right) % SURPRISES.length];

	const move = (box: "a" | "b") => {
		if (!playing) return;
		const now = spots[box];
		if (unloading) {
			if (box !== "b" || now === "ground") return;
			evidence.note("move");
			weighSounds.play(now === "cart" ? "pick" : "thud");
			setSpots({ ...spots, b: now === "cart" ? "scale" : "ground" });
			return;
		}
		if (now === "cart") return;
		if (now === "ground" && onScale) return;
		evidence.note("move");
		weighSounds.play(now === "ground" ? "beep" : "thud");
		setSpots({ ...spots, [box]: now === "ground" ? "scale" : "cart" });
	};
	const type = (digit: number) => {
		evidence.note("digit", ["g", "kg", "roomKg", "roomG"].indexOf(picked));
		setTouched(true);
		setCells({
			...cells,
			[picked]: typeDigit(cells[picked] ?? "", digit, picked === "g" ? 4 : 3),
		});
	};
	const working = {
		operation: unloading ? ("subtract" as const) : ("add" as const),
		g: value("g"),
		exchanged,
		kg: value("kg"),
	};
	const send = () => {
		weighSounds.play("wheels");
		onSubmit(
			loading
				? loadResponse(task, working, value("roomKg") * 1000 + value("roomG"))
				: arithmeticResponse(task, working),
		);
	};

	const said =
		outcome === "correct"
			? "හරියටම හරි! දැන් යමු!"
			: outcome === "wrong"
				? "අපොයි! බර පොඩ්ඩක් පැටලුණා."
				: `${returning ? "අලුත් ගමනක්! " : ""}${prompt}`;
	const cellProps = (id: string, label: string) => ({
		id,
		value: cells[id] ?? "",
		selected: picked === id,
		disabled: !playing || !ready,
		label,
		onSelect: setPicked,
	});
	// The box left in the cart when unloading weighs the answer, so it stays "?" until the cart goes.
	const boxLabel = (box: "a" | "b") =>
		(spots[box] === "ground" && !unloading) ||
		(unloading && box === "a" && outcome !== "correct")
			? null
			: weightOf(box);

	return (
		<div
			className="parcel-cart"
			data-kind={task.kind}
			data-outcome={outcome}
			data-ready={ready || undefined}
		>
			<NimoSays mood={mood} className="cart-nimo">
				{said}
			</NimoSays>
			<div className="cart-yard">
				<div className="cart-ground">
					{(["a", "b"] as const).map((box) =>
						spots[box] === "ground" ? (
							<button
								key={box}
								type="button"
								className="cart-box"
								disabled={!playing || Boolean(onScale)}
								aria-label={`පෙට්ටිය ${box === "a" ? 1 : 2} තරාදියට`}
								onClick={() => move(box)}
							>
								<Box grams={unloading ? weightOf(box) : null} />
							</button>
						) : null,
					)}
					{spots.a !== "ground" && spots.b !== "ground" && !unloading && (
						<span className="cart-hint">👉 කරත්තේට!</span>
					)}
				</div>
				<div className="cart-scale">
					<span className="cart-scale-screen">
						{onScale ? massText(weightOf(onScale)) : "0 g"}
					</span>
					{onScale && (
						<button
							type="button"
							className="cart-box cart-box-on-scale"
							disabled={!playing}
							aria-label={
								unloading
									? "පෙට්ටිය බිමට"
									: `පෙට්ටිය ${onScale === "a" ? 1 : 2} කරත්තේට`
							}
							onClick={() => move(onScale)}
						>
							<Box grams={weightOf(onScale)} />
						</button>
					)}
					<Art art="platformScale" className="cart-scale-art" />
				</div>
				<div
					className="the-cart"
					style={{ "--sink": inCart } as CSSProperties}
					data-rolling={outcome === "correct" || undefined}
					data-wobble={outcome === "wrong" || undefined}
				>
					<span className="cart-load">
						{(["a", "b"] as const).map((box) =>
							spots[box] === "cart" ? (
								<button
									key={box}
									type="button"
									className="cart-box cart-box-in"
									disabled={!playing || !unloading || box === "a"}
									aria-label={box === "b" ? "පෙට්ටිය බස්සමු" : "පෙට්ටිය"}
									onClick={() => move(box)}
								>
									<Box grams={boxLabel(box)} />
								</button>
							) : null,
						)}
					</span>
					<Art art="cart" className="cart-art" />
					{unloading && (
						<b className="cart-total">කරත්තේ: {massText(task.left)}</b>
					)}
					{loading && (
						<b className="cart-total">උපරිම: {massText(task.capacity)}</b>
					)}
				</div>
				{outcome === "correct" && (
					<span className="cart-surprise" aria-hidden="true">
						<Art art="starBurst" className="cart-burst" />
						<i>{surprise}</i>
					</span>
				)}
			</div>
			<div className="cart-register" data-locked={!ready || undefined}>
				<div className="cart-boards">
					<MassBoard
						operation={unloading ? "subtract" : "add"}
						left={task.left}
						right={task.right}
						exchanged={exchanged}
						grams={value("g")}
						disabled={!playing || !ready}
						title={unloading ? "දැන් බර කීයද?" : "මුළු බර කීයද?"}
						kilogramsCell={<AmountCell {...cellProps("kg", "කිලෝග්‍රෑම්")} />}
						gramsCell={<AmountCell {...cellProps("g", "ග්‍රෑම්")} />}
						onExchange={(next) => {
							evidence.note("carry");
							setTouched(true);
							setExchanged(next);
						}}
					/>
					{loading && (
						<div className="room-left">
							<span>තව කීයක් දාන්න පුළුවන්ද?</span>
							<AmountCell {...cellProps("roomKg", "ඉතිරි කිලෝග්‍රෑම්")} unit="kg" />
							<AmountCell {...cellProps("roomG", "ඉතිරි ග්‍රෑම්")} unit="g" />
						</div>
					)}
				</div>
				<Keypad
					disabled={!playing || !ready}
					onDigit={type}
					onRubOut={() =>
						setCells({ ...cells, [picked]: (cells[picked] ?? "").slice(0, -1) })
					}
				/>
			</div>
			{ready && (
				<button
					type="button"
					className="game-action cart-send"
					disabled={busy || !touched || !playing}
					onClick={send}
				>
					🛒 කරත්තේ යවමු!
				</button>
			)}
		</div>
	);
}
