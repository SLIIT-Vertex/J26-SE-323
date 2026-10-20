import { useEffect, useRef } from "react";
import type { AdditionChapter } from "./manifest";

export function AdditionAdventureScene({
	chapter,
	reducedMotion,
	onMove,
}: {
	chapter: AdditionChapter;
	reducedMotion: boolean;
	onMove(kind: string): void;
}) {
	const host = useRef<HTMLDivElement>(null);
	useEffect(() => {
		let game: import("phaser").Game | undefined;
		let disposed = false;
		void import("phaser").then(({ default: Phaser }) => {
			if (disposed || !host.current) return;
			class Scene extends Phaser.Scene {
				create() {
					this.cameras.main.setBackgroundColor("#fff8df");
					const accent = chapter === "festival_data_detective" ? 0x466bb0 : 0xe08c3a;
					const labels =
						chapter === "carrying_crane"
							? ["දහස්", "සිය", "දහය", "එක"]
							: chapter === "tuk_tuk_journey"
								? ["1", "2", "3", "4"]
								: chapter === "festival_data_detective"
									? ["අ", "ආ", "ඇ"]
									: ["5", "10", "+"];
					labels.forEach((label, index) => {
						const x = 48 + index * (220 / Math.max(1, labels.length - 1));
						this.add
							.rectangle(x, 92, 56, 96, 0xfffdf4)
							.setStrokeStyle(2, accent);
						this.add
							.text(x, 135, label, { color: "#47351f", fontSize: "13px" })
							.setOrigin(0.5);
						const token = this.add
							.circle(x, 73, 16, 0xffbd45)
							.setInteractive({ draggable: true });
						this.input.setDraggable(token);
						token.on("dragend", () =>
							onMove(chapter === "festival_data_detective" ? "table_cell" : "column"),
						);
					});
					if (!reducedMotion) {
						this.tweens.add({
							targets: this.children.list,
							alpha: { from: 0.65, to: 1 },
							duration: 300,
						});
					}
				}
			}
			game = new Phaser.Game({
				type: Phaser.AUTO,
				width: 320,
				height: 180,
				parent: host.current,
				transparent: true,
				scene: Scene,
				render: { antialias: true },
			});
		});
		return () => {
			disposed = true;
			game?.destroy(true);
			if (host.current) host.current.replaceChildren();
		};
	}, [chapter, onMove, reducedMotion]);
	return (
		<div
			ref={host}
			className="addition-adventure-canvas"
			aria-hidden="true"
			data-phaser-chapter={chapter}
		/>
	);
}
