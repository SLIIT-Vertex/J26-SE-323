import { useState } from "react";
import type { DraftMissionRecord } from "./api/generated";
import type { FixtureRoundClient, FixtureRoundView } from "./api/fixtureRoundClient";
import { learningAreaName } from "./learningAreas";

const SUPPORT_LABELS = {
	visual_guidance: "දෘශ්‍ය මඟ පෙන්වීම",
	worked_parallel_example: "සමාන්තර උදාහරණය",
	step_by_step_guidance: "පියවරෙන් පියවර මඟ පෙන්වීම",
} as const;

export function FixtureRoundPlayer({
	mission,
	sessionId,
	rounds,
	busy,
	onBusy,
	onFailure,
	onBack,
}: {
	mission: DraftMissionRecord;
	sessionId: string;
	rounds: Pick<FixtureRoundClient, "open" | "answer" | "continue">;
	busy: boolean;
	onBusy(value: boolean): void;
	onFailure(error: unknown): void;
	onBack(): void;
}) {
	const [round, setRound] = useState<FixtureRoundView | null>(null);
	const [selected, setSelected] = useState<string | null>(null);

	const run = async (operation: () => Promise<FixtureRoundView>) => {
		onBusy(true);
		try {
			const next = await operation();
			setRound(next);
			setSelected(null);
			onBusy(false);
		} catch (error) {
			onFailure(error);
		}
	};

	const answering =
		round?.phase === "unsupported_before" ||
		round?.phase === "supported_practice" ||
		round?.phase === "unsupported_after";

	return (
		<section
			className="draft-player"
			data-draft-player={mission.template_id}
			data-template-id={mission.template_id}
			data-fixture-round={mission.area_id}
		>
			<button type="button" className="text-action" onClick={onBack}>
				ආපසු
			</button>
			<h1>{learningAreaName(mission.area_id)}</h1>
			{!round && (
				<button
					type="button"
					className="primary-action"
					disabled={busy}
					onClick={() => run(() => rounds.open(mission.area_id, sessionId))}
				>
					ආරම්භ කරන්න
				</button>
			)}
			{round?.support && (
				<aside className="support-panel" data-support-visible="true" data-support-type={round.support.support_type}>
					<p className="support-badge">{SUPPORT_LABELS[round.support.support_type]}</p>
					<p>{round.support.body_si}</p>
				</aside>
			)}
			{round?.phase === "withdraw" && (
				<p>උදව් අවසන්. අලුත් ප්‍රශ්නයේදී ඉඟි නොපෙන්වයි.</p>
			)}
			{round?.prompt_si && <p className="question">{round.prompt_si}</p>}
			{answering && round && (
				<div className="choice-grid">
					{round.options.map((option) => (
						<button
							type="button"
							key={option.option_id}
							className={selected === option.option_id ? "choice choice--selected" : "choice"}
							aria-pressed={selected === option.option_id}
							onClick={() => setSelected(option.option_id)}
						>
							{option.text_si}
						</button>
					))}
				</div>
			)}
			{answering && round && (
				<button
					type="button"
					className="primary-action"
					disabled={!selected || busy}
					onClick={() =>
						run(() => rounds.answer(round.episode_id, selected ?? ""))
					}
				>
					පිළිතුර යවන්න
				</button>
			)}
			{round?.phase === "support" && (
				<button
					type="button"
					className="primary-action"
					disabled={busy}
					onClick={() => run(() => rounds.continue(round.episode_id))}
				>
					උදව් සමඟ පුහුණු වෙමු
				</button>
			)}
			{round?.phase === "withdraw" && (
				<button
					type="button"
					className="primary-action"
					disabled={busy}
					onClick={() => run(() => rounds.continue(round.episode_id))}
				>
					උදව් අවසන්
				</button>
			)}
			{round && round.server_scores.length > 0 && (
				<ul aria-label="සේවාදායක ලකුණු">
					{round.server_scores.map((score) => (
						<li
							key={score.measurement_role}
							data-server-score={score.earned_score}
							data-maximum-score={score.maximum_score}
							data-scoring-version={score.scoring_version}
							data-server-authoritative="true"
							data-measurement-role={score.measurement_role}
						>
							සේවාදායක ලකුණු {score.earned_score}/{score.maximum_score}
						</li>
					))}
				</ul>
			)}
			{round?.phase === "completed" && round.reward && (
				<p>සහභාගීත්ව ත්‍යාගය +{round.reward.points}</p>
			)}
		</section>
	);
}
