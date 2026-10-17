import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { HalfSetManifest, SceneDomainEvent } from "../bridge/contracts";
import { MobileLearningBridge } from "../bridge/MobileLearningBridge";
import { createHalfSetGame, type GameHandle } from "./createHalfSetGame";
import { HalfSetSceneController } from "./HalfSetSceneController";

export function HalfSetGame({
	manifest,
	support,
	withdrawalRequest,
	reducedMotion,
	onEvent,
}: {
	manifest: HalfSetManifest;
	support: { titleSi: string; stepsSi: string[] } | null;
	withdrawalRequest: { requestId: string; supportRevisionId: string } | null;
	reducedMotion: boolean;
	onEvent(event: SceneDomainEvent): void;
}) {
	const host = useRef<HTMLDivElement>(null);
	const handle = useRef<GameHandle | null>(null);
	const bridge = useMemo(() => new MobileLearningBridge(), []);
	const controller = useMemo(
		() => new HalfSetSceneController((event) => bridge.emit(event)),
		[bridge],
	);
	const [fallback, setFallback] = useState(false);
	const [ready, setReady] = useState(false);
	const [gameSettled, setGameSettled] = useState(false);
	const [withdrawnRequest, setWithdrawnRequest] = useState<{
		requestId: string;
		supportRevisionId: string;
		manifestRevisionId: string;
	} | null>(null);
	const acknowledgedRequest = useRef<string | null>(null);
	const pendingWithdrawal = useRef<string | null>(null);

	useEffect(() => bridge.onEvent(onEvent), [bridge, onEvent]);
	useEffect(
		() => bridge.onCommand((command) => controller.apply(command)),
		[bridge, controller],
	);

	useEffect(() => {
		const element = host.current;
		if (!element) return;
		let active = true;
		setGameSettled(false);
		bridge.command({ type: "load_manifest", manifest });
		bridge.command({ type: "start" });
		setReady(true);
		createHalfSetGame(element, controller, manifest, reducedMotion)
			.then((game) => {
				if (!active) game.destroy();
				else {
					handle.current = game;
					if (pendingWithdrawal.current) game.clearForWithdrawal();
					setGameSettled(true);
				}
			})
			.catch(() => {
				if (active) {
					setFallback(true);
					setGameSettled(true);
					bridge.emit({
						type: "scene_error",
						code: "WEBGL_OR_CANVAS_UNAVAILABLE",
					});
				}
			});
		const resize = () => handle.current?.resize();
		const visibility = () => {
			if (document.hidden) bridge.command({ type: "pause" });
			else bridge.command({ type: "resume" });
		};
		window.addEventListener("resize", resize);
		window.addEventListener("orientationchange", resize);
		document.addEventListener("visibilitychange", visibility);
		return () => {
			active = false;
			window.removeEventListener("resize", resize);
			window.removeEventListener("orientationchange", resize);
			document.removeEventListener("visibilitychange", visibility);
			bridge.command({ type: "dispose" });
			handle.current?.destroy();
			handle.current = null;
			bridge.dispose();
		};
	}, [bridge, controller, manifest, reducedMotion]);

	useEffect(() => {
		if (support) {
			bridge.command({
				type: "present_temporary_support",
				titleSi: support.titleSi,
				stepsSi: support.stepsSi,
			});
		}
	}, [bridge, support]);

	useEffect(() => {
		if (!withdrawalRequest || acknowledgedRequest.current === withdrawalRequest.requestId)
			return;
		pendingWithdrawal.current = withdrawalRequest.requestId;
		bridge.command({ type: "withdraw_support", ...withdrawalRequest });
		handle.current?.clearForWithdrawal();
		setWithdrawnRequest({
			...withdrawalRequest,
			manifestRevisionId: manifest.revisionId,
		});
	}, [bridge, manifest.revisionId, withdrawalRequest]);

	useLayoutEffect(() => {
		if (
			!gameSettled ||
			!withdrawnRequest ||
			acknowledgedRequest.current === withdrawnRequest.requestId
		)
			return;
		acknowledgedRequest.current = withdrawnRequest.requestId;
		bridge.emit({
			type: "withdrawal_acknowledged",
			...withdrawnRequest,
			allSupportRemoved: true,
			answerRevealingStateCleared: true,
			inputHandlersCleared: true,
		});
	}, [bridge, gameSettled, withdrawnRequest]);

	return (
		<section className="game-card" aria-labelledby="game-instruction">
			<p id="game-instruction" className="game-instruction" lang="si">
				{manifest.instructionSi}
			</p>
			{!fallback && (
				<div
					ref={host}
					className="phaser-host"
					aria-hidden="true"
					data-testid="phaser-host"
				/>
			)}
			{ready && !withdrawnRequest && (
				<SemanticHalfSet
					controller={controller}
					manifest={manifest}
					fallback={fallback}
				/>
			)}
		</section>
	);
}

function SemanticHalfSet({
	controller,
	manifest,
	fallback,
}: {
	controller: HalfSetSceneController;
	manifest: HalfSetManifest;
	fallback: boolean;
}) {
	const [, redraw] = useState(0);
	const ids = Object.keys(controller.placements);
	return (
		<div
			className={
				fallback ? "semantic-game semantic-game--primary" : "semantic-game"
			}
		>
			<p className="sr-context" lang="si">
				{fallback
					? "දෘශ්‍ය ක්‍රීඩාව නොමැත. ප්‍රවේශ විය හැකි ක්‍රමය භාවිතා කරන්න."
					: "යතුරු පුවරුව හෝ ස්විචය සඳහා විකල්ප ක්‍රමය."}
			</p>
			<div className="semantic-object-grid">
				{ids.map((id, index) => (
					<fieldset key={id} className="semantic-object">
						<legend lang="si">
							{manifest.objectLabelSi} {index + 1}
						</legend>
						<button
							type="button"
							onClick={() => {
								controller.place(id, 0);
								redraw((n) => n + 1);
							}}
							aria-pressed={controller.placements[id] === 0}
						>
							කාණ්ඩය 1
						</button>
						<button
							type="button"
							onClick={() => {
								controller.place(id, 1);
								redraw((n) => n + 1);
							}}
							aria-pressed={controller.placements[id] === 1}
						>
							කාණ්ඩය 2
						</button>
					</fieldset>
				))}
			</div>
			<button
				className="secondary-action"
				type="button"
				onClick={() => {
					controller.submit();
				}}
				lang="si"
			>
				සමූහ කිරීම අවසන්
			</button>
		</div>
	);
}
