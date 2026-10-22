import { useEffect, useRef } from "react";
import type { HistoryModel, Trace } from "./api";
import { HELP_STYLE, HelpMark, pct } from "./charts";
import { answerLabel } from "./game-row";

/**
 * One game, seen through one model, in a sheet that slides up from the bottom.
 * Model 1 lists every reason it weighed with its probability; Model 2 shows the help order it
 * chose and why, then each help that was given and how it went; Model 3 shows the fair test.
 */
export function GameDetailSheet({
	model,
	trace,
	onClose,
}: {
	model: HistoryModel;
	trace: Trace | null;
	onClose(): void;
}) {
	const sheet = useRef<HTMLDivElement>(null);
	useEffect(() => {
		sheet.current?.focus();
		const onKey = (event: KeyboardEvent) => {
			if (event.key === "Escape") onClose();
		};
		document.addEventListener("keydown", onKey);
		return () => document.removeEventListener("keydown", onKey);
	}, [onClose]);
	const title = trace?.summary.area_title?.split(" · ").at(-1) ?? "Game";
	return (
		<div className="rd-sheet-layer">
			<button
				type="button"
				className="rd-sheet-backdrop"
				aria-label="Close game details"
				onClick={onClose}
			/>
			<div
				className="rd-sheet"
				role="dialog"
				aria-modal="true"
				aria-label={`${title} details`}
				tabIndex={-1}
				ref={sheet}
			>
				<div className="rd-sheet__grip" aria-hidden="true" />
				<header className="rd-sheet__head">
					<div>
						<h3>{title}</h3>
						{trace && (
							<p>
								First try {answerLabel(trace.summary.before_correct)} · Alone
								after help{" "}
								{answerLabel(trace.summary.after_correct, "Not retested")}
							</p>
						)}
					</div>
					<button type="button" className="rd-sheet__close" onClick={onClose}>
						Close
					</button>
				</header>
				<div className="rd-sheet__body">
					{!trace ? (
						<p className="rd-quiet">Loading this game…</p>
					) : model === "misconception" ? (
						<MisconceptionDetail trace={trace} />
					) : model === "support" ? (
						<SupportDetail trace={trace} />
					) : (
						<GainDetail trace={trace} />
					)}
				</div>
			</div>
		</div>
	);
}

function MisconceptionDetail({ trace }: { trace: Trace }) {
	const model1 = trace.model1;
	if (!model1)
		return (
			<p className="rd-quiet">
				The first try was right, so Model 1 had no mistake to explain.
			</p>
		);
	const reasons = [...(model1.reasons ?? [])].sort(
		(a, b) => b.probability - a.probability,
	);
	return (
		<>
			<section>
				<h4>{model1.headline}</h4>
				<p>{model1.why}</p>
				{model1.uncertain && (
					<p className="rd-sheet__note">
						No reason was clear enough to name, so it is recorded as “Reason not
						identified”.
					</p>
				)}
			</section>
			<section>
				<h4>Every reason the model considered</h4>
				<ol className="rd-sheet__bars">
					{reasons.map((reason, index) => (
						<li
							key={reason.code ?? reason.label}
							className={index === 0 ? "is-top" : undefined}
						>
							<span>{reason.label}</span>
							<span className="rd-sheet__bar" aria-hidden="true">
								<i
									style={{ width: `${Math.max(2, reason.probability * 100)}%` }}
								/>
							</span>
							<b>{pct(reason.probability)}</b>
						</li>
					))}
				</ol>
			</section>
			{model1.history_effect && (
				<section>
					<h4>Effect of earlier games</h4>
					<p>{model1.history_effect}</p>
				</section>
			)}
		</>
	);
}

function SupportDetail({ trace }: { trace: Trace }) {
	const model2 = trace.model2;
	if (!model2)
		return <p className="rd-quiet">No help was needed in this game.</p>;
	return (
		<>
			<section>
				<h4>Why this order</h4>
				<p>
					<b>{model2.headline}</b>
				</p>
				<p>{model2.why}</p>
				{model2.steps.length > 0 && (
					<ol className="rd-sheet__steps">
						{model2.steps.map((step) => (
							<li key={step}>{step}</li>
						))}
					</ol>
				)}
				{model2.history_note && (
					<p className="rd-sheet__note">{model2.history_note}</p>
				)}
			</section>
			<section>
				<h4>Help order chosen</h4>
				<ol className="rd-sheet__order">
					{model2.order.map((code, index) => {
						const used = trace.rounds.find(
							(round) => round.scaffold_type === code,
						);
						return (
							<li key={code} className={used ? "is-used" : undefined}>
								<HelpMark code={code} />
								<span>
									<b>
										{index + 1}. {HELP_STYLE[code]?.name ?? code}
									</b>
									<small>{orderReason(index, model2.why)}</small>
								</span>
								<small>
									{used ? `Given in round ${used.round_number}` : "Not needed"}
								</small>
							</li>
						);
					})}
				</ol>
			</section>
			<section>
				<h4>Help recorded, round by round</h4>
				{trace.rounds.length === 0 ? (
					<p className="rd-quiet">No help round was opened.</p>
				) : (
					<ol className="rd-sheet__rounds">
						{trace.rounds.map((round) => (
							<li key={round.round_number}>
								<header>
									<HelpMark code={round.scaffold_type} />
									<b>
										{round.round_number}. {round.name}
									</b>
									<span className={roundClass(round.outcome)}>
										{round.outcome_label ?? round.outcome ?? "In progress"}
									</span>
								</header>
								{(round.what_child_saw ?? []).length > 0 && (
									<ul>
										{round.what_child_saw?.map((line) => (
											<li key={line}>{line}</li>
										))}
									</ul>
								)}
								{round.attempts.length > 0 && (
									<p className="rd-quiet">
										Answers with this help:{" "}
										{round.attempts
											.map((attempt) =>
												attempt.correct
													? "✓ right"
													: `✗ ${readable(attempt.error) || "wrong"}`,
											)
											.join(" · ")}
									</p>
								)}
								<p className="rd-quiet">{round.rule}</p>
							</li>
						))}
					</ol>
				)}
			</section>
		</>
	);
}

/** Why a help sits where it does in the order. */
function orderReason(index: number, why: string) {
	if (index === 0) return `Chosen first: ${why}`;
	return "Next in this subject's standard order, if the help before it was not enough";
}

function readable(code: string | null) {
	return (code ?? "").replaceAll("_", " ");
}

function roundClass(outcome: string | null) {
	if (outcome === "succeeded") return "rd-sheet__pill is-yes";
	if (outcome === "failed") return "rd-sheet__pill is-no";
	return "rd-sheet__pill";
}

function GainDetail({ trace }: { trace: Trace }) {
	const model3 = trace.model3;
	if (!model3)
		return (
			<p className="rd-quiet">The fair test has not finished for this game.</p>
		);
	return (
		<>
			<section>
				<h4>{model3.headline}</h4>
				<p>{model3.why}</p>
				{(model3.before || model3.after) && (
					<p>
						Before help: <b>{model3.before ?? "—"}</b> · Alone after help:{" "}
						<b>{model3.after ?? "—"}</b>
					</p>
				)}
			</section>
			<section>
				<h4>Fair-test checks</h4>
				<ul className="rd-sheet__checks">
					{model3.checks.map((check) => (
						<li key={check.name}>
							<span aria-hidden="true">{check.passed ? "✓" : "✗"}</span>{" "}
							{check.name}
						</li>
					))}
				</ul>
				{model3.formula && <p className="rd-quiet">{model3.formula}</p>}
			</section>
		</>
	);
}
