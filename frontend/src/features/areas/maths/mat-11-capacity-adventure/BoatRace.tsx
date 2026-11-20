import { type CSSProperties, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { MissionOutcome } from "../../../mobile-learning-flow/landscape/useHardFirstEpisode";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { CapacityBoard } from "./CapacityBoard";
import {
	AmountCell,
	Art,
	Jug,
	Keypad,
	NimoSays,
	typeDigit,
} from "./waterParts";
import {
	arithmeticResponse,
	fillResponse,
	type WaterTask,
	waterText,
} from "./waterRules";
import { waterSounds } from "./waterSounds";

/** A big see-through tank with its amount on it and a tap that pours into the channel. */
function Tank({
	amount,
	level,
	open,
	label,
	tapLabel,
	disabled,
	onOpen,
}: {
	amount: number;
	level: number;
	open: boolean;
	label: string;
	tapLabel: string;
	disabled: boolean;
	onOpen(): void;
}) {
	return (
		<div className="race-tank" data-open={open || undefined}>
			<span className="race-tank-body">
				<span
					className="race-tank-water"
					style={{ height: `${Math.round(level * 70)}%` }}
				/>
				<Art art="tank" className="race-tank-art" />
				<b className="race-tank-label">{waterText(amount)}</b>
			</span>
			<button
				type="button"
				className="race-tap"
				disabled={disabled || open}
				aria-label={label}
				onClick={onOpen}
			>
				<Art art={open ? "pipeFull" : "pipeEmpty"} className="race-pipe" />
				<span className="race-tap-name">
					{open ? "🚿" : "🔧"} {tapLabel}
				</span>
			</button>
		</div>
	);
}

const BOATS = ["boatRed", "boatBlue", "boatYellow"] as const;

/**
 * බෝට්ටු තරගය! The boats wait at the start of an empty stone channel. Tank sums: open the tanks'
 * taps, then work out the water on the l | ml board with the 1000 ml ⇄ 1 l exchange. Filling: pour
 * jugs into the channel until it holds the amount asked for. Nothing is checked until the boats are
 * sent; then they race to the flag, or bob in place while Nimo scratches his head.
 */
export function BoatRace({
	task,
	prompt,
	returning,
	outcome,
	busy,
	evidence,
	onSubmit,
}: {
	task: WaterTask;
	prompt: string;
	returning: boolean;
	outcome: MissionOutcome;
	busy: boolean;
	evidence: ReturnType<typeof useMoveEvidence>;
	onSubmit(response: ConstructedResponse): void;
}) {
	const filling = task.kind === "fill";
	const adding = task.kind === "add";
	const [opened, setOpened] = useState<Record<string, boolean>>({});
	const [poured, setPoured] = useState<number[]>([]);
	const [cells, setCells] = useState<Record<string, string>>({});
	const [picked, setPicked] = useState("ml");
	const [exchanged, setExchanged] = useState(false);
	const [touched, setTouched] = useState(false);
	const playing = outcome === "playing";
	const ready = filling
		? poured.length > 0
		: adding
			? Boolean(opened.left && opened.right)
			: Boolean(opened.right);
	const pouredTotal = poured.reduce((sum, jug) => sum + jug, 0);
	const channelLevel = filling
		? Math.min(1, pouredTotal / (task.target * 1.25))
		: ready
			? 0.75
			: opened.left || opened.right
				? 0.4
				: 0;
	const value = (id: string) => Number(cells[id] || "0");
	const mood =
		outcome === "correct" ? "cheer" : outcome === "wrong" ? "think" : "idle";

	const open = (side: "left" | "right") => {
		if (!playing || opened[side]) return;
		evidence.note("move");
		waterSounds.play("tap-open");
		waterSounds.play("pour", { delay: 0.2 });
		setOpened({ ...opened, [side]: true });
	};
	const pour = (jug: number) => {
		if (!playing) return;
		evidence.note("move");
		waterSounds.play("pour");
		setTouched(true);
		setPoured([...poured, jug]);
	};
	const pourBack = () => {
		if (!playing || poured.length === 0) return;
		waterSounds.play("back");
		setPoured(poured.slice(0, -1));
	};
	const type = (digit: number) => {
		evidence.note("digit", picked === "ml" ? 0 : 1);
		setTouched(true);
		setCells({
			...cells,
			[picked]: typeDigit(cells[picked] ?? "", digit, picked === "ml" ? 4 : 3),
		});
	};
	const send = () => {
		waterSounds.play("whoosh");
		onSubmit(
			filling
				? fillResponse(task, poured)
				: arithmeticResponse(task, {
						operation: adding ? "add" : "subtract",
						ml: value("ml"),
						exchanged,
						litres: value("litres"),
					}),
		);
	};

	const said =
		outcome === "correct"
			? "හරියටම හරි! දැන් බෝට්ටු යවමු!"
			: outcome === "wrong"
				? "අපොයි! වතුර ගාණ පොඩ්ඩක් පැටලුණා."
				: `${returning ? "අලුත් තරගයක්! " : ""}${prompt}`;
	const cellProps = (id: string, label: string) => ({
		id,
		value: cells[id] ?? "",
		selected: picked === id,
		disabled: !playing || !ready,
		label,
		onSelect: setPicked,
	});

	return (
		<div
			className="boat-race"
			data-kind={task.kind}
			data-outcome={outcome}
			data-ready={ready || undefined}
		>
			<NimoSays mood={mood} className="race-nimo">
				{said}
			</NimoSays>
			{filling ? (
				<div className="race-jugs">
					<small>ජෝගුවක් තට්ටු කළාම වතුර පාරට වත් වෙනවා</small>
					<div className="race-jug-row">
						{task.jugs.map((jug) => (
							<button
								key={jug}
								type="button"
								className="race-jug"
								disabled={!playing}
								aria-label={`${waterText(jug)} වත් කරන්න`}
								onClick={() => pour(jug)}
							>
								<Jug size={jug} level={Math.min(1, 0.35 + jug / 1500)} />
							</button>
						))}
					</div>
					<div className="race-poured">
						<span>වත් කළා:</span>
						{poured.length === 0 ? (
							<i>—</i>
						) : (
							poured.map((jug, at) => (
								// biome-ignore lint/suspicious/noArrayIndexKey: the pour order is the identity.
								<b key={at} className="race-poured-chip">
									{waterText(jug)}
								</b>
							))
						)}
						{poured.length > 0 && playing && (
							<button
								type="button"
								className="race-pour-back"
								aria-label="අන්තිම ජෝගුව ආපහු"
								onClick={pourBack}
							>
								↩
							</button>
						)}
					</div>
				</div>
			) : (
				<div className="race-tanks">
					{adding ? (
						<>
							<Tank
								amount={task.left}
								level={opened.left ? 0.15 : 0.9}
								open={Boolean(opened.left)}
								label={`${waterText(task.left)} ටැංකියේ කරාම අරින්න`}
								tapLabel="කරාම අරිමු"
								disabled={!playing}
								onOpen={() => open("left")}
							/>
							<Tank
								amount={task.right}
								level={opened.right ? 0.1 : 0.6}
								open={Boolean(opened.right)}
								label={`${waterText(task.right)} ටැංකියේ කරාම අරින්න`}
								tapLabel="කරාම අරිමු"
								disabled={!playing}
								onOpen={() => open("right")}
							/>
						</>
					) : (
						<Tank
							amount={task.left}
							level={opened.right ? 0.55 : 0.95}
							open={Boolean(opened.right)}
							label={`${waterText(task.right)} වතුර පාරට අරින්න`}
							tapLabel={`${waterText(task.right)} වතුර පාරට`}
							disabled={!playing}
							onOpen={() => open("right")}
						/>
					)}
				</div>
			)}
			<div
				className="race-channel"
				style={{ "--level": channelLevel } as CSSProperties}
			>
				<Art art="channel" className="race-channel-art" />
				<span className="race-channel-water" />
				<Art art="fishOrange" className="race-fish" />
				<Art art="splash" className="race-splash" />
				<span className="race-flag" aria-hidden="true">
					🏁
				</span>
				{BOATS.map((boat, at) => (
					<span
						key={boat}
						className="race-boat"
						style={{ "--lane": at } as CSSProperties}
					>
						<Art art={boat} className="race-boat-art" />
					</span>
				))}
			</div>
			{!filling && (
				<div className="race-register" data-locked={!ready || undefined}>
					<CapacityBoard
						operation={adding ? "add" : "subtract"}
						left={task.left}
						right={task.right}
						exchanged={exchanged}
						millilitres={value("ml")}
						disabled={!playing || !ready}
						title={adding ? "මුළු වතුර කීයද?" : "ටැංකියේ ඉතිරි කීයද?"}
						litresCell={<AmountCell {...cellProps("litres", "ලීටර්")} />}
						millilitresCell={<AmountCell {...cellProps("ml", "මිලිලීටර්")} />}
						onExchange={(next) => {
							evidence.note("carry");
							setTouched(true);
							setExchanged(next);
						}}
					/>
					<Keypad
						disabled={!playing || !ready}
						onDigit={type}
						onRubOut={() =>
							setCells({
								...cells,
								[picked]: (cells[picked] ?? "").slice(0, -1),
							})
						}
					/>
				</div>
			)}
			{ready && (
				<button
					type="button"
					className="game-action race-send"
					disabled={busy || !touched || !playing}
					onClick={send}
				>
					🚤 බෝට්ටු යවමු!
				</button>
			)}
		</div>
	);
}
