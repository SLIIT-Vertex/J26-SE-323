// biome-ignore-all lint/a11y/useButtonType: mobile application controls, no forms.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { PhaserSurface } from "../../../gamification/GameHost";
import { SceneBridge } from "../../../gamification/phaser/bridge/GameEventBridge";
import type { ExperimentCondition } from "../../../mobile-learning-flow/api/generated";
import type { GameApi } from "../../../mobile-learning-flow/GameApi";
import {
	type BoardProps,
	freshInteraction,
	type Interaction,
	SinhalaJourney,
} from "../shared/SinhalaJourney";
import "./punctuation-journey.css";
import type {
	PunctuationSceneCommand,
	PunctuationSceneEvent,
} from "./PunctuationScene";
import {
	isComplete,
	isPunctuationGame,
	type Placements,
	type PunctuationGame,
	place,
	preview,
	punctuationResponse,
	removeAt,
} from "./punctuationLogic";

export const PUNCTUATION_AREA_ID = "G5-AREA-SIN-02";
export const PUNCTUATION_ACTIVITIES = [
	{ id: "G5-SIN-PUNC-END-01", name: "වාක්‍ය අවසානය", chapter: "වාක්‍ය රේල් පාර" },
	{ id: "G5-SIN-PUNC-QUESTION-01", name: "ප්‍රශ්න වාක්‍ය", chapter: "වාක්‍ය රේල් පාර" },
	{ id: "G5-SIN-PUNC-EXCLAIM-01", name: "හැඟීම් වාක්‍ය", chapter: "වාක්‍ය රේල් පාර" },
	{ id: "G5-SIN-PUNC-INITIALS-01", name: "මුලකුරු", chapter: "කුඩා ලකුණු වැඩපොළ" },
	{ id: "G5-SIN-PUNC-ABBREV-01", name: "කෙටි නාම", chapter: "කුඩා ලකුණු වැඩපොළ" },
	{
		id: "G5-SIN-PUNC-COMMA-LIST-01",
		name: "ලැයිස්තු කොමාව",
		chapter: "කුඩා ලකුණු වැඩපොළ",
	},
	{
		id: "G5-SIN-PUNC-COMMA-PAUSE-01",
		name: "විරාම කොමාව",
		chapter: "කුඩා ලකුණු වැඩපොළ",
	},
	{ id: "G5-SIN-PUNC-QUOTE-01", name: "කියූ වචන", chapter: "කියූ දේ සහ අමතර දේ" },
	{
		id: "G5-SIN-PUNC-PAREN-01",
		name: "අමතර තොරතුරු",
		chapter: "කියූ දේ සහ අමතර දේ",
	},
	{ id: "G5-SIN-PUNC-RANGE-01", name: "පිටු පරාසය", chapter: "කෙටි ඉරේ මඟ" },
	{
		id: "G5-SIN-PUNC-LINEBREAK-01",
		name: "පේළි බෙදීම",
		chapter: "කෙටි ඉරේ මඟ",
		// Fail closed: no approved word-division rule or example exists yet.
		blockedReason: "ගුරුවරුන්ගේ සමාලෝචනයෙන් පසු විවෘත වේ",
	},
] as const;

export function PunctuationJourney(props: {
	api: GameApi;
	learnerId: string;
	condition: ExperimentCondition;
	reducedMotion: boolean;
	onBack(): void;
	onFailure(error: unknown): void;
}) {
	return (
		<SinhalaJourney<PunctuationGame>
			{...props}
			areaId={PUNCTUATION_AREA_ID}
			title="විරාම ලක්ෂණ හඳුනාගනිමු"
			activities={PUNCTUATION_ACTIVITIES}
			isGame={isPunctuationGame}
			Board={PunctuationBoard}
			rootClassName="punctuation-journey"
		/>
	);
}

/** The rail: Phaser for drag/tap, DOM buttons for the same semantic actions. */
export function PunctuationBoard({
	revision,
	game,
	reducedMotion,
	busy,
	checkLabel,
	registry,
	onSubmit,
}: BoardProps<PunctuationGame>) {
	const started = useRef(Date.now());
	const submitted = useRef(false);
	const [selected, setSelected] = useState<string | null>(null);
	const [placements, setPlacements] = useState<Placements>({});
	const [interaction, setInteraction] = useState<Interaction>(freshInteraction);
	const bridge = useMemo(
		() => new SceneBridge<PunctuationSceneCommand, PunctuationSceneEvent>(),
		[],
	);

	const record = useCallback(
		(via: "drag" | "tap" | "keyboard", correction: boolean) => {
			setInteraction((current) => ({
				moves: current.moves + 1,
				corrections: current.corrections + (correction ? 1 : 0),
				cancels: current.cancels,
				firstActionMs: current.firstActionMs ?? Date.now() - started.current,
				mode: current.mode && current.mode !== via ? "mixed" : via,
			}));
		},
		[],
	);
	const put = useCallback(
		(card: string, gap: string, via: "drag" | "tap" | "keyboard") => {
			setPlacements((current) => {
				record(via, Object.values(current).includes(card) || gap in current);
				return place(current, gap, card);
			});
			setSelected(null);
		},
		[record],
	);
	const take = useCallback(
		(gap: string) => {
			setPlacements((current) => {
				record("tap", true);
				return removeAt(current, gap);
			});
		},
		[record],
	);

	useEffect(() => {
		const off = bridge.onEvent((event) => {
			if (event.type === "select")
				setSelected((current) => (current === event.id ? null : event.id));
			else if (event.type === "place") put(event.card, event.gap, event.via);
			else if (event.type === "remove") take(event.gap);
			else
				setInteraction((current) => ({
					...current,
					cancels: current.cancels + 1,
				}));
		});
		registry?.listen(off);
		return off;
	}, [bridge, put, take, registry]);

	useEffect(() => {
		bridge.send({
			type: "model",
			model: {
				revision,
				chapter: game.chapter,
				tokens: game.tokens.map((token) => token.text_si),
				gaps: game.boundaries.map((b) => ({
					id: b.boundary_id,
					after: b.after_token_index,
				})),
				cards: game.mark_cards.map((card) => ({
					id: card.token_id,
					text: card.display_si,
				})),
				placements,
				selected,
				emphasis: game.support_emphasis ?? null,
				reducedMotion,
			},
		});
	});
	useEffect(() => () => bridge.clear(), [bridge]);
	useEffect(() => {
		if (!busy) submitted.current = false;
	}, [busy]);

	const scene = useCallback(async () => {
		const [{ default: Phaser }, { createPunctuationScene }] = await Promise.all(
			[import("phaser"), import("./PunctuationScene")],
		);
		return createPunctuationScene(Phaser, bridge);
	}, [bridge]);

	const ready = isComplete(game, placements) && !busy;
	const check = () => {
		if (!ready || submitted.current) return;
		submitted.current = true;
		onSubmit(
			punctuationResponse(game, placements),
			interaction,
			Date.now() - started.current,
		);
	};
	const cardLabel = new Map(
		game.mark_cards.map((card) => [card.token_id, card.accessible_label_si]),
	);
	const gapNumber = new Map(
		game.boundaries.map((b, index) => [b.boundary_id, index + 1]),
	);

	return (
		<div
			className="pj-board pu-board"
			data-support-emphasis={game.support_emphasis}
		>
			{game.context_si && <p className="pu-context">{game.context_si}</p>}
			<PhaserSurface
				key={revision}
				className="pj-canvas pu-canvas"
				label="විරාම ලක්ෂණ පුවරුව"
				scene={scene}
				options={{ fonts: ['400 21px "Noto Sans Sinhala"'], reducedMotion }}
				onReady={(phaserGame) => {
					if (phaserGame && registry)
						registry.track({ destroy: () => phaserGame.destroy(true) });
				}}
			/>
			<fieldset className="pj-controls">
				<legend>ලකුණක් තෝරා වාක්‍යයේ හිඩැසකට තබන්න</legend>
				<p className="pu-rail" aria-hidden="true">
					{preview(game, placements)}
				</p>
				<fieldset className="pj-cards">
					<legend className="sr-only">ලකුණු</legend>
					{game.mark_cards.map((card) => (
						<button
							key={card.token_id}
							className="pj-card pu-mark"
							data-token={card.token_id}
							aria-label={card.accessible_label_si}
							aria-pressed={
								selected === card.token_id ||
								Object.values(placements).includes(card.token_id)
							}
							disabled={busy}
							onClick={() =>
								setSelected((current) =>
									current === card.token_id ? null : card.token_id,
								)
							}
						>
							<span aria-hidden="true">{card.display_si}</span>
						</button>
					))}
				</fieldset>
				<fieldset className="pj-docks pu-gaps">
					<legend className="sr-only">වාක්‍යයේ හිඩැස්</legend>
					{game.boundaries.map((b) => {
						const held = placements[b.boundary_id];
						const before =
							b.after_token_index >= 0
								? game.tokens[b.after_token_index]?.text_si
								: null;
						const label = before
							? `“${before}” ට පසු හිඩැස`
							: "වාක්‍යයේ මුලට පෙර හිඩැස";
						return (
							<button
								key={b.boundary_id}
								className="pj-dock pu-gap"
								data-token={b.boundary_id}
								disabled={busy || (!selected && !held)}
								aria-label={`${gapNumber.get(b.boundary_id)}. ${label}${held ? ` · ${cardLabel.get(held)}` : ""}`}
								onClick={() =>
									selected
										? put(selected, b.boundary_id, "keyboard")
										: held && take(b.boundary_id)
								}
							>
								{label}
								{held && <strong> · {cardLabel.get(held)}</strong>}
							</button>
						);
					})}
				</fieldset>
			</fieldset>
			<div className="pj-actions">
				<button
					className="text-action"
					disabled={busy}
					onClick={() => setPlacements({})}
				>
					නැවත පටන් ගන්න
				</button>
				<button className="primary-action" disabled={!ready} onClick={check}>
					{checkLabel}
				</button>
			</div>
		</div>
	);
}
