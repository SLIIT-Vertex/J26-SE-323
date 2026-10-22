// biome-ignore-all lint/a11y/useButtonType: this application contains no HTML forms; all buttons are application actions.

import type { CSSProperties } from "react";
import type { DraftMissionRecord, DraftTemplateId } from "../api/generated";
import { ENGLISH_LEARNING_AREAS, learningAreaName } from "../learningAreas";
import { AppIcon } from "./common";

export type SubjectCode = "MAT" | "SIN" | "ENV" | "ENG";

export type GameSubject = {
	code: SubjectCode;
	title: string;
	image: string;
	tone: "math" | "sinhala" | "env" | "english";
	bannerColors: { start: string; end: string; accent: string };
};

export const GAME_SUBJECTS: GameSubject[] = [
	{
		code: "MAT",
		title: "ගණිතය",
		image: "/curriculum/math.svg",
		tone: "math",
		bannerColors: { start: "#eff8ff", end: "#dceeff", accent: "#c1def6" },
	},
	{
		code: "SIN",
		title: "සිංහල",
		image: "/curriculum/sinhala.svg",
		tone: "sinhala",
		bannerColors: { start: "#f7f2ff", end: "#e9e0fb", accent: "#d6c5f2" },
	},
	{
		code: "ENV",
		title: "පරිසර අධ්‍යයනය",
		image: "/curriculum/environmental-studies.svg",
		tone: "env",
		bannerColors: { start: "#effaf5", end: "#daf1e7", accent: "#b9e2d4" },
	},
	{
		code: "ENG",
		title: "ඉංග්‍රීසි",
		image: "/curriculum/english.svg",
		tone: "english",
		bannerColors: { start: "#fff3f8", end: "#fbe1ee", accent: "#f2c6dc" },
	},
];

export function SubjectPageHeader({
	subject,
	onBack,
}: {
	subject: GameSubject;
	onBack(): void;
}) {
	const bannerStyle = {
		"--subject-banner-start": subject.bannerColors.start,
		"--subject-banner-end": subject.bannerColors.end,
		"--subject-banner-accent": subject.bannerColors.accent,
	} as CSSProperties;

	return (
		<header className="subject-page-header" lang="si">
			<div className="subject-page-header__navigation">
				<button
					className="back-button"
					type="button"
					aria-label="ආපසු"
					onClick={onBack}
				>
					<AppIcon name="back" size={21} />
				</button>
				<span>විෂයයන්</span>
			</div>
			<div className="subject-page-header__banner" style={bannerStyle}>
				<div className="subject-page-header__copy">
					<h1>{subject.title}</h1>
					<p>අදත් අලුත් දෙයක් ඉගෙන ගනිමු!</p>
				</div>
				<img src={subject.image} alt="" aria-hidden="true" />
			</div>
		</header>
	);
}

// Sinhala areas with a dedicated durable game. They are playable without the researcher-only
// draft-mission catalogue, the way the English games are.
export const DEDICATED_SINHALA_AREAS = {
	"G5-AREA-SIN-01": "pillam_journey",
	"G5-AREA-SIN-02": "punctuation_journey",
	"G5-AREA-SIN-03": "riddle_journey",
} as const satisfies Record<string, DraftTemplateId>;

export function missionsForSubject(
	subject: SubjectCode,
	missions: DraftMissionRecord[],
) {
	const listed = missions.filter((mission) =>
		mission.area_id.includes(`-${subject}-`),
	);
	const dedicated: DraftMissionRecord[] =
		subject === "SIN"
			? Object.entries(DEDICATED_SINHALA_AREAS)
					.filter(
						([areaId]) => !listed.some((mission) => mission.area_id === areaId),
					)
					.map(([areaId, templateId]) => ({
						area_id: areaId,
						cited_node_id: "",
						template_id: templateId,
						outcome_slots: [],
						draft_item_slots: [],
						held_slots: [],
					}))
			: [];
	return [...listed, ...dedicated].sort((left, right) =>
		left.area_id.localeCompare(right.area_id),
	);
}

export function GamesHome({
	missions = [],
	catalogStatus = "idle",
	onChoose,
	openSubject = null,
	onOpenSubject,
}: {
	missions?: DraftMissionRecord[];
	catalogStatus?: "idle" | "loading" | "ready" | "error";
	onChoose?(areaId: string): void;
	openSubject?: SubjectCode | null;
	onOpenSubject?(subject: SubjectCode | null): void;
}) {
	const subject = GAME_SUBJECTS.find((item) => item.code === openSubject);
	const subjectMissions = subject
		? missionsForSubject(subject.code, missions)
		: [];
	const englishAreas = subject?.code === "ENG" ? ENGLISH_LEARNING_AREAS : [];
	return (
		<section className="tab-screen games-screen">
			{subject ? (
				<section className="learning-areas" data-subject-areas={subject.code}>
					<SubjectPageHeader
						subject={subject}
						onBack={() => onOpenSubject?.(null)}
					/>
					{subjectMissions.length > 0 ? (
						<ul>
							{subjectMissions.map((mission) => (
								<li key={mission.area_id}>
									<button
										className="mission-choice"
										data-area-id={mission.area_id}
										onClick={() => onChoose?.(mission.area_id)}
									>
										{learningAreaName(mission.area_id)}
									</button>
								</li>
							))}
						</ul>
					) : englishAreas.length > 0 ? (
						<ul>
							{englishAreas.map((area) => (
								<li key={area.areaId}>
									<button
										className="mission-choice"
										data-area-id={area.areaId}
										type="button"
										onClick={() => onChoose?.(area.areaId)}
									>
										{area.title}
									</button>
								</li>
							))}
						</ul>
					) : (
						<p className="quiet">මෙම විෂය සඳහා ඉගෙනුම් ක්ෂේත්‍ර තවම නොමැත.</p>
					)}
				</section>
			) : (
				<>
					<header className="games-hero">
						<div className="games-title">
							<span>ක්‍රීඩා කරමින්</span>
							<span className="games-title-last">ඉගෙන ගමු!</span>
						</div>
					</header>
					<div className="subject-cards">
						{GAME_SUBJECTS.map((item) => {
							const count =
								item.code === "ENG"
									? ENGLISH_LEARNING_AREAS.length
									: missionsForSubject(item.code, missions).length;
							return (
								<button
									className={`subject-card subject-card--${item.tone}`}
									data-subject={item.code}
									key={item.code}
									onClick={() => onOpenSubject?.(item.code)}
								>
									<span className="subject-badge">
										<img src={item.image} alt="" aria-hidden="true" />
									</span>
									<span className="subject-copy">
										<strong>{item.title}</strong>
										{count > 0 && <em>{count} ඉගෙනුම් ක්ෂේත්‍ර</em>}
									</span>
									<span className="subject-start" aria-hidden="true">
										<AppIcon name="arrow" size={18} />
									</span>
								</button>
							);
						})}
					</div>
					{catalogStatus === "error" && (
						<p role="status">
							සිංහල සහ පරිසර අධ්‍යයන මෙහෙයුම් ලබා ගත නොහැක. API සේවාව ක්‍රියාත්මක නොවේ.
						</p>
					)}
				</>
			)}
		</section>
	);
}
