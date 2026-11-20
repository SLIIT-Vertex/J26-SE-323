import { type CSSProperties, useEffect, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { Art, BLOCK_LABEL, type BlockSize } from "./villageParts";
import {
	conversionResponse,
	metrePieces,
	relationResponse,
	type VillageTask,
} from "./villageRules";
import { villageSounds } from "./villageSounds";

type Evidence = ReturnType<typeof useMoveEvidence>;
type BoardProps = {
	task: VillageTask;
	demo?: boolean;
	hint?: boolean;
	evidence: Evidence;
	onResponse(response: ConstructedResponse | null): void;
};

/** Tikki talks in a bubble; his face shows how it is going. */
function Tikki({
	mood,
	line,
	at,
}: {
	mood: "idle" | "happy" | "think";
	line: string;
	/** How far along the strip Tikki has crawled (0–1). */
	at: number;
}) {
	return (
		<span
			className="tikki"
			data-mood={mood}
			data-side={at > 0.75 ? "right" : "left"}
			style={{ "--crawl": at } as CSSProperties}
		>
			<span className="tikki-says" role="status">
				{line}
			</span>
			{mood === "happy" && (
				<span className="leaf-burst" aria-hidden="true">
					{Array.from({ length: 6 }, (_, at) => (
						<Art
							// biome-ignore lint/suspicious/noArrayIndexKey: the leaves are interchangeable.
							key={at}
							art={at % 2 ? "leafGold" : "leafGreen"}
							className="leaf"
						/>
					))}
				</span>
			)}
			<Art
				art={
					mood === "happy"
						? "tikkiHappy"
						: mood === "think"
							? "tikkiThink"
							: "tikkiIdle"
				}
				className="tikki-art"
			/>
		</span>
	);
}

/**
 * ටික්කි එක්ක දුර මනිමු! Tikki the snail loves measuring. Units: pull the tape along a 1 m fence
 * piece (how many cm?), then join 100 m pieces up to Tikki's 1 km flag (how many m?). Building a
 * distance: join 1 km and metre pieces until the strip is the asked number of metres.
 */
export function TikkiGarden(props: BoardProps) {
	return props.task.kind === "relation" ? (
		<TapeAndFlag {...props} />
	) : (
		<BuildDistance {...props} />
	);
}

const CM_STEP = 10;

function TapeAndFlag({
	demo = false,
	hint = false,
	evidence,
	onResponse,
}: BoardProps) {
	const [tape, setTape] = useState(demo ? 100 : 0);
	const [tapeDone, setTapeDone] = useState(demo);
	const [joined, setJoined] = useState(demo ? 1000 : 0);
	const [flagDone, setFlagDone] = useState(demo);

	useEffect(() => {
		onResponse(demo || !flagDone ? null : relationResponse(tape, joined));
	}, [demo, flagDone, tape, joined, onResponse]);

	const pull = (step: number) => {
		if (demo || tapeDone) return;
		const next = Math.max(0, Math.min(150, tape + step));
		if (next === tape) return;
		evidence.note("move");
		villageSounds.play("tape");
		setTape(next);
	};
	const join = (step: number) => {
		if (demo || !tapeDone || flagDone) return;
		const next = Math.max(0, Math.min(1500, joined + step));
		if (next === joined) return;
		evidence.note("move");
		villageSounds.play(step > 0 ? "snap" : "back");
		setJoined(next);
	};

	const line = demo
		? "1 m = 100 cm. 1 km = 1000 m!"
		: !tapeDone
			? "පටිය ඇදලා වැටේ දිග මනිමු! වැට මීටර් 1යි."
			: !flagDone
				? "දැන් මගේ කොඩියට 100 m කෑලි එකතු කරමු! කොඩිය 1 km."
				: "හරියටම හරි! ටික්කිත් සතුටුයි!";
	const mood = flagDone ? "happy" : "idle";

	return (
		<div className="tikki-garden" data-demo={demo || undefined}>
			<div className="garden-tape">
				<Art art="fence" className="garden-fence" />
				<span className="tape-case" aria-hidden="true" />
				<span
					className="tape-strip"
					style={{ "--cm": tape } as CSSProperties}
					aria-hidden="true"
				>
					{Array.from({ length: tape / CM_STEP + 1 }, (_, at) => (
						// biome-ignore lint/suspicious/noArrayIndexKey: the tick order is the identity.
						<i key={at} style={{ "--at": at } as CSSProperties} />
					))}
				</span>
				<strong className="tape-reading">{tape} cm</strong>
			</div>
			{!demo && !tapeDone && (
				<div className="garden-buttons">
					<button
						type="button"
						className="garden-step"
						onClick={() => pull(-CM_STEP)}
					>
						◀ 10 cm
					</button>
					<button
						type="button"
						className="garden-step"
						data-ghost={(hint && tape < 100) || undefined}
						onClick={() => pull(CM_STEP)}
					>
						පටිය ඇදමු ▶ 10 cm
					</button>
					<button
						type="button"
						className="garden-done"
						disabled={tape === 0}
						data-ghost={(hint && tape === 100) || undefined}
						onClick={() => {
							villageSounds.play("tap");
							evidence.note("move");
							setTapeDone(true);
						}}
					>
						✓ මැන්නා
					</button>
				</div>
			)}
			{tapeDone && (
				<p className="garden-fact">
					1 m = <strong>{tape} cm</strong>
				</p>
			)}
			{tapeDone && (
				<div
					className="garden-strip"
					style={{ "--pieces": 10 } as CSSProperties}
				>
					{Array.from({ length: joined / 100 }, (_, at) => (
						// biome-ignore lint/suspicious/noArrayIndexKey: the pieces are interchangeable.
						<span key={at} className="strip-piece" data-size={100}>
							100 m
						</span>
					))}
					<Art art="flag" className="strip-flag" />
					<Tikki mood={mood} line={line} at={Math.min(1, joined / 1000)} />
				</div>
			)}
			{!tapeDone && <Tikki mood={mood} line={line} at={0} />}
			{tapeDone && !flagDone && !demo && (
				<div className="garden-buttons">
					<button
						type="button"
						className="garden-step"
						onClick={() => join(-100)}
					>
						↩ 100 m
					</button>
					<button
						type="button"
						className="garden-step"
						data-ghost={(hint && joined < 1000) || undefined}
						onClick={() => join(100)}
					>
						➕ 100 m කෑල්ලක්
					</button>
					<button
						type="button"
						className="garden-done"
						disabled={joined === 0}
						data-ghost={(hint && joined === 1000) || undefined}
						onClick={() => {
							villageSounds.play("sparkle");
							evidence.note("move");
							setFlagDone(true);
						}}
					>
						✓ කොඩියට ආවා
					</button>
				</div>
			)}
			{flagDone && (
				<p className="garden-fact">
					1 km = <strong>{joined} m</strong>
				</p>
			)}
		</div>
	);
}

const SIZES: BlockSize[] = ["km", 100, 10, 1];
const METRES: Record<BlockSize, number> = { km: 1000, 100: 100, 10: 10, 1: 1 };

function BuildDistance({
	task,
	demo = false,
	hint = false,
	evidence,
	onResponse,
}: BoardProps) {
	const target = task.total;
	const [pieces, setPieces] = useState<Record<BlockSize, number>>(() => {
		if (!demo) return { km: 0, 100: 0, 10: 0, 1: 0 };
		const { hundreds, tens, ones } = metrePieces(target % 1000);
		return { km: Math.floor(target / 1000), 100: hundreds, 10: tens, 1: ones };
	});
	const total = SIZES.reduce(
		(sum, size) => sum + pieces[size] * METRES[size],
		0,
	);
	const metres = total - pieces.km * 1000;
	const canSwap = pieces[100] >= 10;
	// The right length is not finished until ten 100 m pieces are swapped for 1 km.
	const done = total === target && metres < 1000;

	useEffect(() => {
		onResponse(
			demo || !done ? null : conversionResponse(task, pieces.km, metres),
		);
	}, [demo, done, task, pieces.km, metres, onResponse]);

	const add = (size: BlockSize, step: 1 | -1) => {
		if (demo || pieces[size] + step < 0) return;
		evidence.note("move");
		villageSounds.play(step > 0 ? "snap" : "back");
		setPieces({ ...pieces, [size]: pieces[size] + step });
	};
	const swap = () => {
		if (demo || !canSwap) return;
		evidence.note("carry");
		villageSounds.play("exchange");
		setPieces({ ...pieces, km: pieces.km + 1, 100: pieces[100] - 10 });
	};

	// The next right piece, shown faintly on a help stage.
	const want = metrePieces(target % 1000);
	const wanted: Record<BlockSize, number> = {
		km: Math.floor(target / 1000),
		100: want.hundreds,
		10: want.tens,
		1: want.ones,
	};
	const next = SIZES.find((size) => pieces[size] < wanted[size]);
	const line = demo
		? `${target} m = ${pieces.km} km ${metres} m`
		: done
			? "හරියටම හරි! ටික්කිත් සතුටුයි!"
			: total > target
				? "අපොයි, වැඩියි! කෑල්ලක් අයින් කරමු."
				: canSwap
					? "100 m කෑලි 10ක් = 1 km! මාරු කරමු."
					: `මීටර් ${target}ක් හදමු!`;

	return (
		<div
			className="tikki-garden"
			data-demo={demo || undefined}
			data-done={done || undefined}
		>
			<div className="garden-strip garden-build">
				{SIZES.flatMap((size) =>
					Array.from({ length: Math.min(pieces[size], 12) }, (_, at) => (
						<span
							// biome-ignore lint/suspicious/noArrayIndexKey: pieces of one size are interchangeable.
							key={`${size}-${at}`}
							className="strip-piece"
							data-size={size}
						>
							{BLOCK_LABEL[size]}
						</span>
					)),
				)}
				<Art art="flag" className="strip-flag" />
				<Tikki
					mood={done ? "happy" : total > target ? "think" : "idle"}
					line={line}
					at={Math.min(1, total / target)}
				/>
			</div>
			<p className="garden-fact">
				<strong>{total} m</strong> = {pieces.km} km {metres} m
			</p>
			{!demo && (
				<div className="garden-buttons">
					{SIZES.map((size) => (
						<span key={size} className="garden-piece-pair">
							<button
								type="button"
								className="garden-piece"
								data-size={size}
								data-ghost={(hint && next === size) || undefined}
								aria-label={`${BLOCK_LABEL[size]} කෑල්ලක් එකතු කරන්න`}
								onClick={() => add(size, 1)}
							>
								➕ {BLOCK_LABEL[size]}
							</button>
							<button
								type="button"
								className="garden-piece-back"
								disabled={pieces[size] === 0}
								aria-label={`${BLOCK_LABEL[size]} කෑල්ලක් අයින් කරන්න`}
								onClick={() => add(size, -1)}
							>
								↩
							</button>
						</span>
					))}
					<button
						type="button"
						className="garden-done"
						disabled={!canSwap}
						onClick={swap}
					>
						🔁 100 m × 10 → 1 km
					</button>
				</div>
			)}
		</div>
	);
}
