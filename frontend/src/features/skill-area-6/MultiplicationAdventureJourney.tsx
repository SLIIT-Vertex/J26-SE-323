import {
	useCallback,
	useEffect,
	useMemo,
	useRef,
	useState,
	type CSSProperties,
} from "react";
import type {
	ConstructedResponse,
	ExperimentCondition,
	PresentationManifest,
	SupportView,
} from "../mobile-learning-flow/api/generated";
import type { LearningFlowClient } from "../mobile-learning-flow/api/learningFlowClient";
import { ContractError } from "../mobile-learning-flow/api/runtime";
import {
	AdaptiveSupportActivity,
	SUPPORT_TYPE_LABELS,
} from "../mobile-learning-flow/AdaptiveSupportActivity";
import {
	AdventureBackButton,
	SuccessCelebration,
} from "../mobile-learning-flow/AdventureShared";
import {
	MULTIPLICATION_CHAPTERS,
	MULTIPLICATION_SKILLS,
	type MultiplicationChapter,
} from "./manifest";

type Step =
	| "chapters"
	| "question"
	| "feedback"
	| "support"
	| "withdrawing"
	| "result";

export function MultiplicationAdventureJourney({
	api,
	learnerId,
	condition,
	reducedMotion,
	onBack,
	onFailure,
}: {
	api: Pick<
		LearningFlowClient,
		| "open"
		| "answerBefore"
		| "completeSupport"
		| "withdrawSupport"
		| "presentAfter"
		| "answerAfter"
	>;
	learnerId: string;
	condition: ExperimentCondition;
	reducedMotion: boolean;
	onBack(): void;
	onFailure(error: unknown): void;
}) {
	const [step, setStep] = useState<Step>("chapters");
	const [chapter, setChapter] = useState<MultiplicationChapter | null>(null);
	const [episodeId, setEpisodeId] = useState<string | null>(null);
	const [manifest, setManifest] = useState<PresentationManifest | null>(null);
	const [support, setSupport] = useState<SupportView | null>(null);
	const [response, setResponse] = useState<ConstructedResponse | null>(null);
	const [activeSkillId, setActiveSkillId] = useState<string | null>(null);
	const [busy, setBusy] = useState(false);
	const [message, setMessage] = useState("");
	const [answeredCorrectly, setAnsweredCorrectly] = useState(false);
	const [startedAt, setStartedAt] = useState(0);
	const [supportActions, setSupportActions] = useState(0);
	const [supportComplete, setSupportComplete] = useState(false);
	const [digitEntries, setDigitEntries] = useState(0);
	const openInFlight = useRef(false);
	const requestInFlight = useRef(false);
	const skills = useMemo(
		() => MULTIPLICATION_SKILLS.filter((skill) => skill.chapter === chapter),
		[chapter],
	);
	const activeChallengeIndex = Math.max(
		0,
		skills.findIndex((skill) => skill.id === activeSkillId),
	);
	const activeChapterIndex = MULTIPLICATION_CHAPTERS.findIndex(
		(item) => item.id === chapter,
	);
	const isLastChallenge = activeChallengeIndex === skills.length - 1;
	const resetWork = useCallback(() => {
		setResponse(null);
		setDigitEntries(0);
		setStartedAt(Date.now());
		setMessage("");
		setSupportActions(0);
		setSupportComplete(false);
	}, []);
	const run = useCallback(
		async <T,>(operation: () => Promise<T>): Promise<T | undefined> => {
			setBusy(true);
			try {
				return await operation();
			} catch (error) {
				onFailure(error);
				return undefined;
			} finally {
				setBusy(false);
			}
		},
		[onFailure],
	);

	useEffect(() => {
		if (step !== "withdrawing" || !episodeId || !support || !manifest) return;
		let cancelled = false;
		void (async () => {
			const withdrawn = await run(() =>
				api.withdrawSupport(
					episodeId,
					{
						request_id: crypto.randomUUID(),
						support_revision_id: support.revision_id,
						manifest_revision_id: manifest.revision_id,
						all_support_removed: true,
						answer_revealing_state_cleared: true,
						input_handlers_cleared: true,
					},
					crypto.randomUUID(),
				),
			);
			if (!withdrawn || cancelled) return;
			const next = await run(() =>
				api.presentAfter(episodeId, crypto.randomUUID()),
			);
			if (!next || cancelled) return;
			setManifest(next.manifest);
			setSupport(null);
			resetWork();
			setStep("question");
		})();
		return () => {
			cancelled = true;
		};
	}, [api, episodeId, manifest, resetWork, run, step, support]);

	const openSkill = async (skillId: string, selectedChapter = chapter) => {
		if (openInFlight.current) return;
		openInFlight.current = true;
		const opened = await run(() =>
			api.open(
				{
					learner_id: learnerId,
					session_id: crypto.randomUUID(),
					grade: 5,
					medium: "si",
					condition,
					environment: "development",
					allow_draft: true,
					area_id: "G5-AREA-MAT-06",
					atomic_skill_id: skillId,
				},
				crypto.randomUUID(),
			),
		);
		openInFlight.current = false;
		if (!opened) return;
		if (selectedChapter) setChapter(selectedChapter);
		setEpisodeId(opened.episode_id);
		setActiveSkillId(skillId);
		setManifest(opened.manifest);
		setSupport(null);
		setAnsweredCorrectly(false);
		resetWork();
		setStep("question");
	};

	const answer = async () => {
		if (!episodeId || !manifest || !response || requestInFlight.current) return;
		requestInFlight.current = true;
		const body = {
			constructed_response: {
				...response,
				presentation_id: manifest.presentation_id,
				item_revision_id: manifest.revision_id,
				interaction_version: "constructed-response-v1" as const,
			},
			response_time_ms: reducedMotion
				? null
				: Math.max(0, Date.now() - startedAt),
			interaction_summary: {
				digit_entry_count: digitEntries,
				attempt_count: 1,
				first_action_ms: 0,
				active_time_ms: reducedMotion ? 0 : Math.max(0, Date.now() - startedAt),
			},
		};
		const next = await run(() =>
			manifest.measurement_role === "unsupported_after"
				? api.answerAfter(episodeId, body, crypto.randomUUID())
				: api.answerBefore(episodeId, body, crypto.randomUUID()),
		);
		requestInFlight.current = false;
		if (!next) return;
		if (!next.server_score || next.server_score.correct == null) {
			onFailure(new ContractError("STALE_OR_INCOMPATIBLE_MANIFEST"));
			return;
		}
		const correct = next.server_score.correct === true;
		setAnsweredCorrectly(correct);
		setMessage(correct ? "ක්‍රියාව සම්පූර්ණයි!" : "නැවත බලමු.");
		if (next.status === "support_active" && next.support)
			setSupport(next.support);
		else setSupport(null);
		setStep(next.status === "support_active" ? "feedback" : "result");
	};

	const finishSupport = async () => {
		if (!episodeId || !support) return;
		const supportManifest = support.game_manifest;
		if (supportManifest.schema_version === "half-set-manifest-v1") return;
		const completed = await run(() =>
			api.completeSupport(
				episodeId,
				{
					duration_ms: Math.max(1000, Date.now() - startedAt),
					steps_viewed: Math.max(1, supportActions),
					manifest_revision_id: supportManifest.revision_id,
					// The server accepts the support as complete only with the renderer, the
					// parallel example and the number of support actions (as in the other adventures).
					interaction_summary: {
						completed: true,
						renderer_id: supportManifest.renderer_id,
						parallel_example_id: supportManifest.parallel_example_id,
						support_actions: supportActions,
					},
				},
				crypto.randomUUID(),
			),
		);
		if (!completed) return;
		setSupport(null);
		resetWork();
		setStep("withdrawing");
	};

	const advance = () => {
		const nextChallenge = skills[activeChallengeIndex + 1];
		if (nextChallenge) {
			void openSkill(nextChallenge.id);
			return;
		}
		setStep("chapters");
	};

	return (
		<section
			className="learning-adventure multiplication-adventure"
			data-episode-id={episodeId ?? undefined}
			data-multiplication-step={step}
			data-skill-id={activeSkillId ?? undefined}
			data-reduced-motion={reducedMotion ? "true" : "false"}
		>
			<header className="adventure-header">
				<AdventureBackButton
					onClick={step === "chapters" ? onBack : () => setStep("chapters")}
				/>
				<h1>ගුණ කිරීම</h1>
			</header>
			{step === "chapters" && (
				<div className="adventure-cards">
					{MULTIPLICATION_CHAPTERS.map((item, index) => {
						const count = MULTIPLICATION_SKILLS.filter(
							(skill) => skill.chapter === item.id,
						).length;
						return (
							<button
								type="button"
								key={item.id}
								style={
									{
										"--card-tone": ["#54CBAB", "#E6A23C", "#7B61E8"][index],
									} as CSSProperties
								}
								onClick={() => {
									const first = MULTIPLICATION_SKILLS.find(
										(skill) => skill.chapter === item.id,
									);
									if (first) void openSkill(first.id, item.id);
								}}
							>
								<img src={item.asset} alt="" />
								<span>
									<strong>{item.title}</strong>
									<small>
										අභියෝග {count}ක් · {item.difficulty}
									</small>
								</span>
							</button>
						);
					})}
				</div>
			)}
			{(step === "question" || step === "feedback") && manifest && (
				<div className="adventure-play">
					<ChallengeProgress
						index={activeChallengeIndex}
						count={skills.length}
					/>
					<p className="game-round-label">
						ක්‍රීඩාව {activeChapterIndex + 1} · අභියෝගය {activeChallengeIndex + 1}/
						{skills.length}
					</p>
					<h2>{manifest.prompt_si}</h2>
					<MultiplicationMechanic
						key={manifest.revision_id}
						game={manifest.game ?? {}}
						onChange={(next, entries) => {
							setResponse(next);
							setDigitEntries((current) => current + entries);
						}}
					/>
					{step === "feedback" && <h3 role="status">{message}</h3>}
					<button
						type="button"
						className="primary-action"
						disabled={step === "question" && (!response || busy)}
						onClick={
							step === "feedback"
								? () => setStep(support ? "support" : "result")
								: () => void answer()
						}
					>
						{step === "feedback"
							? support
								? "උදව්ව බලන්න"
								: "ඊළඟට"
							: "තහවුරු කරන්න"}
					</button>
				</div>
			)}
			{step === "support" && support && (
				<div className="adventure-play" data-support-visible="true">
					<p
						className="support-badge"
						data-support-type={support.scaffold_type}
					>
						උදව් වර්ගය: {SUPPORT_TYPE_LABELS[support.scaffold_type]}
					</p>
					<h2>{support.title_si}</h2>
					{support.game_manifest.schema_version !== "half-set-manifest-v1" &&
						support.game_manifest.schema_version !==
							"classroom-action-support-v1" && (
							<AdaptiveSupportActivity
								manifest={support.game_manifest}
								onProgress={(actions, complete) => {
									setSupportActions(actions);
									setSupportComplete(complete);
								}}
							/>
						)}
					<button
						type="button"
						className="primary-action"
						disabled={busy || !supportComplete}
						onClick={() => void finishSupport()}
					>
						උදව්ව අවසන් කරන්න
					</button>
				</div>
			)}
			{step === "withdrawing" && (
				<div className="adventure-result" role="status">
					<h2>උදව් සම්පූර්ණයෙන් ඉවත් කරමින්…</h2>
				</div>
			)}
			{step === "result" && (
				<div
					className={`adventure-result${answeredCorrectly ? " is-success" : ""}`}
					data-answer-result={answeredCorrectly ? "correct" : "incorrect"}
				>
					<ChallengeProgress
						index={activeChallengeIndex}
						count={skills.length}
					/>
					{answeredCorrectly && isLastChallenge && <SuccessCelebration />}
					<h2>
						{answeredCorrectly
							? isLastChallenge
								? `${MULTIPLICATION_CHAPTERS[activeChapterIndex]?.title} සම්පූර්ණයි!`
								: `අභියෝගය ${activeChallengeIndex + 1} සම්පූර්ණයි!`
							: message}
					</h2>
					<button
						type="button"
						className="primary-action"
						onClick={
							answeredCorrectly
								? advance
								: () => activeSkillId && void openSkill(activeSkillId)
						}
					>
						{answeredCorrectly
							? isLastChallenge
								? "ක්‍රීඩා තේරීමට"
								: "ඊළඟ අභියෝගය"
							: "නැවත උත්සාහ කරන්න"}
					</button>
				</div>
			)}
		</section>
	);
}

function ChallengeProgress({ index, count }: { index: number; count: number }) {
	return (
		<ol
			className="multiplication-progress"
			data-progress-count={count}
			aria-label={`අභියෝග ${count}ක්`}
		>
			{["අභියෝග 1", "අභියෝග 2", "අභියෝග 3"].slice(0, count).map((label, item) => (
				<li
					key={label}
					className={
						item < index ? "is-done" : item === index ? "is-current" : undefined
					}
					aria-current={item === index ? "step" : undefined}
				>
					{item + 1}
				</li>
			))}
		</ol>
	);
}

export function MultiplicationMechanic({
	game,
	onChange,
}: {
	game: Record<string, unknown>;
	onChange(response: ConstructedResponse | null, entries: number): void;
}) {
	const kind = String(game.response_kind ?? "");
	const [product, setProduct] = useState("");
	const [digits, setDigits] = useState<string[]>([]);
	const [size, setSize] = useState("");
	const [count, setCount] = useState("");
	const factors = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];
	if (kind === "multiplication_fact") {
		const multiplicand = Number(game.multiplicand);
		const multiplier = Number(game.multiplier);
		return (
			<div className="multiplication-table-board" data-kind="fact">
				<p>
					{multiplicand} × {multiplier}
				</p>
				<section className="table-scroll" aria-label="1 සිට 12 දක්වා ගුණන වගුව">
					<table>
						<caption className="sr-only">ගුණන වගුව</caption>
						<thead>
							<tr>
								<th scope="col">×</th>
								{factors.map((factor) => (
									<th
										key={factor}
										scope="col"
										className={factor === multiplier ? "is-active" : undefined}
									>
										{factor}
									</th>
								))}
							</tr>
						</thead>
						<tbody>
							{factors.map((row) => (
								<tr
									key={row}
									className={row === multiplicand ? "is-active" : undefined}
								>
									<th scope="row">{row}</th>
									{factors.map((column) => {
										const selected =
											row === multiplicand && column === multiplier;
										return (
											<td key={`${row}-${column}`}>
												{selected ? "" : row * column}
											</td>
										);
									})}
								</tr>
							))}
						</tbody>
					</table>
				</section>
				<label>
					<span className="sr-only">හමුවන කොටුවේ ගුණිතය ඇතුළත් කරන්න</span>
					<input
						className="touch-target product-input"
						inputMode="numeric"
						aria-label="හමුවන කොටුවේ ගුණිතය ඇතුළත් කරන්න"
						value={product}
						onChange={(event) => {
							const value = event.target.value.replace(/\D/g, "").slice(0, 3);
							setProduct(value);
							onChange(
								value
									? {
											kind: "multiplication_fact",
											multiplicand,
											multiplier,
											product: Number(value),
										}
									: null,
								1,
							);
						}}
					/>
				</label>
			</div>
		);
	}
	if (kind === "written_multiplication") {
		const multiplicand = Number(game.multiplicand);
		const multiplier = Number(game.multiplier);
		const labels = (game.place_labels_si as string[] | undefined) ?? [];
		const width = Number(game.blank_count ?? labels.length);
		const top = String(multiplicand).padStart(width, " ");
		return (
			<div
				className="written-multiplication"
				data-kind="written"
				data-multiplier={multiplier}
			>
				<table className="multiplication-columns">
					<caption>තීරු ගුණන පුවරුව</caption>
					<thead>
						<tr>
							{labels.map((label) => (
								<th key={label} scope="col">
									{label}
								</th>
							))}
						</tr>
					</thead>
					<tbody>
						<tr>
							{top.split("").map((digit, index) => (
								<td key={labels[index] ?? index}>{digit.trim()}</td>
							))}
						</tr>
						<tr>
							{labels.map((label, index) => (
								<td key={label}>
									{index === labels.length - 1 ? `× ${multiplier}` : ""}
								</td>
							))}
						</tr>
						<tr className="result-digits">
							{labels.map((label, index) => (
								<td key={label}>
									<input
										className="touch-target result-digit"
										inputMode="numeric"
										aria-label={`${label} තැනේ පිළිතුරු ඉලක්කම ඇතුළත් කරන්න`}
										value={digits[index] ?? ""}
										onChange={(event) => {
											const value = event.target.value
												.replace(/\D/g, "")
												.slice(0, 1);
											const next = Array.from(
												{ length: width },
												(_, digitIndex) =>
													digitIndex === index
														? value
														: (digits[digitIndex] ?? ""),
											);
											setDigits(next);
											if (next.every((digit) => digit !== "")) {
												const resultDigits = next.map(Number);
												onChange(
													{
														kind: "written_multiplication",
														multiplicand,
														multiplier,
														result_digits: resultDigits,
														product: Number(resultDigits.join("")),
													},
													1,
												);
											} else onChange(null, 1);
										}}
									/>
								</td>
							))}
						</tr>
					</tbody>
				</table>
			</div>
		);
	}
	const groupSize = Number(game.group_size);
	const groupCount = Number(game.group_count);
	const emit = (nextSize: string, nextCount: string, nextProduct: string) => {
		if (nextSize && nextCount && nextProduct) {
			onChange(
				{
					kind: "multiplication_story",
					group_size: Number(nextSize),
					group_count: Number(nextCount),
					product: Number(nextProduct),
				},
				1,
			);
		} else onChange(null, 1);
	};
	return (
		<div className="multiplication-story" data-kind="story">
			<img src={String(game.asset ?? "")} alt="" />
			<p>{String(game.label_si ?? "")}</p>
			<ul className="equal-groups" aria-label="සමාන කණ්ඩායම්">
				{Array.from(
					{ length: groupCount },
					(_, group) => `group-${group + 1}`,
				).map((groupId) => (
					<li key={groupId}>
						{Array.from(
							{ length: groupSize },
							(_, item) => `${groupId}-item-${item + 1}`,
						).map((itemId) => (
							<span key={itemId} aria-hidden="true" />
						))}
					</li>
				))}
			</ul>
			<fieldset className="story-expression">
				<legend>ගුණන වාක්‍යය සාදන්න</legend>
				<input
					className="touch-target"
					inputMode="numeric"
					aria-label="කණ්ඩායමේ ප්‍රමාණය"
					value={size}
					onChange={(event) => {
						const value = event.target.value.replace(/\D/g, "").slice(0, 2);
						setSize(value);
						emit(value, count, product);
					}}
				/>
				<span aria-hidden="true">×</span>
				<input
					className="touch-target"
					inputMode="numeric"
					aria-label="කණ්ඩායම් ගණන"
					value={count}
					onChange={(event) => {
						const value = event.target.value.replace(/\D/g, "").slice(0, 2);
						setCount(value);
						emit(size, value, product);
					}}
				/>
				<span aria-hidden="true">=</span>
				<input
					className="touch-target product-input"
					inputMode="numeric"
					aria-label="කතාවේ ගුණිතය ඇතුළත් කරන්න"
					value={product}
					onChange={(event) => {
						const value = event.target.value.replace(/\D/g, "").slice(0, 4);
						setProduct(value);
						emit(size, count, value);
					}}
				/>
			</fieldset>
		</div>
	);
}
