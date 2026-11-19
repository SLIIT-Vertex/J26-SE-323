import {
	type CarnivalArtKey,
	carnivalArtReady,
	carnivalArtUrl,
} from "./carnivalArt";
import { carnivalSounds } from "./carnivalSounds";

/** A picture from the art manifest, or a placeholder shape until the art is ready. */
export function Art({
	art,
	className,
}: {
	art: CarnivalArtKey;
	className?: string;
}) {
	return carnivalArtReady(art) ? (
		<img className={className} src={carnivalArtUrl(art)} alt="" />
	) : (
		<span className={`${className ?? ""} carnival-shape`} data-art={art} />
	);
}

const PLACE_NAMES = ["එක", "දහය", "සිය", "දහස්", "දස දහස්"];

/**
 * Big score wheels: ▲ turns a wheel up, ▼ turns it down (9 wraps to 0). The wheels show only what
 * the child set; nothing is checked here.
 */
export function ScoreWheels({
	digits,
	ghost,
	disabled = false,
	onChange,
}: {
	digits: readonly number[];
	/** Faint answer digits in a help stage. */
	ghost?: readonly number[];
	disabled?: boolean;
	onChange(digits: number[]): void;
}) {
	const turn = (wheel: number, step: 1 | -1) => {
		carnivalSounds.play("tick");
		onChange(
			digits.map((digit, at) =>
				at === wheel ? (digit + step + 10) % 10 : digit,
			),
		);
	};
	return (
		<div className="score-wheels">
			{digits.map((digit, wheel) => {
				const place = PLACE_NAMES[digits.length - 1 - wheel] ?? "";
				return (
					<div
						// biome-ignore lint/suspicious/noArrayIndexKey: the wheel order is the place.
						key={wheel}
						className="score-wheel"
						data-ghost={(ghost && ghost[wheel] !== digit) || undefined}
					>
						<button
							type="button"
							disabled={disabled}
							aria-label={`${place} තැන වැඩි කරන්න`}
							onClick={() => turn(wheel, 1)}
						>
							▲
						</button>
						<strong>
							<span className="carnival-sr-only">{place} තැන </span>
							{digit}
						</strong>
						{ghost && <small className="score-ghost">{ghost[wheel]}</small>}
						<button
							type="button"
							disabled={disabled}
							aria-label={`${place} තැන අඩු කරන්න`}
							onClick={() => turn(wheel, -1)}
						>
							▼
						</button>
					</div>
				);
			})}
		</div>
	);
}
