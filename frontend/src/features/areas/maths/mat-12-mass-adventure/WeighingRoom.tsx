import { type CSSProperties, useEffect, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import type { WeighArtKey } from "./weighArt";
import { Art, NimoSays } from "./weighParts";
import {
	type Instrument,
	instrumentResponse,
	massText,
	type Placement,
	type WeighTask,
} from "./weighRules";
import { weighSounds } from "./weighSounds";

type Evidence = ReturnType<typeof useMoveEvidence>;

/** The things to weigh: how each looks, what it weighs, and its right scale and spot. */
const THINGS: Record<
	string,
	{
		emoji: string;
		name: string;
		grams: number;
		instrument: Instrument;
		placement: Placement;
	}
> = {
	"hanging-bag": {
		emoji: "👜",
		name: "බෑග් එක",
		grams: 500,
		instrument: "spring_balance",
		placement: "hook",
	},
	"market-crate": {
		emoji: "🧺",
		name: "එළවළු කූඩය",
		grams: 12000,
		instrument: "platform_scale",
		placement: "platform",
	},
	"flour-bowl": {
		emoji: "🥣",
		name: "පිටි බඳුන",
		grams: 1500,
		instrument: "dial_scale",
		placement: "tray",
	},
	"small-parcel": {
		emoji: "📦",
		name: "පුංචි පාර්සලය",
		grams: 250,
		instrument: "two_pan_balance",
		placement: "pan",
	},
	"sealed-package": {
		emoji: "🎁",
		name: "තෑගි පෙට්ටිය",
		grams: 1000,
		instrument: "digital_scale",
		placement: "platform",
	},
};

const SCALES: Record<Instrument, { art: WeighArtKey; name: string }> = {
	two_pan_balance: { art: "balancePhoto", name: "තැටි දෙකේ තරාදිය" },
	spring_balance: { art: "springScale", name: "දුනු තරාදිය" },
	dial_scale: { art: "dialScale", name: "කටු තරාදිය" },
	digital_scale: { art: "digitalScale", name: "ඩිජිටල් තරාදිය" },
	platform_scale: { art: "platformScale", name: "වේදිකා තරාදිය" },
};

const SPOTS: { placement: Placement; label: string }[] = [
	{ placement: "hook", label: "🪝 කොක්කේ එල්ලමු" },
	{ placement: "pan", label: "⚖️ තැටියට දාමු" },
	{ placement: "tray", label: "🥣 බඳුනට දාමු" },
	{ placement: "platform", label: "⬜ උඩින් තියමු" },
];

type Try = { instrument: Instrument; placement: Placement };

/**
 * බර බලලා හොයමු! A room with the five weighing scales. Tap the scale the thing should go on, then
 * choose where it goes (hang it on the hook, put it in the pan or the bowl, or stand it on top). On
 * the right scale and spot the scale shows the weight: the spring stretches, the needle turns, the
 * screen lights up. Anywhere else it wobbles and the thing can be moved again.
 */
export function WeighingRoom({
	task,
	demo = false,
	hint = false,
	evidence,
	onResponse,
}: {
	task: WeighTask;
	demo?: boolean;
	hint?: boolean;
	evidence: Evidence;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const thing = THINGS[task.objectId] ?? THINGS["small-parcel"];
	const right = {
		instrument: thing?.instrument ?? "digital_scale",
		placement: thing?.placement ?? "platform",
	} as Try;
	const [chosen, setChosen] = useState<Instrument | null>(
		demo ? right.instrument : null,
	);
	const [tries, setTries] = useState<Try[]>(demo ? [right] : []);
	const last = tries.at(-1);
	const weighed =
		last?.instrument === right.instrument && last.placement === right.placement;
	const scales =
		task.instruments.length > 0
			? task.instruments
			: (Object.keys(SCALES) as Instrument[]);

	useEffect(() => {
		onResponse(
			demo || tries.length === 0 ? null : instrumentResponse(task, tries),
		);
	}, [demo, tries, task, onResponse]);

	const choose = (instrument: Instrument) => {
		if (demo) return;
		weighSounds.play("pick");
		setChosen(instrument);
	};
	const place = (placement: Placement) => {
		if (demo || !chosen) return;
		evidence.note("move");
		const ok = chosen === right.instrument && placement === right.placement;
		weighSounds.play(
			ok
				? chosen === "spring_balance"
					? "spring"
					: chosen === "digital_scale"
						? "beep"
						: "ding"
				: "wobble",
		);
		setTries([...tries, { instrument: chosen, placement }]);
	};

	const said = demo
		? `${thing?.name} ${SCALES[right.instrument].name}ට!`
		: weighed
			? `නියමයි! බර ${massText(thing?.grams ?? 0)}!`
			: last
				? "අපොයි! මේකට ඒ තැන හරි නෑ. ආයෙත් බලමු."
				: chosen
					? "කොහෙද තියන්නේ? හරි තැන තෝරමු!"
					: `බර බලන්න ${thing?.name} හරි තරාදියට දාමු!`;

	return (
		<div
			className="weigh-room"
			data-demo={demo || undefined}
			data-done={weighed || undefined}
		>
			<NimoSays
				mood={weighed ? "cheer" : last ? "think" : "idle"}
				className="help-nimo"
			>
				{said}
			</NimoSays>
			<span className="weigh-thing" aria-hidden="true">
				{thing?.emoji}
			</span>
			<div
				className="weigh-scales"
				style={{ "--scales": scales.length } as CSSProperties}
			>
				{scales.map((instrument) => {
					const here = chosen === instrument;
					const reading = weighed && here;
					return (
						<button
							key={instrument}
							type="button"
							className="weigh-scale"
							data-chosen={here || undefined}
							data-reading={reading || undefined}
							data-wobble={
								(here && last && !weighed && last.instrument === instrument) ||
								undefined
							}
							data-kind={instrument}
							disabled={demo}
							data-ghost={
								(hint && !chosen && instrument === right.instrument) ||
								undefined
							}
							aria-label={SCALES[instrument].name}
							onClick={() => choose(instrument)}
						>
							<span className="weigh-scale-body">
								<Art art={SCALES[instrument].art} className="weigh-scale-art" />
								{here && last?.instrument === instrument && (
									<span
										className="weigh-on"
										data-spot={last.placement}
										aria-hidden="true"
									>
										{thing?.emoji}
									</span>
								)}
								{reading && (
									<b className="weigh-reading">{massText(thing?.grams ?? 0)}</b>
								)}
							</span>
							<small>{SCALES[instrument].name}</small>
						</button>
					);
				})}
			</div>
			{!demo && chosen && !weighed && (
				<div className="weigh-spots">
					{SPOTS.map(({ placement, label }) => (
						<button
							key={placement}
							type="button"
							className="weigh-spot"
							data-ghost={
								(hint &&
									chosen === right.instrument &&
									placement === right.placement) ||
								undefined
							}
							onClick={() => place(placement)}
						>
							{label}
						</button>
					))}
				</div>
			)}
		</div>
	);
}
