import {
	type CSSProperties,
	useEffect,
	useMemo,
	useRef,
	useState,
} from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { FRIENDS } from "./bookArt";
import { Art, Frac } from "./bookParts";
import { type BookPage, groupingResponse, pageAnswer } from "./bookRules";
import { bookSounds } from "./bookSounds";

type Evidence = ReturnType<typeof useMoveEvidence>;

/**
 * The Sticker Sharing Party: the sticker friends each hold an envelope and the stickers wait on the
 * table. The child drags (or taps an envelope to drop) stickers in one at a time; equal shares make
 * every friend happy, and each envelope is then one quarter (or one half). For a quarter table the
 * child then gathers envelopes to show 1/4, 2/4 and 3/4 of the stickers.
 */
export function StickerParty({
	page,
	demo = false,
	hint = false,
	evidence,
	onResponse,
}: {
	page: BookPage;
	demo?: boolean;
	hint?: boolean;
	evidence: Evidence;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const groups = page.kind === "grouping" ? page.denominator : 4;
	const total =
		page.kind === "grouping" || page.kind === "quarter_table" ? page.total : 0;
	const share = Math.floor(total / groups);
	const table = page.kind === "quarter_table";
	const [envelopes, setEnvelopes] = useState<number[]>(() =>
		Array.from({ length: groups }, () => (demo ? share : 0)),
	);
	const [rows, setRows] = useState<number[][]>(() =>
		demo ? [[0], [0, 1], [0, 1, 2]] : [[], [], []],
	);
	const [drag, setDrag] = useState<{ x: number; y: number } | null>(null);
	const board = useRef<HTMLDivElement>(null);
	const latest = useRef(envelopes);
	latest.current = envelopes;

	const onTable = total - envelopes.reduce((sum, count) => sum + count, 0);
	const shared = onTable === 0;
	const equal = shared && envelopes.every((count) => count === envelopes[0]);
	const rowSums = rows.map((picked) =>
		picked.reduce((sum, group) => sum + (envelopes[group] ?? 0), 0),
	);
	const answer = useMemo(() => pageAnswer(page), [page]);

	useEffect(() => {
		if (demo) {
			onResponse(null);
			return;
		}
		if (table) {
			onResponse(
				shared && rows.every((picked) => picked.length > 0)
					? {
							kind: "fraction_quantity_table",
							total,
							// Each row is the stickers in the envelopes the child gathered for it.
							quarter_values: rows.map((picked) =>
								picked.reduce((sum, group) => sum + (envelopes[group] ?? 0), 0),
							) as [number, number, number],
						}
					: null,
			);
			return;
		}
		onResponse(groupingResponse(page, envelopes));
	}, [demo, table, shared, rows, envelopes, total, page, onResponse]);

	const drop = (group: number) => {
		if (demo) return;
		const now = latest.current;
		if (total - now.reduce((sum, count) => sum + count, 0) <= 0) {
			bookSounds.play("boing");
			return;
		}
		evidence.note("move");
		bookSounds.play("drop");
		const next = now.map((count, at) => (at === group ? count + 1 : count));
		setEnvelopes(next);
		const done = next.reduce((sum, count) => sum + count, 0) === total;
		if (done && next.every((count) => count === next[0]))
			bookSounds.play("sparkle", { delay: 0.2 });
		if (done && !next.every((count) => count === next[0]))
			bookSounds.play("hmm", { delay: 0.2 });
	};
	const takeBack = (group: number) => {
		if (demo || (envelopes[group] ?? 0) === 0) return;
		evidence.note("digit", group);
		bookSounds.play("back");
		setEnvelopes(
			envelopes.map((count, at) => (at === group ? count - 1 : count)),
		);
		setRows([[], [], []]);
	};
	const pickRow = (row: number, group: number) => {
		if (demo) return;
		evidence.note("move");
		bookSounds.play("pick");
		setRows(
			rows.map((picked, at) =>
				at !== row
					? picked
					: picked.includes(group)
						? picked.filter((g) => g !== group)
						: [...picked, group].sort(),
			),
		);
	};

	// Dragging a sticker: it follows the finger and drops into the envelope under it.
	useEffect(() => {
		if (!drag) return;
		const move = (event: PointerEvent) =>
			setDrag({ x: event.clientX, y: event.clientY });
		const up = (event: PointerEvent) => {
			setDrag(null);
			const target = document
				.elementFromPoint(event.clientX, event.clientY)
				?.closest<HTMLElement>("[data-envelope]");
			if (target?.dataset.envelope) drop(Number(target.dataset.envelope));
		};
		window.addEventListener("pointermove", move);
		window.addEventListener("pointerup", up, { once: true });
		return () => {
			window.removeEventListener("pointermove", move);
			window.removeEventListener("pointerup", up);
		};
	});

	const message = demo
		? "හැම යාළුවෙක්ටම සමාන ස්ටිකර් ගාණක්."
		: !shared
			? `ස්ටිකර් ${total}ක් ${groups} දෙනා අතර සමානව බෙදමු!`
			: !equal
				? "අයියෝ! හැමෝටම සමාන නෑ. ආපහු ගෙන බලමු."
				: table
					? "හැමෝටම සමානයි! දැන් ලියුම් කවර එකතු කරලා බලමු."
					: "නියමයි! හැමෝටම සමාන ස්ටිකර් ගාණක් ලැබුණා!";

	return (
		<div
			className="sticker-party"
			ref={board}
			data-demo={demo || undefined}
			data-happy={equal || undefined}
		>
			<p className="book-message" role="status">
				{message}
			</p>
			<div
				className="sticker-friends"
				style={{ "--groups": groups } as CSSProperties}
			>
				{envelopes.map((count, group) => (
					<div
						// biome-ignore lint/suspicious/noArrayIndexKey: friend order is the identity.
						key={group}
						className="sticker-friend"
						data-wobble={(shared && !equal) || undefined}
					>
						<Art
							art={FRIENDS[group] ?? "friend1"}
							className="sticker-friend-art"
						/>
						<button
							type="button"
							className="sticker-envelope"
							data-envelope={group}
							disabled={demo}
							aria-label={`${group + 1} වන ලියුම් කවරයට ස්ටිකරයක් දාන්න (දැන් ${count})`}
							onClick={() => drop(group)}
						>
							<Art art="envelope" className="sticker-envelope-art" />
							<strong>{count}</strong>
							{hint && !demo && count < share && (
								<small className="sticker-ghost">{share}</small>
							)}
						</button>
						{!demo && count > 0 && (
							<button
								type="button"
								className="sticker-back"
								aria-label={`${group + 1} වන ලියුම් කවරයෙන් එකක් ආපහු ගන්න`}
								onClick={() => takeBack(group)}
							>
								↩
							</button>
						)}
						{equal && (
							<span className="sticker-share">
								<Frac n={1} d={groups} />
							</span>
						)}
					</div>
				))}
			</div>
			{!shared && (
				<div className="sticker-table">
					{Array.from({ length: onTable }, (_, at) => (
						<button
							type="button"
							// biome-ignore lint/suspicious/noArrayIndexKey: stickers are interchangeable.
							key={at}
							className="sticker"
							tabIndex={-1}
							aria-hidden="true"
							disabled={demo}
							onPointerDown={(event) => {
								event.preventDefault();
								setDrag({ x: event.clientX, y: event.clientY });
							}}
						>
							<Art art="star" className="sticker-art" />
						</button>
					))}
				</div>
			)}
			{table && shared && (
				<div className="sticker-rows">
					{[1, 2, 3].map((quarters, row) => (
						<div key={quarters} className="sticker-row">
							<span className="sticker-row-label">
								<Frac n={quarters} d={4} />
							</span>
							{envelopes.map((count, group) => (
								<button
									type="button"
									// biome-ignore lint/suspicious/noArrayIndexKey: envelope order is the identity.
									key={group}
									className="sticker-pick"
									aria-pressed={rows[row]?.includes(group) ?? false}
									data-ghost={
										(hint &&
											!demo &&
											group < quarters &&
											!rows[row]?.includes(group)) ||
										undefined
									}
									disabled={demo}
									aria-label={`${quarters}/4 ට ${group + 1} වන කවරය`}
									onClick={() => pickRow(row, group)}
								>
									{count}
								</button>
							))}
							<strong className="sticker-row-sum">= {rowSums[row]}</strong>
							{hint && !demo && rowSums[row] !== answer[row] && (
								<small className="sticker-ghost">{answer[row]}</small>
							)}
						</div>
					))}
				</div>
			)}
			{drag && (
				<span
					className="sticker-dragged"
					style={{ left: drag.x, top: drag.y }}
					aria-hidden="true"
				>
					<Art art="star" className="sticker-art" />
				</span>
			)}
		</div>
	);
}
