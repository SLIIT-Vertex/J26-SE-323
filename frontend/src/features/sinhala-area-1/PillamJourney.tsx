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
import "./pillam-journey.css";
import type {
	PillamSceneCommand,
	PillamSceneEvent,
	PillamSceneModel,
} from "./PillamScene";
import {
	buildResponse,
	composePreview,
	exclusiveBuild,
	isComplete,
	isPillamGame,
	type MatchPlacement,
	matchResponse,
	PAPILI_SHAPE_LABEL,
	type PillamGame,
	placeMatch,
	toggleComponent,
} from "./pillamLogic";

export const PILLAM_AREA_ID = "G5-AREA-SIN-01";
export const PILLAM_ACTIVITIES = [
	{ id: "G5-SIN-PIL-NAME-01", name: "පිල්ලම් මිතුරෝ", chapter: "පිල්ලම් මිතුරෝ" },
	{ id: "G5-SIN-PIL-VOWEL-01", name: "ස්වර පාලම", chapter: "පිල්ලම් මිතුරෝ" },
	{ id: "G5-SIN-PIL-BUILD-01", name: "අකුරු වැඩපොළ", chapter: "අකුරු වැඩපොළ" },
	{ id: "G5-SIN-PIL-LENGTH-01", name: "කෙටිද දික්ද?", chapter: "අකුරු වැඩපොළ" },
	{ id: "G5-SIN-PIL-PAPILI-01", name: "පාපිලි මාරුව", chapter: "සංයුක්ත පිල්ලම් උයන" },
	{
		id: "G5-SIN-PIL-COMPOUND-01",
		name: "සංයුක්ත පිල්ලම් උයන",
		chapter: "සංයුක්ත පිල්ලම් උයන",
	},
] as const;

export function PillamJourney(props: {
	api: GameApi;
	learnerId: string;
	condition: ExperimentCondition;
	reducedMotion: boolean;
	onBack(): void;
	onFailure(error: unknown): void;
}) {
	return (
		<SinhalaJourney<PillamGame>
			{...props}
			areaId={PILLAM_AREA_ID}
			title="පිල්ලම් හඳුනාගනිමු"
			activities={PILLAM_ACTIVITIES}
			isGame={isPillamGame}
			Board={PillamBoard}
			rootClassName="pillam-journey"
		/>
	);
}

/**
 * One play surface: the Phaser scene for drag and tap, mirrored by DOM buttons that emit the
 * same semantic actions. Both feed the same state; the server scores whatever was submitted.
 */
export function PillamBoard({
	revision,
	game,
	reducedMotion,
	busy,
	checkLabel,
	registry,
	onSubmit,
}: BoardProps<PillamGame>) {
	const started = useRef(Date.now());
	const submitted = useRef(false);
	const [selected, setSelected] = useState<string | null>(null);
	const [match, setMatch] = useState<MatchPlacement[]>([]);
	const [ordered, setOrdered] = useState<string[]>([]);
	const [interaction, setInteraction] = useState<Interaction>(freshInteraction);
	const bridge = useMemo(
		() => new SceneBridge<PillamSceneCommand, PillamSceneEvent>(),
		[],
	);
	const isMatch = game.response_kind === "sinhala_pillam_match";
	const mode = game.match_mode ?? "name";
	type BoardCard = {
		id: string;
		text: string;
		label: string;
		shape?: "kon" | "vak" | "aeda";
	};
	const cards: BoardCard[] = isMatch
		? (game.sign_cards ?? []).map((card) => ({
				id: card.token_id,
				text: card.display_si,
				label: card.accessible_label_si,
			}))
		: (game.component_cards ?? []).map((card) => ({
				id: card.token_id,
				text: card.display_si,
				shape: card.allograph_shape,
				label: card.label_si ?? card.accessible_label_si,
			}));
	const chosen = (game.component_cards ?? []).filter((card) =>
		ordered.includes(card.token_id),
	);
	const preview = game.base ? composePreview(game.base.text_si, chosen) : null;

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

	const place = useCallback(
		(source: string, destination: string, via: "drag" | "tap" | "keyboard") => {
			setMatch((current) => {
				record(
					via,
					current.some((row) => row.source === source),
				);
				return placeMatch(current, source, destination, mode);
			});
			setSelected(null);
		},
		[mode, record],
	);
	const toggle = useCallback(
		(id: string, via: "drag" | "tap" | "keyboard") => {
			setOrdered((current) => {
				record(via, current.includes(id));
				return toggleComponent(
					current,
					id,
					game.maximum_components ?? 4,
					exclusiveBuild(game),
				);
			});
			setSelected(null);
		},
		[game, record],
	);

	useEffect(() => {
		const off = bridge.onEvent((event) => {
			if (event.type === "select")
				setSelected((current) => (current === event.id ? null : event.id));
			else if (event.type === "place")
				place(event.source, event.destination, event.via);
			else if (event.type === "toggle") toggle(event.id, event.via);
			else
				setInteraction((current) => ({
					...current,
					cancels: current.cancels + 1,
				}));
		});
		registry?.listen(off);
		return off;
	}, [bridge, place, toggle, registry]);

	useEffect(() => {
		const model: PillamSceneModel = {
			revision,
			chapter: game.chapter,
			mode: isMatch ? "match" : "build",
			cards,
			docks: (game.destinations ?? []).map((dock) => ({
				id: dock.destination_id,
				text: dock.text_si,
			})),
			base: game.base
				? { id: game.base.token_id, text: game.base.text_si }
				: undefined,
			placements: Object.fromEntries(
				match.map((row) => [row.source, row.destination]),
			),
			ordered,
			selected,
			preview,
			emphasis: game.support_emphasis ?? null,
			reducedMotion,
		};
		bridge.send({ type: "model", model });
	});

	useEffect(() => () => bridge.clear(), [bridge]);

	const ready = isComplete(game, match, ordered) && !busy;
	const check = () => {
		if (!ready || submitted.current) return;
		submitted.current = true;
		const response = isMatch
			? matchResponse(mode, match)
			: buildResponse(game.base?.token_id ?? "", ordered);
		onSubmit(response, interaction, Date.now() - started.current);
	};
	useEffect(() => {
		if (!busy) submitted.current = false;
	}, [busy]);

	const scene = useCallback(async () => {
		const [{ default: Phaser }, { createPillamScene }] = await Promise.all([
			import("phaser"),
			import("./PillamScene"),
		]);
		return createPillamScene(Phaser, bridge);
	}, [bridge]);

	return (
		<div className="pj-board" data-support-emphasis={game.support_emphasis}>
			{game.base && (
				<p className="pj-target">
					<span>
						මුල් අකුර:{" "}
						<strong className="pj-glyph-inline">{game.base.text_si}</strong>
					</span>
					<span>
						ඉල්ලා ඇති ස්වරය:{" "}
						<strong className="pj-glyph-inline">{game.target_vowel_si}</strong>
					</span>
				</p>
			)}
			<PhaserSurface
				key={revision}
				className="pj-canvas"
				label="පිල්ලම් ක්‍රීඩා පුවරුව"
				scene={scene}
				options={{ fonts: ['700 32px "Noto Sans Sinhala"'], reducedMotion }}
				onReady={(phaserGame) => {
					if (phaserGame && registry)
						registry.track({ destroy: () => phaserGame.destroy(true) });
				}}
			/>
			{/* Accessible controls: the same semantic actions as the scene. */}
			<fieldset className="pj-controls">
				<legend>
					{isMatch ? "කාඩ්පතක් තෝරා ගැළපෙන තැනට තබන්න" : "පිල්ලමක් තෝරා අකුරට යොදන්න"}
				</legend>
				<fieldset className="pj-cards">
					<legend className="sr-only">කාඩ්පත්</legend>
					{cards.map((card, position) => (
						<button
							key={card.id}
							className="pj-card"
							aria-pressed={selected === card.id || ordered.includes(card.id)}
							aria-label={`${card.label} ${position + 1}`}
							data-token={card.id}
							disabled={busy}
							onClick={() => {
								if (isMatch)
									setSelected((current) =>
										current === card.id ? null : card.id,
									);
								else toggle(card.id, "keyboard");
							}}
						>
							{card.shape ? (
								<span>{PAPILI_SHAPE_LABEL[card.shape]}</span>
							) : (
								<span className="pj-glyph-inline" aria-hidden="true">
									{card.text}
								</span>
							)}
						</button>
					))}
				</fieldset>
				{isMatch && (
					<fieldset className="pj-docks">
						<legend className="sr-only">ගැළපෙන තැන්</legend>
						{(game.destinations ?? []).map((dock) => {
							const here = match.filter(
								(row) => row.destination === dock.destination_id,
							).length;
							return (
								<button
									key={dock.destination_id}
									className="pj-dock"
									data-token={dock.destination_id}
									disabled={busy || !selected}
									onClick={() =>
										selected && place(selected, dock.destination_id, "keyboard")
									}
								>
									{dock.text_si}
									{here > 0 && <small> · {here}</small>}
								</button>
							);
						})}
					</fieldset>
				)}
				{!isMatch && (
					<p className="pj-preview" aria-live="polite">
						ඔයා හැදූ අකුර:{" "}
						<strong className="pj-glyph-inline">
							{preview ?? game.base?.text_si}
						</strong>
						{chosen.some((card) => card.allograph_shape) && (
							<small> ({chosen.map((card) => card.label_si).join(", ")})</small>
						)}
					</p>
				)}
			</fieldset>
			<div className="pj-actions">
				<button
					className="text-action"
					disabled={busy}
					onClick={() => {
						setMatch([]);
						setOrdered([]);
						setSelected(null);
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
