import { useEffect, useRef, useState } from "react";
import { CLASSROOM_ASSET_ROOT } from "../eng-01-classroom-action-quest/manifest";

/** Phaser presents the characters and mirrors choices; accessible HTML owns input. */
export function ConversationScene({
	progress,
	cue,
	message,
	reducedMotion,
}: {
	progress: number;
	message?: string;
	cue?: string;
	reducedMotion: boolean;
}) {
	const host = useRef<HTMLDivElement>(null);
	const engine = useRef<import("phaser").Game | null>(null);
	const latest = useRef({ progress, message });
	latest.current = { progress, message };
	const [ready, setReady] = useState(false);
	useEffect(() => {
		const parent = host.current;
		if (!parent) return;
		let disposed = false;
		let instance: import("phaser").Game | undefined;
		setReady(false);
		void import("phaser")
			.then(({ default: Phaser }) => {
				if (disposed) return;
				class Street extends Phaser.Scene {
					preload() {
						this.load.image(
							"speaker-a",
							`${CLASSROOM_ASSET_ROOT}/student-standing-neutral.png`,
						);
						this.load.image(
							"speaker-b",
							`${CLASSROOM_ASSET_ROOT}/student-arms-stretched.png`,
						);
						this.load.image("bag", `${CLASSROOM_ASSET_ROOT}/school-bag.png`);
					}
					create() {
						const g = this.add.graphics();
						g.fillStyle(0xdff4f5).fillRoundedRect(0, 0, 640, 230, 20);
						g.fillStyle(0xb8d9b0).fillRect(0, 158, 640, 72);
						g.fillStyle(0xffefd0).fillRect(0, 188, 640, 42);
						// A street backdrop, kept quiet so the conversation remains the focus.
						for (const x of [24, 462]) {
							g.fillStyle(0xf7e3c1).fillRoundedRect(x, 68, 140, 90, 8);
							g.fillStyle(0xc394ac).fillTriangle(
								x - 8,
								69,
								x + 70,
								20,
								x + 148,
								69,
							);
							g.fillStyle(0x7aa6a5).fillRoundedRect(x + 50, 110, 32, 48, 5);
							g.fillStyle(0xfffdf7).fillRoundedRect(x + 14, 87, 24, 24, 3);
						}
						const a = this.add
							.image(206, 143, "speaker-a")
							.setDisplaySize(104, 146);
						const b = this.add
							.image(434, 143, "speaker-b")
							.setDisplaySize(128, 146)
							.setFlipX(true);
						const bubble = this.add
							.text(320, 47, latest.current.message || "Let's talk!", {
								fontFamily: "Nunito, sans-serif",
								fontSize: "17px",
								fontStyle: "bold",
								color: "#563a88",
								align: "center",
								wordWrap: { width: 280 },
								backgroundColor: "#fffdf7",
								padding: { x: 18, y: 10 },
							})
							.setOrigin(0.5);
						this.add
							.text(206, 216, "Speaker A", {
								fontFamily: "Nunito, sans-serif",
								fontSize: "15px",
								color: "#214b4b",
							})
							.setOrigin(0.5);
						this.add
							.text(434, 216, "Speaker B", {
								fontFamily: "Nunito, sans-serif",
								fontSize: "15px",
								color: "#214b4b",
							})
							.setOrigin(0.5);
						if (cue) {
							g.fillStyle(0xfffdf7).fillRoundedRect(268, 86, 104, 112, 14);
							if (cue === "bag")
								this.add.image(320, 137, "bag").setDisplaySize(72, 76);
							else if (cue === "bush") {
								g.fillStyle(0x558755)
									.fillCircle(298, 148, 19)
									.fillCircle(320, 130, 25)
									.fillCircle(341, 150, 19);
							} else if (cue === "house") {
								g.fillStyle(0xf3ce8b).fillRect(291, 128, 58, 45);
								g.fillStyle(0xb16b7e).fillTriangle(281, 129, 320, 96, 359, 129);
								g.fillStyle(0x658790).fillRect(315, 149, 13, 24);
							} else if (cue === "umbrella") {
								g.fillStyle(0x8b65b5)
									.slice(320, 135, 36, Math.PI, Math.PI * 2, false)
									.fillPath();
								g.lineStyle(5, 0x63516d).lineBetween(320, 135, 320, 170);
								g.strokeCircle(314, 170, 6);
							}
						}
						const respond = ({
							progress: count,
							message: text,
						}: {
							progress: number;
							message?: string;
						}) => {
							bubble.setText(text || "Let's talk!");
							if (
								!reducedMotion &&
								!window.matchMedia("(prefers-reduced-motion: reduce)").matches
							) {
								const actor = count % 2 ? b : a;
								this.tweens.killTweensOf(actor);
								actor.y = 143;
								this.tweens.add({
									targets: actor,
									y: 135,
									duration: 140,
									yoyo: true,
								});
							}
						};
						this.game.events.on("conversation-choice", respond);
						this.events.once("shutdown", () =>
							this.game.events.off("conversation-choice", respond),
						);
						setReady(true);
					}
				}
				instance = new Phaser.Game({
					type: Phaser.AUTO,
					parent,
					width: 640,
					height: 230,
					backgroundColor: "#dff4f5",
					scene: Street,
					scale: {
						mode: Phaser.Scale.FIT,
						autoCenter: Phaser.Scale.CENTER_BOTH,
					},
					render: { antialias: true },
					audio: { noAudio: true },
					fps: { target: 30 },
				});
				engine.current = instance;
			})
			.catch(() => {
				/* The illustrated HTML fallback remains usable. */
			});
		return () => {
			disposed = true;
			engine.current = null;
			instance?.destroy(true);
		};
	}, [cue, reducedMotion]);
	useEffect(() => {
		engine.current?.events.emit("conversation-choice", { progress, message });
	}, [progress, message]);
	return (
		<div
			className="cs-scene"
			role="img"
			aria-label={
				cue
					? `Show-and-tell picture: ${cue}. Two story characters are talking.`
					: "Two story characters, Speaker A and Speaker B, are talking on Conversation Street."
			}
		>
			{!ready && (
				<div className="cs-scene-fallback">
					<img
						src={`${CLASSROOM_ASSET_ROOT}/student-standing-neutral.png`}
						alt=""
					/>
					<span>{cue ?? "Let’s talk!"}</span>
					<img
						src={`${CLASSROOM_ASSET_ROOT}/student-arms-stretched.png`}
						alt=""
					/>
				</div>
			)}
			<div className="cs-phaser" ref={host} aria-hidden="true" />
		</div>
	);
}
