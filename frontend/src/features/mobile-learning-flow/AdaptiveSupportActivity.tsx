import { useEffect, useRef, useState } from "react";
import type {
	AdditionAdventureSupportManifest,
	AdditionAdventureWorkedExample,
	FractionAdventureSupportManifest,
	MultiplicationAdventureSupportManifest,
	NumberPatternSupportManifest,
	NumberPatternWorkedExample,
	NumberWorldSupportManifest,
	NumberWorldWorkedExample,
	SubtractionAdventureSupportManifest,
	SubtractionAdventureWorkedExample,
	SupportView,
} from "./api/generated";

type AdaptiveManifest = Extract<
	SupportView["game_manifest"],
	{
		schema_version:
			| "number-world-support-v1"
			| "addition-adventure-support-v1"
			| "number-pattern-support-v1"
			| "subtraction-adventure-support-v1"
			| "fraction-adventure-support-v1"
			| "multiplication-adventure-support-v1"
			| "time-adventure-support-v1"
			| "division-adventure-support-v1"
			| "distance-adventure-support-v1"
			| "money-adventure-support-v1"
			| "capacity-adventure-support-v1"
			| "mass-adventure-support-v1"
			| "shape-adventure-support-v1"
			| "direction-adventure-support-v1"
			| "decimal-adventure-support-v1"
			| "roman-adventure-support-v1"
			| "classroom-action-support-v1"
			| "sri-lanka-discovery-support-v1"
			| "plant-explorer-support-v1"
			| "wildlife-ranger-support-v1"
			| "everyday-object-quest-support-v1"
			| "island-food-festival-support-v1"
			| "water-works-adventure-support-v1"
			| "transit-terminal-quest-support-v1"
			| "rainbow-wardrobe-support-v1"
			| "bloom-builder-garden-support-v1"
			| "workplace-link-city-support-v1"
			| "family-word-constellation-support-v1"
			| "earth-sky-explorer-support-v1"
			| "blueprint-quest-support-v1"
			| "information-station-support-v1"
			| "heritage-museum-support-v1"
			| "classroom-language-live-support-v1"
			| "conversation-street-support-v1";
	}
>;

export const SUPPORT_TYPE_LABELS: Record<SupportView["scaffold_type"], string> =
	{
		visual_guidance: "දෘශ්‍ය මඟ පෙන්වීම",
		worked_parallel_example: "පියවරෙන් පියවර දෘශ්‍ය උදාහරණය",
		step_by_step_guidance: "පියවරෙන් පියවර මඟ පෙන්වීම",
	};

const PLACE_LABELS = ["ලක්ෂ", "දස දහස්", "දහස්", "සිය", "දහය", "එක"];
const PATTERN_ROUTE_KEYS = [
	"first",
	"second",
	"third",
	"fourth",
	"fifth",
	"sixth",
] as const;

function numberValue(value: unknown): number {
	return typeof value === "number" ? value : 0;
}

function numberList(value: unknown): number[] {
	return Array.isArray(value)
		? value.filter((item): item is number => typeof item === "number")
		: [];
}

function formatNumber(value: number): string {
	return new Intl.NumberFormat("en-US").format(value);
}

function taggedNumbers(values: number[]) {
	const seen = new Map<number, number>();
	return values.map((value, index) => {
		const occurrence = (seen.get(value) ?? 0) + 1;
		seen.set(value, occurrence);
		return { id: `${value}-${occurrence}`, index, value };
	});
}

const ADDITION_PLACE_LABELS = ["දස දහස්", "දහස්", "සිය", "දහය", "එක"];

function columnAddition(addends: number[]) {
	const width = ADDITION_PLACE_LABELS.length;
	const rows = addends.map((value) =>
		String(value).padStart(width, "0").split("").map(Number),
	);
	const carries = Array<number>(width).fill(0);
	const digits = Array<number>(width).fill(0);
	let carry = 0;
	for (let column = width - 1; column >= 0; column -= 1) {
		const total = rows.reduce((sum, row) => sum + row[column], carry);
		digits[column] = total % 10;
		carry = Math.floor(total / 10);
		if (column > 0) carries[column - 1] = carry;
	}
	return { carries, digits, rows };
}

function ExactNumberWorldExample({
	example,
	actions,
	scaffoldType,
}: {
	example: NumberWorldWorkedExample;
	actions: number;
	scaffoldType: SupportView["scaffold_type"];
}) {
	const game = example.game;
	const response = example.correct_response;
	const skillId = typeof game.skill_id === "string" ? game.skill_id : "";
	const demonstrate = scaffoldType !== "visual_guidance";
	const showMove = demonstrate && actions >= 2;
	const showAnswer = demonstrate && actions >= 3;
	const number = numberValue(game.number);
	const place = numberValue(game.place);
	const digit = numberValue(game.digit);
	const numberDigits = String(number).padStart(6, "0").split("");
	const activeIndex = 5 - place;
	let visual: React.ReactNode;

	if (skillId === "G5-MAT-NUM-100000-01") {
		visual = (
			<fieldset className="worked-milestone">
				<legend className="sr-only">99 999 ට එකක් එකතු කරන පියවර</legend>
				<strong className={actions >= 1 ? "is-active" : ""}>99,999</strong>
				<span className={actions >= 1 ? "is-visible" : ""}>+ 1</span>
				<span className={actions >= 2 ? "is-visible worked-carry" : ""}>
					9 → 0 · ඉදිරියට 1
				</span>
				{showAnswer && (
					<strong className="is-visible worked-answer">100,000</strong>
				)}
			</fieldset>
		);
	} else if (
		skillId === "G5-MAT-NUM-POSITION-01" ||
		skillId === "G5-MAT-NUM-REPRESENTED-01"
	) {
		const represented =
			response.kind === "drag_to_slot" && "represented_value" in response
				? response.represented_value
				: digit * 10 ** place;
		visual = (
			<div className="worked-place-value">
				<div
					className="worked-number"
					role="img"
					aria-label={`සංඛ්‍යාව ${formatNumber(number)}`}
				>
					{numberDigits.map((character, index) => (
						<span
							className={
								actions >= 1 && index === activeIndex ? "is-target" : ""
							}
							key={PLACE_LABELS[index]}
						>
							{character}
						</span>
					))}
				</div>
				<div className="worked-place-grid" role="img" aria-label="ස්ථානීය අගය වගුව">
					{PLACE_LABELS.map((label, index) => (
						<div
							className={
								actions >= 2 && index === activeIndex ? "is-target" : ""
							}
							key={label}
						>
							<small>{label}</small>
							<strong>{showMove ? numberDigits[index] : "?"}</strong>
						</div>
					))}
				</div>
				{showAnswer && (
					<p className="worked-answer" role="status">
						{skillId.endsWith("POSITION-01")
							? `නිවැරදි ස්ථානය: ${PLACE_LABELS[activeIndex]}`
							: `${digit} × ${formatNumber(10 ** place)} = ${formatNumber(numberValue(represented))}`}
					</p>
				)}
			</div>
		);
	} else if (response.kind === "expanded_form") {
		const terms = response.terms;
		visual = (
			<div className="worked-expanded" role="img" aria-label="විහිදුණු ආකාරය">
				{PLACE_LABELS.map((label) => (
					<span className={actions >= 1 ? "is-highlight" : ""} key={label}>
						{label}
					</span>
				))}
				{showMove &&
					terms.map((term) => <strong key={term}>{formatNumber(term)}</strong>)}
				{showAnswer && (
					<p className="worked-answer" role="status">
						{terms.map(formatNumber).join(" + ")}
					</p>
				)}
			</div>
		);
	} else if (response.kind === "bead_placement") {
		const rods = response.rods;
		visual = (
			<div
				className="worked-abacus"
				role="img"
				aria-label="නිවැරදි පබළු පිහිටීම පියවරෙන් පියවර"
			>
				{PLACE_LABELS.map((label, index) => (
					<div className="worked-rod" key={label}>
						<div className="worked-rod-line">
							{showMove &&
								Array.from(
									{ length: rods[index] ?? 0 },
									(_, bead) => `${label}-bead-${bead + 1}`,
								).map((beadId, beadIndex) => (
									<i
										key={beadId}
										style={{ animationDelay: `${beadIndex * 55}ms` }}
									/>
								))}
						</div>
						<small>{actions >= 1 ? label : "?"}</small>
						<strong>{showMove ? rods[index] : "?"}</strong>
					</div>
				))}
				{showAnswer && (
					<p className="worked-answer" role="status">
						{formatNumber(Number(rods.join("")))}
					</p>
				)}
			</div>
		);
	} else if (response.kind === "digit_order") {
		const sourceDigits = numberList(game.digits);
		const answerDigits = numberList(response.digits);
		visual = (
			<div className="worked-digit-construction">
				<div className="worked-source-cards">
					{sourceDigits.map((value) => (
						<strong key={value}>{value}</strong>
					))}
				</div>
				<span className={actions >= 1 ? "is-visible worked-direction" : ""}>
					{game.greatest ? "විශාල → කුඩා" : "කුඩා → විශාල"}
				</span>
				<fieldset className="worked-answer-slots">
					<legend className="sr-only">නිවැරදි ඉලක්කම් පිළිවෙළ</legend>
					{answerDigits.map((value, index) => (
						<strong
							className={showMove ? "is-visible" : ""}
							key={value}
							style={{ animationDelay: `${index * 90}ms` }}
						>
							{showMove ? value : "?"}
						</strong>
					))}
				</fieldset>
				{showAnswer && (
					<p className="worked-answer" role="status">
						පිළිතුර: {answerDigits.join("")}
					</p>
				)}
			</div>
		);
	} else if (response.kind === "number_order") {
		const sourceValues = numberList(game.values);
		visual = (
			<div className="worked-ordering">
				<div className="worked-source-cards">
					{sourceValues.map((value) => (
						<strong key={value}>{formatNumber(value)}</strong>
					))}
				</div>
				<span className={actions >= 1 ? "is-visible worked-direction" : ""}>
					{game.ascending ? "කුඩා සිට විශාල දක්වා" : "විශාල සිට කුඩා දක්වා"}
				</span>
				<fieldset className="worked-route">
					<legend className="sr-only">නිවැරදි සංඛ්‍යා පිළිවෙළ</legend>
					{response.order.map((value, index) => (
						<strong
							className={showMove ? "is-visible" : ""}
							key={value}
							style={{ animationDelay: `${index * 100}ms` }}
						>
							{index > 0 && <span aria-hidden="true">→</span>}{" "}
							{showMove ? formatNumber(value) : "?"}
						</strong>
					))}
				</fieldset>
				{showAnswer && (
					<p className="worked-answer" role="status">
						නිවැරදි පිළිවෙළ සම්පූර්ණයි.
					</p>
				)}
			</div>
		);
	} else {
		visual = null;
	}

	return (
		<div
			className="exact-worked-example"
			data-worked-example-mode={example.mode}
			data-support-behavior={scaffoldType}
		>
			<p className="worked-same-question">ඔබට ලැබුණු ප්‍රශ්නය</p>
			<h4>{example.prompt_si}</h4>
			{visual}
			<ol className="worked-steps" aria-live="polite">
				{example.steps_si.map((step, index) => (
					<li
						className={
							actions > index
								? "is-done"
								: actions === index
									? "is-current"
									: ""
						}
						key={step}
					>
						<span>{index + 1}</span>
						{step}
					</li>
				))}
			</ol>
		</div>
	);
}

function ExactAdditionExample({
	example,
	actions,
	scaffoldType,
}: {
	example: AdditionAdventureWorkedExample;
	actions: number;
	scaffoldType: SupportView["scaffold_type"];
}) {
	const game = example.game;
	const response = example.correct_response;
	const chapter = game.chapter;
	const reveal = scaffoldType !== "visual_guidance" && response !== null;
	const addends = numberList(game.addends);
	const table = Array.isArray(game.table)
		? game.table.map((row) => numberList(row))
		: [];
	const rowLabels = Array.isArray(game.row_labels)
		? game.row_labels.map(String)
		: [];
	const columnLabels = Array.isArray(game.column_labels)
		? game.column_labels.map(String)
		: [];
	let visual: React.ReactNode = null;

	if (chapter === "fruit_catch") {
		const answer =
			response?.kind === "combine_quantities" ? response.total : null;
		visual = (
			<div
				className="worked-combine"
				role="img"
				aria-label="කාණ්ඩ එකතු කරන දෘශ්‍ය පියවර"
			>
				<div>
					{taggedNumbers(addends).map(({ id, value }) => (
						<strong className={actions >= 1 ? "is-active" : ""} key={id}>
							{value}
						</strong>
					))}
				</div>
				<span aria-hidden="true">→</span>
				<div
					className={actions >= 2 ? "worked-basket is-active" : "worked-basket"}
				>
					🧺
				</div>
				{reveal && actions >= 3 && (
					<p className="worked-answer">
						{addends.join(" + ")} = {answer}
					</p>
				)}
			</div>
		);
	} else if (chapter === "tuk_tuk_journey") {
		const start = numberValue(game.start);
		const stops = numberList(game.stops);
		const totals =
			response?.kind === "route_progression" ? response.totals : [];
		const revealCount = reveal
			? actions >= 3
				? stops.length
				: Math.min(actions, stops.length)
			: 0;
		const latestRevealed = Math.max(0, revealCount - 1);
		visual = (
			<div className="worked-route-demonstration">
				<div className="worked-route-start">
					<small>ආරම්භක අගය</small>
					<strong>{start}</strong>
				</div>
				<ol
					className="worked-addition-route"
					aria-label="එකතුව ඉදිරියට ගෙන යන පියවර"
				>
					{taggedNumbers(stops).map(({ id, index, value: stop }) => {
						const previous = index === 0 ? start : totals[index - 1];
						const showPrevious =
							index === 0 || (reveal && index <= revealCount);
						const showResult = reveal && index < revealCount;
						const state = showResult
							? "is-complete"
							: index === revealCount
								? "is-current"
								: "";
						return (
							<li className={state || undefined} key={id}>
								<span className="worked-route-arrow" aria-hidden="true">
									↓
								</span>
								<small>පියවර {index + 1}</small>
								<div className="worked-route-equation">
									<strong>{showPrevious ? previous : "?"}</strong>
									<span>+</span>
									<strong>{stop}</strong>
									<span>=</span>
									<strong className="worked-route-total">
										{showResult ? totals[index] : "?"}
									</strong>
								</div>
								{showResult && index < stops.length - 1 && (
									<p>
										<strong>{totals[index]}</strong> ඊළඟ පියවරට ගෙන යමු.
									</p>
								)}
							</li>
						);
					})}
				</ol>
				<p className="worked-route-explanation" aria-live="polite">
					{!reveal || actions === 0
						? `${start} ට ${stops[0]} එකතු කර පළමු නව එකතුව සොයමු.`
						: actions < 3
							? `${latestRevealed === 0 ? start : totals[latestRevealed - 1]} + ${stops[latestRevealed]} = ${totals[latestRevealed]}. මේ පිළිතුර ඊළඟ පියවරේ ආරම්භක අගයයි.`
							: "සෑම පියවරකම ලැබුණු පිළිතුර ඊළඟ එකතුවේ ආරම්භක අගය කරගෙන මාර්ගය දිගටම යමු."}
				</p>
			</div>
		);
	} else if (chapter === "carrying_crane") {
		const answer = response?.kind === "regroup_carry" ? response.total : null;
		const columns = columnAddition(addends);
		const activeColumn = actions <= 1 ? 4 : actions === 2 ? 3 : -1;
		const onesTotal = addends.reduce((sum, value) => sum + (value % 10), 0);
		const onesCarry = Math.floor(onesTotal / 10);
		const tensTotal = addends.reduce(
			(sum, value) => sum + (Math.floor(value / 10) % 10),
			columns.carries[3],
		);
		visual = (
			<div className="worked-column-addition">
				<table aria-label="ස්ථානීය තීරු අනුව එකතු කිරීම">
					<thead>
						<tr>
							<th scope="col" aria-label="ලකුණ" />
							{ADDITION_PLACE_LABELS.map((label, index) => (
								<th
									className={activeColumn === index ? "is-active" : ""}
									scope="col"
									key={label}
								>
									{label}
								</th>
							))}
						</tr>
					</thead>
					<tbody>
						<tr className="worked-carry-row">
							<th scope="row">ගෙනයාම</th>
							{columns.carries.map((carry, index) => (
								<td
									className={activeColumn === index ? "is-active" : ""}
									key={ADDITION_PLACE_LABELS[index]}
								>
									{reveal && actions >= 2 && carry > 0 ? carry : ""}
								</td>
							))}
						</tr>
						{columns.rows.map((row, rowIndex) => (
							// biome-ignore lint/suspicious/noArrayIndexKey: addend rows preserve the exact textbook order.
							<tr key={`${addends[rowIndex]}-${rowIndex}`}>
								<th scope="row">
									{rowIndex === columns.rows.length - 1 ? "+" : ""}
								</th>
								{row.map((digit, index) => (
									<td
										className={activeColumn === index ? "is-active" : ""}
										key={ADDITION_PLACE_LABELS[index]}
									>
										{index === 0 && digit === 0 ? "" : digit}
									</td>
								))}
							</tr>
						))}
						<tr className="worked-sum-row">
							<th scope="row">=</th>
							{columns.digits.map((digit, index) => {
								const visible =
									reveal &&
									(actions >= 3 ||
										(actions >= 1 && index === 4) ||
										(actions >= 2 && index === 3));
								return (
									<td
										className={activeColumn === index ? "is-active" : ""}
										key={ADDITION_PLACE_LABELS[index]}
									>
										{visible ? digit : "?"}
									</td>
								);
							})}
						</tr>
					</tbody>
				</table>
				{reveal && actions === 1 && (
					<p className="worked-column-explanation">
						එකක තීරුව: {addends.map((value) => value % 10).join(" + ")} ={" "}
						{onesTotal}. {onesTotal % 10} ලියමු.{" "}
						{onesCarry > 0 ? `${onesCarry} දහය තැනට ගෙන යමු.` : "ගෙනයාමක් නැහැ."}
					</p>
				)}
				{reveal && actions === 2 && (
					<p className="worked-column-explanation">
						දහය තීරුවට ගෙනා {columns.carries[3]} එකතු කරමු. එකතුව {tensTotal};{" "}
						{tensTotal % 10} ලියා {Math.floor(tensTotal / 10)} සියය තැනට ගෙන යමු.
					</p>
				)}
				{reveal && actions >= 3 && (
					<p className="worked-answer">
						{addends.map(formatNumber).join(" + ")} ={" "}
						{formatNumber(numberValue(answer))}
					</p>
				)}
			</div>
		);
	} else if (chapter === "market_delivery_planner") {
		const answer = response?.kind === "cargo_loading" ? response.total : null;
		visual = (
			<div className="worked-cargo">
				<div>
					{taggedNumbers(addends).map(({ id, value }) => (
						<strong className={actions >= 2 ? "is-loaded" : ""} key={id}>
							📦 {formatNumber(value)}
						</strong>
					))}
				</div>
				<span aria-hidden="true">→ 🛒</span>
				{reveal && actions >= 3 && (
					<p className="worked-answer">
						{addends.map(formatNumber).join(" + ")} ={" "}
						{formatNumber(numberValue(answer))}
					</p>
				)}
			</div>
		);
	} else if (chapter === "festival_data_detective") {
		const selected =
			response?.kind === "data_cell_selection"
				? new Set(response.selected_cells)
				: new Set<string>();
		const answer =
			response?.kind === "data_cell_selection" ? response.total : null;
		visual = (
			<div className="worked-data-table">
				<table>
					<thead>
						<tr>
							<th scope="col">•</th>
							{columnLabels.map((label) => (
								<th scope="col" key={label}>
									{label}
								</th>
							))}
						</tr>
					</thead>
					<tbody>
						{table.map((row, rowIndex) => (
							<tr key={rowLabels[rowIndex] ?? rowIndex}>
								<th scope="row">{rowLabels[rowIndex]}</th>
								{row.map((value, columnIndex) => {
									const id = `r${rowIndex}c${columnIndex}`;
									return (
										<td
											className={
												reveal && actions >= 2 && selected.has(id)
													? "is-selected"
													: ""
											}
											key={id}
										>
											{value}
										</td>
									);
								})}
							</tr>
						))}
					</tbody>
				</table>
				{reveal && actions >= 3 && (
					<p className="worked-answer">{formatNumber(numberValue(answer))}</p>
				)}
			</div>
		);
	}

	return (
		<div
			className="exact-worked-example exact-addition-example"
			data-worked-example-mode={example.mode}
			data-support-behavior={scaffoldType}
		>
			<p className="worked-same-question">ඔබට ලැබුණු ප්‍රශ්නය</p>
			<h4>{example.prompt_si}</h4>
			{visual}
			<ol className="worked-steps" aria-live="polite">
				{example.steps_si.map((step, index) => (
					<li
						className={
							actions > index
								? "is-done"
								: actions === index
									? "is-current"
									: ""
						}
						key={step}
					>
						<span>{index + 1}</span>
						{step}
					</li>
				))}
			</ol>
		</div>
	);
}

function ExactNumberPatternExample({
	example,
	actions,
	scaffoldType,
}: {
	example: NumberPatternWorkedExample;
	actions: number;
	scaffoldType: SupportView["scaffold_type"];
}) {
	const terms =
		(example.game.visible_terms as Array<number | null> | undefined) ?? [];
	const equations = (example.game.equations as string[] | undefined) ?? [];
	const reveal = scaffoldType !== "visual_guidance";
	return (
		<div
			className="exact-worked-example exact-pattern-example"
			data-worked-example-mode={example.mode}
			data-support-behavior={scaffoldType}
		>
			<p className="worked-same-question">ඔබට ලැබුණු ප්‍රශ්නය</p>
			<h4>{example.prompt_si}</h4>
			<ol className="worked-pattern-route" aria-label="සංඛ්‍යා රටාවේ පියවර">
				{terms.map((term, index) => (
					<li
						key={PATTERN_ROUTE_KEYS[index]}
						className={actions > 0 && index < 2 ? "is-active" : ""}
					>
						<strong>{term ?? (reveal && actions >= 3 ? "✓" : "?")}</strong>
						{index < terms.length - 1 && <span aria-hidden="true">→</span>}
					</li>
				))}
			</ol>
			{reveal && actions > 0 && (
				<div className="worked-pattern-equations" aria-live="polite">
					{equations
						.slice(0, actions >= 3 ? equations.length : actions)
						.map((equation) => (
							<strong key={equation}>{equation}</strong>
						))}
				</div>
			)}
			<ol className="worked-steps">
				{example.steps_si.map((step, index) => (
					<li
						className={
							actions > index
								? "is-done"
								: actions === index
									? "is-current"
									: ""
						}
						key={step}
					>
						<span>{index + 1}</span>
						{step}
					</li>
				))}
			</ol>
		</div>
	);
}

function ExactSubtractionExample({
	example,
	actions,
	scaffoldType,
}: {
	example: SubtractionAdventureWorkedExample;
	actions: number;
	scaffoldType: SupportView["scaffold_type"];
}) {
	const game = example.game;
	const places = (game.places as string[] | undefined) ?? [];
	const labels = (game.place_labels_si as string[] | undefined) ?? places;
	const staged =
		(game.staged_columns as
			| Array<{
					place: string;
					top: number;
					bottom: number;
					result: number;
					exchange_from?: string | null;
			  }>
			| undefined) ?? [];
	const reveal = scaffoldType !== "visual_guidance" && actions > 0;
	const visibleStages = reveal ? staged.slice(0, actions) : [];
	const visualFocus =
		places.length === 0
			? -1
			: places.length - 1 - Math.min(actions, places.length - 1);
	return (
		<div
			className="worked-subtraction"
			data-support-reveals={reveal || undefined}
		>
			<p>
				{String(game.minuend ?? "")} − {String(game.subtrahend ?? "")}
			</p>
			<fieldset className="support-place-grid">
				<legend className="sr-only">ඉස්මතු කළ ස්ථාන අගය තීරු</legend>
				{places.map((place, index) => (
					<div
						key={place}
						className={
							scaffoldType === "visual_guidance"
								? index === visualFocus
									? "is-active"
									: ""
								: visibleStages.some((stage) => stage.place === place)
									? "is-active"
									: ""
						}
					>
						<span>{labels[index]}</span>
					</div>
				))}
			</fieldset>
			{reveal && (
				<ol className="worked-subtraction-steps">
					{visibleStages.map((stage) => (
						<li key={stage.place}>
							{stage.exchange_from
								? `${stage.exchange_from} → ${stage.place}: ${stage.top} − ${stage.bottom} = ${stage.result}`
								: `${stage.place}: ${stage.top} − ${stage.bottom} = ${stage.result}`}
						</li>
					))}
				</ol>
			)}
			<ol className="worked-steps">
				{example.steps_si.map((step, index) => (
					<li
						className={
							actions > index
								? "is-done"
								: actions === index
									? "is-current"
									: ""
						}
						key={step}
					>
						<span>{index + 1}</span>
						{step}
					</li>
				))}
			</ol>
		</div>
	);
}

function MultiplicationSupport({
	manifest,
	actions,
}: {
	manifest: MultiplicationAdventureSupportManifest;
	actions: number;
}) {
	const example = manifest.worked_example;
	const game = example.game;
	const staged = (game.staged_digits as number[] | undefined) ?? [];
	const visible =
		manifest.scaffold_type === "visual_guidance"
			? []
			: staged.slice(0, actions);
	return (
		<div className="exact-worked-example" data-reduced-motion="inherit">
			<ol className="worked-steps">
				{example.steps_si.map((step, index) => (
					<li key={step} className={index < actions ? "is-shown" : undefined}>
						{index < actions ? step : "…"}
					</li>
				))}
			</ol>
			{visible.length > 0 && (
				<p className="staged-product" aria-hidden="true">
					{visible.join(" ")}
				</p>
			)}
		</div>
	);
}

export function AdaptiveSupportActivity({
	manifest,
	onProgress,
}: {
	manifest: AdaptiveManifest;
	onProgress(actions: number, complete: boolean): void;
}) {
	const [actions, setActions] = useState(0);
	const heading = useRef<HTMLHeadingElement>(null);
	useEffect(() => heading.current?.focus(), []);
	const act = () => {
		const next = Math.min(manifest.required_actions, actions + 1);
		setActions(next);
		onProgress(next, next >= manifest.required_actions);
	};
	const isNumberWorld = manifest.schema_version === "number-world-support-v1";
	const isNumberPattern =
		manifest.schema_version === "number-pattern-support-v1";
	const isSubtraction =
		manifest.schema_version === "subtraction-adventure-support-v1";
	const isFraction =
		manifest.schema_version === "fraction-adventure-support-v1";
	const isMultiplication =
		manifest.schema_version === "multiplication-adventure-support-v1";
	const headingText = isSubtraction
		? manifest.scaffold_type === "visual_guidance"
			? "දෘශ්‍ය මඟ පෙන්වීම"
			: manifest.scaffold_type === "step_by_step_guidance"
				? "පියවරෙන් පියවර ක්‍රියා"
				: "අඩු කිරීමේ පියවර"
		: isNumberWorld
			? manifest.scaffold_type === "visual_guidance"
				? "දෘශ්‍ය මඟ පෙන්වීම"
				: manifest.scaffold_type === "step_by_step_guidance"
					? "පියවරෙන් පියවර ක්‍රියා"
					: "විසඳන ආකාරය"
			: isNumberPattern
				? manifest.scaffold_type === "visual_guidance"
					? "දෘශ්‍ය මඟ පෙන්වීම"
					: "එකම රීතිය පියවරෙන් බලමු"
				: "දෘශ්‍ය විසඳුම";
	return (
		<div
			className={`scaffold-practice scaffold-practice--${manifest.scaffold_type}`}
			data-support-renderer={manifest.renderer_id}
		>
			<h3 ref={heading} tabIndex={-1}>
				{headingText}
			</h3>
			{isNumberWorld ? (
				<ExactNumberWorldExample
					example={(manifest as NumberWorldSupportManifest).worked_example}
					actions={actions}
					scaffoldType={manifest.scaffold_type}
				/>
			) : isNumberPattern ? (
				<ExactNumberPatternExample
					example={(manifest as NumberPatternSupportManifest).worked_example}
					actions={actions}
					scaffoldType={manifest.scaffold_type}
				/>
			) : isSubtraction ? (
				<ExactSubtractionExample
					example={
						(manifest as SubtractionAdventureSupportManifest).worked_example
					}
					actions={actions}
					scaffoldType={manifest.scaffold_type}
				/>
			) : isFraction ? (
				<div className="exact-worked-example">
					<h4>
						{
							(manifest as FractionAdventureSupportManifest).worked_example
								.prompt_si
						}
					</h4>
					<ol className="worked-steps">
						{(
							manifest as FractionAdventureSupportManifest
						).worked_example.steps_si.map((step) => (
							<li key={step}>{step}</li>
						))}
					</ol>
				</div>
			) : isMultiplication ? (
				<MultiplicationSupport
					manifest={manifest as MultiplicationAdventureSupportManifest}
					actions={actions}
				/>
			) : manifest.schema_version === "time-adventure-support-v1" ||
				manifest.schema_version === "division-adventure-support-v1" ||
				manifest.schema_version === "shape-adventure-support-v1" ? (
				<ol className="worked-steps">
					{manifest.worked_example.steps_si.map((step) => (
						<li key={step}>{step}</li>
					))}
				</ol>
			) : (
				<ExactAdditionExample
					example={
						(manifest as AdditionAdventureSupportManifest).worked_example
					}
					actions={actions}
					scaffoldType={manifest.scaffold_type}
				/>
			)}
			<button
				type="button"
				onClick={act}
				disabled={actions >= manifest.required_actions}
			>
				{actions >= manifest.required_actions
					? "විසඳුම සම්පූර්ණයි"
					: `පියවර ${actions + 1} පෙන්වන්න`}
			</button>
		</div>
	);
}
