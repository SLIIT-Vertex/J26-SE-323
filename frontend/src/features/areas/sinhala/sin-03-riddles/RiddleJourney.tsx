// biome-ignore-all lint/a11y/useButtonType: mobile application controls, no forms.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { PhaserSurface } from "../gamification/GameHost";
import { SceneBridge } from "../gamification/phaser/bridge/GameEventBridge";
import type { ExperimentCondition } from "../mobile-learning-flow/api/generated";
import type { GameApi } from "../mobile-learning-flow/GameApi";
import {
	type BoardProps,
	freshInteraction,
	type Interaction,
	SinhalaJourney,
} from "../sinhala-shared/SinhalaJourney";
import "./riddle-journey.css";
import { RiddleReveal } from "./RiddleReveal";
import type { RiddleSceneCommand, RiddleSceneEvent } from "./RiddleScene";
import {
	isRiddleGame,
	type RiddleAction,
	type RiddleGame,
	recordAction,
	riddleResponse,
	toggleSpan,
} from "./riddleLogic";

export const RIDDLE_AREA_ID = "G5-AREA-SIN-03";
export const RIDDLE_ACTIVITIES = [
	{
		id: "G5-SIN-RID-DIRECT-01",
		name: "ඉඟි මාවත සහ ඉඟි පාලම",
		chapter: "ඉඟි එකතු කර පිළිතුර සොයමු",
	},
	{
		id: "G5-SIN-RID-FIGURATIVE-01",
		name: "වචන රහස් පෙට්ටිය",
		chapter: "සැඟවුණු අදහස තේරුම් ගනිමු",
	},
] as const;

export function RiddleJourney(props: {
	api: GameApi;
	learnerId: string;
	condition: ExperimentCondition;
	reducedMotion: boolean;
	onBack(): void;
	onFailure(error: unknown): void;
}) {
	return (
		<SinhalaJourney<RiddleGame>
			{...props}
			areaId={RIDDLE_AREA_ID}
			title="තේරවිලි"
			activities={RIDDLE_ACTIVITIES}
			isGame={isRiddleGame}
			Board={RiddleBoard}
			rootClassName="riddle-journey"
			renderReveal={(key) => <RiddleReveal revealKey={key} />}
		/>
	);
}

/**
 * The whole riddle stays visible. The child gathers clue lines as their own evidence and puts
 * one plain answer card in the chest. Nothing on the board marks which card or line matters.
 */
export function RiddleBoard({
	revision,
	game,
	reducedMotion,
	busy,
	checkLabel,
	registry,
	onSubmit,
}: BoardProps<RiddleGame>) {
	const started = useRef(Date.now());
	const submitted = useRef(false);
	const [spans, setSpans] = useState<string[]>([]);
	const [chest, setChest] = useState<string | null>(null);
	const [selected, setSelected] = useState<string | null>(null);
	const [history, setHistory] = useState<RiddleAction[]>([]);
	const [interaction, setInteraction] = useState<Interaction>(freshInteraction);
	const bridge = useMemo(
		() => new SceneBridge<RiddleSceneCommand, RiddleSceneEvent>(),
		[],
	);

	const note = useCallback(
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
	const placeCard = useCallback(
		(id: string, via: "drag" | "tap" | "keyboard") => {
			setChest((current) => {
				const swap = current !== null && current !== id;
				note(via, swap);
				setHistory((h) =>
					recordAction(h, { type: swap ? "swap_card" : "place_card", id }),
				);
				return id;
			});
			setSelected(null);
		},
		[note],
	);
	const toggle = (id: string) => {
		const removing = spans.includes(id);
		note("keyboard", removing);
		setHistory((h) =>
			recordAction(h, { type: removing ? "remove_span" : "select_span", id }),
		);
		setSpans((current) => toggleSpan(current, id, game.evidence_limit));
	};

	useEffect(() => {
		const off = bridge.onEvent((event) => {
			if (event.type === "select")
				setSelected((current) => (current === event.id ? null : event.id));
			else if (event.type === "place") placeCard(event.id, event.via);
			else
				setInteraction((current) => ({
					...current,
					cancels: current.cancels + 1,
				}));
		});
		registry?.listen(off);
		return off;
	}, [bridge, placeCard, registry]);
	useEffect(() => {
		bridge.send({
			type: "model",
			model: {
				revision,
				chapter: game.chapter,
				cards: game.answer_cards.map((card) => ({
					id: card.card_id,
					text: card.text_si,
				})),
				trail: spans,
				chest,
				selected,
				reducedMotion,
			},
		});
	});
	useEffect(() => () => bridge.clear(), [bridge]);
	useEffect(() => {
		if (!busy) submitted.current = false;
	}, [busy]);

	const scene = useCallback(async () => {
		const [{ default: Phaser }, { createRiddleScene }] = await Promise.all([
			import("phaser"),
			import("./RiddleScene"),
		]);
		return createRiddleScene(Phaser, bridge);
	}, [bridge]);

	const ready = chest !== null && !busy;
	const check = () => {
		if (!ready || submitted.current || !chest) return;
		submitted.current = true;
		onSubmit(
			riddleResponse(chest, spans),
			interaction,
			Date.now() - started.current,
		);
	};
	const cardText = new Map(
		game.answer_cards.map((card) => [card.card_id, card.text_si]),
	);

	return (
		<div
			className="pj-board rd-board"
			data-support-emphasis={game.support_emphasis}
			data-history-length={history.length}
		>
			<fieldset className="rd-riddle">
				<legend>තේරවිල්ල · ඉඟියක් තෝරන්න</legend>
				{game.clue_spans.map((span) => (
					<button
						key={span.span_id}
						className="rd-line"
						data-token={span.span_id}
						aria-pressed={spans.includes(span.span_id)}
						data-outlined={
							game.support_emphasis === "outline_selected_spans" &&
							spans.includes(span.span_id)
								? "true"
								: undefined
						}
						disabled={busy}
						onClick={() => toggle(span.span_id)}
					>
						{span.text_si}
					</button>
				))}
			</fieldset>
			<PhaserSurface
				key={revision}
				className="pj-canvas rd-canvas"
				label="තේරවිලි පෙට්ටිය"
				scene={scene}
				options={{ fonts: ['400 19px "Noto Sans Sinhala"'], reducedMotion }}
				onReady={(phaserGame) => {
					if (phaserGame && registry)
						registry.track({ destroy: () => phaserGame.destroy(true) });
				}}
			/>
			<fieldset className="pj-controls">
				<legend>පිළිතුරු කාඩ්පතක් පෙට්ටියට තබන්න</legend>
				<p className="rd-chest" aria-live="polite">
					<span aria-hidden="true">🧰 </span>පෙට්ටිය:{" "}
					<strong>{chest ? cardText.get(chest) : "හිස්"}</strong>
					{spans.length > 0 && <small> · ඔයා තෝරූ ඉඟි {spans.length}</small>}
				</p>
				<fieldset className="pj-cards rd-cards">
					<legend className="sr-only">පිළිතුරු කාඩ්පත්</legend>
					{game.answer_cards.map((card) => (
						<button
							key={card.card_id}
							className="pj-card rd-card"
							data-token={card.card_id}
							aria-pressed={chest === card.card_id}
							disabled={busy}
							onClick={() => placeCard(card.card_id, "keyboard")}
						>
							{card.text_si}
						</button>
					))}
				</fieldset>
			</fieldset>
			<div className="pj-actions">
				<button
					className="text-action"
					disabled={busy}
					onClick={() => {
						setChest(null);
						setSpans([]);
					}}
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
