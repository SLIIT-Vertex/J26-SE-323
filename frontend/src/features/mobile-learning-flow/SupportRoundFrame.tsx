import { type ReactNode, useEffect, useRef } from "react";
import type {
	EnglishSupportTagKey,
	SupportAnswer,
	SupportLesson,
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
 * plays, or strongly marked in a demonstration. Either way the child can still touch the board
 * and place the answer themselves.
 */
function AnswerBoard({
	answer,
	hideLines = false,
	children,
}: {
	answer?: SupportAnswer | null;
	/** A lesson says the answer in words, so the raw answer lines are left out. */
	hideLines?: boolean;
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
			>
				{children}
			</div>
			{answer && !hideLines && answer.lines.length > 0 && (
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

/** What the help says before the child looks at the board: their mistake, theory, hints. */
function LessonIntro({ lesson }: { lesson: SupportLesson }) {
	const empty =
		!lesson.diagnosis &&
		lesson.notes.length === 0 &&
		lesson.another_view_si.length === 0 &&
		lesson.hints_si.length === 0;
	if (empty) return null;
	return (
		<div className="support-lesson">
			<h3>{lesson.title_si}</h3>
			{lesson.diagnosis && (
				<div className="support-lesson-diagnosis">
					<p>
						<strong>ඔබ කළේ:</strong> {lesson.diagnosis.you_did_si}
					</p>
					<p>
						<strong>වැරදුණු තැන:</strong> {lesson.diagnosis.went_wrong_si}
					</p>
				</div>
			)}
			{lesson.notes.length > 0 && (
				<dl className="support-lesson-notes">
					{lesson.notes.map((note) => (
						<div key={note.title_si}>
							<dt>{note.title_si}</dt>
							<dd>{note.text_si}</dd>
						</div>
					))}
				</dl>
			)}
			{lesson.another_view_si.length > 0 && (
				<div className="support-lesson-another">
					<strong>වෙනත් ආකාරයකින් බලමු</strong>
					<ul>
						{lesson.another_view_si.map((line) => (
							<li key={line}>{line}</li>
						))}
					</ul>
				</div>
			)}
			{lesson.hints_si.length > 0 && (
				<div className="support-lesson-hints">
					<strong>ඉඟි</strong>
					<ul>
						{lesson.hints_si.map((hint) => (
							<li key={hint}>{hint}</li>
						))}
					</ul>
				</div>
			)}
		</div>
	);
}

/** The solution under the board: every step with its numbers, then the answer, large. */
function LessonSolution({ lesson }: { lesson: SupportLesson }) {
	if (lesson.steps_si.length === 0 && !lesson.answer_si) return null;
	return (
		<div className="support-lesson-solution">
			{lesson.steps_si.length > 0 && (
				<ol className="support-lesson-steps">
					{lesson.steps_si.map((step) => (
						<li key={step}>{step}</li>
					))}
				</ol>
			)}
			{lesson.answer_si && (
				<p className="support-lesson-answer">
					<strong>පිළිතුර</strong>
					<span>{lesson.answer_si}</span>
				</p>
			)}
		</div>
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
	const lesson = manifest.lesson ?? null;
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
			{lesson && <LessonIntro lesson={lesson} />}
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
					<AnswerBoard
						answer={manifest.activity.answer}
						hideLines={lesson !== null}
					>
						{renderActivity(manifest.activity)}
					</AnswerBoard>
					{lesson && !manifest.worked_example && (
						<LessonSolution lesson={lesson} />
					)}
				</div>
			)}
			{manifest.worked_example && (
				<div
					className="support-round-activity"
					data-worked-parallel-example="true"
				>
					<h3>{manifest.worked_example.prompt_si}</h3>
					<AnswerBoard
						hideLines={lesson !== null}
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
					<ol className="support-lesson-steps">
						{manifest.worked_example.steps_si.map((step) => (
							<li key={step}>{step}</li>
						))}
					</ol>
					{lesson && <LessonSolution lesson={{ ...lesson, steps_si: [] }} />}
				</div>
			)}
			{manifest.stage_kind === "view" && (
				<button
					type="button"
					className="primary-action"
					disabled={busy}
					onClick={onViewComplete}
				>
					{lesson?.continue_label_si ?? "දැන් මම කරමි"}
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
