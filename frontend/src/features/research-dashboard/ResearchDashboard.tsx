import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
	type AccuracyReport,
	createResearchClient,
	type GainSeries,
	type HistoryEntry,
	type HistoryModel,
	type LearnerProfile,
	type MisconceptionSeries,
	type Overview,
	type ResearchClient,
	type SupportSeries,
	type Trace,
} from "./api";
import { GainTab, MisconceptionTab, SupportTab } from "./model-tabs";
import {
	AccuracyPanel,
	EmptyStep,
	LivePanel,
	OverviewPanel,
	ProfilePanel,
} from "./panels";
import "./research-dashboard.css";

const HISTORY_TABS: Record<string, HistoryModel> = {
	model1: "misconception",
	model2: "support",
	model3: "gain",
};

const TABS = [
	["overview", "Overview"],
	["live", "Live game"],
	["model1", "Probabilistic Misconception"],
	["model2", "Contextual Support Selection"],
	["model3", "Independence Gain"],
	["profile", "Child profile"],
	["accuracy", "Parameter validation & accuracy"],
] as const;
type Tab = (typeof TABS)[number][0];

export function ResearchDashboard({
	learnerId,
	onClose,
	client: injected,
}: {
	learnerId: string;
	onClose(): void;
	client?: ResearchClient;
}) {
	const client = useMemo(() => injected ?? createResearchClient(), [injected]);
	const [tab, setTab] = useState<Tab>("overview");
	const body = useRef<HTMLDivElement>(null);
	const changeTab = (next: Tab) => {
		setTab(next);
		if (body.current) body.current.scrollTop = 0;
	};
	const [overview, setOverview] = useState<Overview | null>(null);
	const [live, setLive] = useState<{
		active: boolean;
		trace: Trace | null;
	} | null>(null);
	const [profile, setProfile] = useState<LearnerProfile | null>(null);
	const [accuracy, setAccuracy] = useState<AccuracyReport | null>(null);
	const [history, setHistory] = useState<
		Partial<Record<HistoryModel, HistoryEntry[]>>
	>({});
	const [series, setSeries] = useState<{
		misconception?: MisconceptionSeries;
		support?: SupportSeries;
		gain?: GainSeries;
	}>({});
	const [picked, setPickedState] = useState<string | null>(null);
	const pickedRef = useRef<string | null>(null);
	const pickedTraceRef = useRef<Trace | null>(null);
	const setPicked = useCallback((id: string | null) => {
		pickedRef.current = id;
		setPickedState(id);
	}, []);
	const [error, setError] = useState<string | null>(null);
	const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
	const dialog = useRef<HTMLDivElement>(null);
	const loadedLearner = useRef(learnerId);
	const refresh = useCallback(async () => {
		const [nextLive, nextOverview] = await Promise.all([
			client.live(learnerId),
			client.overview(learnerId),
		]);
		setLive(nextLive);
		setOverview(nextOverview);
		setUpdatedAt(new Date());
		if (tab === "profile") setProfile(await client.profile(learnerId));
		if (tab === "accuracy") setAccuracy(await client.accuracy(learnerId));
		const model = HISTORY_TABS[tab];
		if (model) {
			const [nextHistory, nextSeries] = await Promise.all([
				client.history(learnerId, model),
				client.series(learnerId, model),
			]);
			setHistory((current) => ({ ...current, [model]: nextHistory.sessions }));
			setSeries((current) => ({ ...current, [model]: nextSeries }));
			const chosen = nextHistory.sessions.find(
				(entry) => entry.episode_id === pickedRef.current,
			);
			if (chosen?.play_status === "live") {
				const traced = await client.trace(chosen.episode_id);
				pickedTraceRef.current = traced;
			}
		}
		setError(null);
	}, [client, learnerId, tab]);
	useEffect(() => {
		let stopped = false;
		let timer: ReturnType<typeof setTimeout>;
		const tick = async () => {
			if (!document.hidden) {
				try {
					await refresh();
				} catch {
					if (!stopped)
						setError(
							"This view could not be refreshed. Please try again shortly.",
						);
				}
			}
			if (!stopped) timer = setTimeout(tick, tab === "accuracy" ? 60000 : 1500);
		};
		void tick();
		return () => {
			stopped = true;
			clearTimeout(timer);
		};
	}, [refresh, tab]);
	useEffect(() => {
		if (loadedLearner.current === learnerId) return;
		loadedLearner.current = learnerId;
		setPicked(null);
		setHistory({});
		setSeries({});
		setProfile(null);
		setAccuracy(null);
	}, [learnerId, setPicked]);
	useEffect(() => {
		const previous = document.activeElement as HTMLElement | null;
		const oldOverflow = document.body.style.overflow;
		document.body.style.overflow = "hidden";
		dialog.current?.focus();
		const key = (event: KeyboardEvent) => {
			if (event.key === "Escape") onClose();
			if (event.key !== "Tab") return;
			const controls = [
				...(dialog.current?.querySelectorAll<HTMLElement>(
					"button, a, input, select, textarea, summary, [tabindex='0']",
				) ?? []),
			].filter((el) => el.getClientRects().length);
			const first = controls[0];
			const last = controls.at(-1);
			if (event.shiftKey && document.activeElement === first) {
				event.preventDefault();
				last?.focus();
			}
			if (!event.shiftKey && document.activeElement === last) {
				event.preventDefault();
				first?.focus();
			}
		};
		window.addEventListener("keydown", key);
		return () => {
			window.removeEventListener("keydown", key);
			document.body.style.overflow = oldOverflow;
			previous?.focus();
		};
	}, [onClose]);
	const openEpisode = (id: string) => {
		setPicked(id);
		changeTab("model2");
	};
	const name =
		profile?.name ??
		overview?.learner_name ??
		`Learner ${learnerId.slice(0, 4)}`;
	return (
		<div
			className="rd-overlay"
			role="dialog"
			aria-modal="true"
			aria-labelledby="rd-title"
			ref={dialog}
			tabIndex={-1}
		>
			<header className="rd-top">
				<div>
					<h2 id="rd-title">Learning research</h2>
					<p>
						{name}
						{updatedAt && <> · Updated {updatedAt.toLocaleTimeString()}</>}
					</p>
				</div>
				<button
					type="button"
					className="rd-close"
					aria-label="Close research dashboard"
					onClick={onClose}
				>
					✕
				</button>
			</header>
			<nav className="rd-tabs" aria-label="Dashboard sections">
				{TABS.map(([key, label]) => (
					<button
						key={key}
						type="button"
						aria-pressed={tab === key}
						className={tab === key ? "is-active" : undefined}
						onClick={() => changeTab(key)}
					>
						{label}
					</button>
				))}
			</nav>
			<label className="rd-mobile-nav">
				Dashboard section
				<select
					value={tab}
					onChange={(event) => changeTab(event.target.value as Tab)}
				>
					{TABS.map(([key, label]) => (
						<option key={key} value={key}>
							{label}
						</option>
					))}
				</select>
			</label>
			<div className="rd-body" ref={body}>
				{error && (
					<p className="rd-banner is-fail" role="alert">
						{error}
					</p>
				)}
				{tab === "overview" &&
					(overview ? (
						<OverviewPanel overview={overview} onOpenEpisode={openEpisode} />
					) : (
						<EmptyStep text="Loading games…" />
					))}
				{tab === "live" &&
					(live?.trace ? (
						<LivePanel trace={live.trace} />
					) : (
						<EmptyStep text="Start any game; it appears here within 2 seconds." />
					))}
				{tab === "model1" && (
					<MisconceptionTab
						series={series.misconception ?? null}
						history={history.misconception ?? []}
						selected={picked}
						onSelect={setPicked}
					/>
				)}
				{tab === "model2" && (
					<SupportTab
						series={series.support ?? null}
						history={history.support ?? []}
						selected={picked}
						onSelect={setPicked}
					/>
				)}
				{tab === "model3" && (
					<GainTab
						series={series.gain ?? null}
						history={history.gain ?? []}
						selected={picked}
						onSelect={setPicked}
					/>
				)}
				{tab === "profile" &&
					(profile ? (
						<ProfilePanel profile={profile} />
					) : (
						<EmptyStep text="Loading the child profile…" />
					))}
				{tab === "accuracy" &&
					(accuracy ? (
						<AccuracyPanel report={accuracy} />
					) : (
						<EmptyStep text="Checking the recorded games…" />
					))}
			</div>
		</div>
	);
}
