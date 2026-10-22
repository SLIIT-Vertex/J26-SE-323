import { useEffect, useRef } from "react";
import type { NumberWorldChapter } from "./manifest";

export function NumberWorldScene({
	chapter,
	reducedMotion,
}: {
	chapter: NumberWorldChapter;
	reducedMotion: boolean;
}) {
	const host = useRef<HTMLDivElement>(null);
	useEffect(() => {
		let game: import("phaser").Game | undefined;
		let disposed = false;
		void import("phaser").then(({ default: Phaser }) => {
			if (disposed || !host.current || !Phaser.WEBGL) return;
			class Scene extends Phaser.Scene {
				create() {
					this.cameras.main.setBackgroundColor("#fff7e8");
					const labels =
						chapter === "firefly_abacus"
							? ["ල", "දද", "ද", "සි", "දහ", "එ"]
							: ["100000", "10000", "1000", "100", "10", "1"];
					labels.forEach((label, index) => {
						const x = 35 + index * 48;
						this.add
							.rectangle(x, 88, 40, 112, 0xf0e6ff)
							.setStrokeStyle(2, 0x7651c9);
						this.add
							.text(x, 145, label, { color: "#3d2f59", fontSize: "11px" })
							.setOrigin(0.5);
						this.add.circle(x, 70, 14, 0xffb54c);
					});
					if (!reducedMotion)
						this.tweens.add({
							targets: this.children.list,
							alpha: { from: 0.7, to: 1 },
							duration: 350,
						});
				}
			}
			game = new Phaser.Game({
				banner: false,
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
	}, [chapter, reducedMotion]);
	return (
		<div
			ref={host}
			className="number-world-canvas"
			aria-hidden="true"
			data-phaser-chapter={chapter}
		/>
	);
}
