import { useEffect, useState } from "react";
import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
import type { useMoveEvidence } from "../../../mobile-learning-flow/landscape/useMoveEvidence";
import { COSTUME_ART_KEYS, toyArtReady, toyArtUrl } from "./toyArt";
import {
	type CostumeQuestion,
	costumePlaces,
	costumeResponse,
	costumeValue,
	PLACE_TAGS,
	placeOfDigit,
	spaced,
} from "./toyRules";
import { toySounds } from "./toySounds";

/** Placeholder costume colours, ones first (cap, sun hat, crown, top hat, wizard hat). */
const COSTUME_COLOURS = ["#3b7dd8", "#f5a623", "#ffd23f", "#b44ff0", "#2e9b4f"];

/**
 * The Silly Number Costume Shop: a digit tries on the costume of a place. The rack's tags name
 * the place ("which place is it in?") or the value the digit gets there ("what is it worth?").
 */
export function CostumeShop({
	number,
	digit,
	question,
	demo = false,
	hint = false,
	evidence,
	onResponse,
}: {
	number: number;
	digit: number;
	question: CostumeQuestion;
	demo?: boolean;
	hint?: boolean;
	evidence: ReturnType<typeof useMoveEvidence>;
	onResponse(response: ConstructedResponse | null): void;
}) {
	const answerPlace = placeOfDigit(number, digit);
	const [worn, setWorn] = useState<number | null>(demo ? answerPlace : null);
	const places = costumePlaces(number);
	const text = String(number);

	useEffect(() => {
		onResponse(demo ? null : costumeResponse(question, digit, worn));
	}, [demo, question, digit, worn, onResponse]);

	const wear = (power: number) => {
		if (demo) return;
		evidence.note("move");
		toySounds.play("swish");
		toySounds.play("sparkle", { delay: 0.2, volume: 0.4 });
		setWorn(power);
	};

	return (
		<div className="costume-shop" data-demo={demo || undefined}>
			<p className="costume-number">
				{text.split("").map((character, at) => (
					<span
						// biome-ignore lint/suspicious/noArrayIndexKey: digit positions are fixed.
						key={at}
						data-target={
							(Number(character) === digit &&
								at === text.indexOf(String(digit))) ||
							undefined
						}
					>
						{character}
					</span>
				))}
			</p>
			<fieldset className="costume-rack">
				<legend>ඇඳුම් රාක්කය</legend>
				{places.map((power) => {
					const art = COSTUME_ART_KEYS[power];
					return (
						<button
							type="button"
							key={power}
							className="costume"
							aria-pressed={worn === power}
							data-hint={(hint && answerPlace === power) || undefined}
							disabled={demo}
							onClick={() => wear(power)}
						>
							{art && toyArtReady(art) ? (
								<img src={toyArtUrl(art)} alt="" />
							) : (
								<span
									className="costume-shape"
									data-power={power}
									style={{ background: COSTUME_COLOURS[power] }}
								/>
							)}
							<span className="costume-tag">
								{question === "position"
									? PLACE_TAGS[power]
									: spaced(costumeValue(digit, power))}
							</span>
						</button>
					);
				})}
			</fieldset>
			<div className="digit-buddy" data-power={worn ?? undefined}>
				{worn !== null &&
					(COSTUME_ART_KEYS[worn] && toyArtReady(COSTUME_ART_KEYS[worn]) ? (
						<img
							className="buddy-costume"
							src={toyArtUrl(COSTUME_ART_KEYS[worn])}
							alt=""
						/>
					) : (
						<span
							className="buddy-costume costume-shape"
							data-power={worn}
							style={{ background: COSTUME_COLOURS[worn] }}
						/>
					))}
				<strong className="buddy-digit">{digit}</strong>
				<span className="buddy-face" aria-hidden="true">
					<i />
					<i />
					<b />
				</span>
			</div>
			<p className="costume-card" aria-live="polite">
				{worn === null ? (
					"ඇඳුමක් තෝරන්න!"
				) : (
					<>
						<span>{PLACE_TAGS[worn]}</span>
						<strong>
							{digit} → {spaced(costumeValue(digit, worn))}
						</strong>
					</>
				)}
			</p>
		</div>
	);
}
