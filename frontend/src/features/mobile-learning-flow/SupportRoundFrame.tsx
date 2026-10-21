import { type ReactNode, useEffect, useRef } from "react";
import type {
	EnglishSupportTagKey,
	SupportAnswer,
	SupportRoundActivity,
	SupportView,
} from "./api/generated";
import "./support-round-frame.css";

export const ENGLISH_SUPPORT_TAGS: Record<EnglishSupportTagKey, string> = {
	VISUAL_GUIDANCE: "Visual guidance",
	GUIDED_REASONING: "Guided reasoning",
	WORKED_EXAMPLE: "Worked example",
	SIMPLER_VERSION: "Simpler version",
	PREREQUISITE_REPAIR: "Prerequisite repair",
	CONCEPTUAL_REEXPLANATION: "Conceptual re-explanation",
};

const MARKABLE =
	"button, label, li, td, th, option, [role='option'], span, strong, text";

/** Board elements whose own visible label is one of the answer's marks. */
function markAnswer(board: HTMLElement, marks: ReadonlySet<string>) {
	for (const element of board.querySelectorAll<HTMLElement>(MARKABLE)) {
		const label = element.textContent?.trim().toLowerCase() ?? "";
		element.classList.toggle("support-answer-mark", marks.has(label));
	}
}

/**
 * The game board of a help stage with its real answer shown: faintly tinted while the child
 * plays, or fully solved and untouchable in a worked example.
 */
function AnswerBoard({
	answer,
	children,
}: {
	answer?: SupportAnswer | null;
	children: ReactNode;
}) {
	const board = useRef<HTMLDivElement>(null);
	const marks = answer?.marks.join("\u0000") ?? "";
	useEffect(() => {
		const element = board.current;
		if (!element || !marks) return;
		const wanted = new Set(
			marks.split("\u0000").map((mark) => mark.toLowerCase()),
		);
		markAnswer(element, wanted);
		// The board re-renders as the child plays; keep the marks on what it draws next.
		const observer = new MutationObserver(() => markAnswer(element, wanted));
		observer.observe(element, {
			childList: true,
			subtree: true,
			characterData: true,
		});
		return () => observer.disconnect();
	}, [marks]);
	const filled = answer?.mode === "filled";
	return (
		<>
			<div
				ref={board}
				className="support-answer-board"
				data-answer-mode={answer?.mode ?? "none"}
				inert={filled || undefined}
			>
				{children}
			</div>
			{answer && answer.lines.length > 0 && (
				<div className="support-answer-lines" data-answer-mode={answer.mode}>
					<strong>{filled ? "විසඳුම" : "ඉඟිය"}</strong>
					<ul>
						{answer.lines.map((line) => (
							<li key={line}>{line}</li>
						))}
					</ul>
				</div>
			)}
		</>
	);
}

/** Shared support chrome. The feature still owns and renders its normal game activity. */
export function SupportRoundFrame({
	support,
	renderActivity,
	onViewComplete,
	children,
	busy = false,
}: {
	support: SupportView;
	renderActivity(activity: SupportRoundActivity): ReactNode;
	onViewComplete(): void;
	children?: ReactNode;
	busy?: boolean;
}) {
	const manifest = support.game_manifest;
	if (manifest.schema_version !== "support-round-v1") return null;
	const englishTag = ENGLISH_SUPPORT_TAGS[manifest.english_tag_key];
	return (
		<section
			className="support-round-frame"
			data-support-type={support.scaffold_type}
			data-support-stage={manifest.stage_kind}
		>
			<span className="support-round-tag" lang="en">
				{englishTag}
			</span>
			{manifest.cues_si.map((cue) => (
				<p key={cue}>{cue}</p>
			))}
			{manifest.guidance && manifest.guidance.length > 0 && (
				<ol className="support-round-guidance">
					{manifest.guidance.map((pair) => (
						<li key={pair.question_si}>
							<strong>{pair.question_si}</strong>
							<span>{pair.answer_si}</span>
						</li>
					))}
				</ol>
			)}
			{manifest.activity && (
				<div className="support-round-activity">
					<h3>{manifest.activity.prompt_si}</h3>
					<AnswerBoard answer={manifest.activity.answer}>
						{renderActivity(manifest.activity)}
					</AnswerBoard>
				</div>
			)}
			{manifest.worked_example && (
				<div
					className="support-round-activity"
					data-worked-parallel-example="true"
				>
					<h3>{manifest.worked_example.prompt_si}</h3>
					<AnswerBoard
						answer={
							manifest.worked_example.answer ?? {
								mode: "filled",
								lines: [],
								marks: [],
							}
						}
					>
						{renderActivity({
							presentation_id: manifest.worked_example.presentation_id,
							revision_id: manifest.worked_example.revision_id,
							skill_id: manifest.worked_example.skill_id,
							prompt_si: manifest.worked_example.prompt_si,
							game: manifest.worked_example.game,
							returns_to_failed_item: false,
						})}
					</AnswerBoard>
					<ol>
						{manifest.worked_example.steps_si.map((step) => (
							<li key={step}>{step}</li>
						))}
					</ol>
				</div>
			)}
			{manifest.stage_kind === "view" && (
				<button
					type="button"
					className="primary-action"
					disabled={busy}
					onClick={onViewComplete}
				>
					දැන් මම කරමි
				</button>
			)}
			{children}
		</section>
	);
}

/**
 * The support frame with the feature's own check button. The button is hidden while the round
 * shows a demonstration, which the child ends with the frame's own button instead.
 */
export function SupportRoundPlay({
	support,
	busy,
	ready,
	checkLabel,
	checkClassName = "primary-action",
	onCheck,
	onViewComplete,
	renderActivity,
}: {
	support: SupportView;
	busy: boolean;
	ready: boolean;
	checkLabel: string;
	checkClassName?: string;
	onCheck(): void;
	onViewComplete(): void;
	renderActivity(activity: SupportRoundActivity): ReactNode;
}) {
	const manifest = support.game_manifest;
	return (
		<SupportRoundFrame
			support={support}
			busy={busy}
			onViewComplete={onViewComplete}
			renderActivity={renderActivity}
		>
			{manifest.schema_version === "support-round-v1" &&
				manifest.stage_kind !== "view" && (
					<button
						type="button"
						className={checkClassName}
						disabled={busy || !ready}
						onClick={onCheck}
					>
						{checkLabel}
					</button>
				)}
		</SupportRoundFrame>
	);
}
