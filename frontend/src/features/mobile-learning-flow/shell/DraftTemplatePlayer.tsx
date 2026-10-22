// biome-ignore-all lint/a11y/useButtonType: this application contains no HTML forms; all buttons are application actions.

import type { DraftMissionRecord, DraftTemplateId } from "../api/generated";
import { learningAreaName } from "../learningAreas";
import { Back } from "./common";

export const DRAFT_TEMPLATE_LABELS = {
	market_mission: "Market Mission",
	pattern_temple: "Pattern Temple",
	parcel_workshop: "Parcel Workshop",
	word_workshop: "Word Workshop",
	story_studio: "Story Studio",
	eco_explorer: "Eco Explorer",
	pillam_journey: "Pillam Journey",
	punctuation_journey: "Punctuation Journey",
	riddle_journey: "Riddle Journey",
} as const;

export function DraftTemplatePlayer({
	mission,
	busy,
	submitted,
	onSubmit,
	onBack,
}: {
	mission: DraftMissionRecord & {
		template_id: Exclude<DraftTemplateId, "half_set">;
	};
	busy: boolean;
	submitted: boolean;
	onSubmit(): void;
	onBack(): void;
}) {
	const draftItems = [...mission.outcome_slots, ...mission.draft_item_slots];
	return (
		<section
			className="draft-player"
			data-draft-player={mission.template_id}
			data-template-id={mission.template_id}
		>
			<Back onClick={onBack} />
			<p className="eyebrow">{DRAFT_TEMPLATE_LABELS[mission.template_id]}</p>
			<h1>{learningAreaName(mission.area_id)}</h1>
			<p data-template-id={mission.template_id}>{mission.template_id}</p>
			{draftItems.map((slot) => (
				<p className="draft-item" key={slot.node_id}>
					{slot.item_text.split(" Medium-confidence trace.")[0]}
				</p>
			))}
			{mission.held_slots.length > 0 && (
				<p className="held-slots" data-held-count={mission.held_slots.length}>
					රඳවා ඇති සටහන් ප්‍රශ්නයක් නොවේ.
				</p>
			)}
			<button
				className="primary-action"
				disabled={busy || submitted}
				onClick={onSubmit}
			>
				පිළිතුර යවන්න
			</button>
		</section>
	);
}
