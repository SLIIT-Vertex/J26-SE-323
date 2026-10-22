// biome-ignore-all lint/a11y/useButtonType: this application contains no HTML forms; all buttons are application actions.

import { useState } from "react";
import { AppIcon } from "./common";

export type ProgressRange = "week" | "month";

export const progressSubjects = [
	{
		id: "math",
		title: "ගණිතය",
		note: "ඉතා හොඳින් ඉදිරියට යනවා",
		percent: 72,
		xp: 34,
		tone: "purple",
		symbol: "123",
		skills: [
			{ title: "බාග", percent: 82 },
			{ title: "එකතු කිරීම", percent: 76 },
			{ title: "හැඩතල", percent: 58 },
		],
	},
	{
		id: "sinhala",
		title: "සිංහල",
		note: "අද තවත් කුඩා පියවරක්",
		percent: 61,
		xp: 21,
		tone: "pink",
		symbol: "අ",
		skills: [
			{ title: "කියවීම", percent: 70 },
			{ title: "වචන", percent: 63 },
			{ title: "ව්‍යාකරණ", percent: 48 },
		],
	},
	{
		id: "environment",
		title: "පරිසරය",
		note: "තවත් පුහුණුවෙන් දියුණු වෙමු",
		percent: 48,
		xp: 13,
		tone: "teal",
		symbol: "✿",
		skills: [
			{ title: "අප වටා ලෝකය", percent: 60 },
			{ title: "සත්ව ලෝකය", percent: 46 },
			{ title: "පරිසර ආරක්ෂාව", percent: 38 },
		],
	},
	{
		id: "english",
		title: "ඉංග්‍රීසි",
		note: "අලුත් වචන සමඟ නැවත උත්සාහ කරමු",
		percent: 35,
		xp: 8,
		tone: "orange",
		symbol: "Aa",
		skills: [
			{ title: "Classroom words", percent: 51 },
			{ title: "Listening", percent: 34 },
			{ title: "Simple sentences", percent: 22 },
		],
	},
] as const;

export function ProgressScreen({
	onLearn,
	onPractice,
}: {
	onLearn(): void;
	onPractice(): void;
}) {
	const [range, setRange] = useState<ProgressRange>("week");
	const [selectedDay, setSelectedDay] = useState(5);
	const [openSubject, setOpenSubject] = useState<string | null>("math");
	const activity =
		range === "week"
			? [
					{ label: "ස", value: 34, xp: 8 },
					{ label: "අ", value: 58, xp: 14 },
					{ label: "බ", value: 43, xp: 10 },
					{ label: "බ්‍ර", value: 72, xp: 18 },
					{ label: "සි", value: 50, xp: 12 },
					{ label: "සෙ", value: 88, xp: 22 },
					{ label: "ඉ", value: 62, xp: 16 },
				]
			: [
					{ label: "ස 1", value: 46, xp: 42 },
					{ label: "ස 2", value: 68, xp: 61 },
					{ label: "ස 3", value: 55, xp: 49 },
					{ label: "ස 4", value: 82, xp: 76 },
				];
	const overall = range === "week" ? 68 : 74;
	const totalXp = range === "week" ? 60 : 228;
	const activeIndex = Math.min(selectedDay, activity.length - 1);

	return (
		<section className="tab-screen progress-screen">
			<header className="progress-header">
				<div>
					<p className="eyebrow">මගේ ඉගෙනුම් ගමන</p>
					<h1>ප්‍රගතිය</h1>
				</div>
				<div className="progress-streak">
					<AppIcon name="fire" size={18} />
					<strong>3</strong>
					<small>දින</small>
				</div>
			</header>

			<fieldset className="progress-range">
				<legend className="sr-only">ප්‍රගති කාල පරාසය</legend>
				<button
					type="button"
					className={range === "week" ? "is-active" : ""}
					aria-pressed={range === "week"}
					onClick={() => {
						setRange("week");
						setSelectedDay(5);
					}}
				>
					මෙම සතිය
				</button>
				<button
					type="button"
					className={range === "month" ? "is-active" : ""}
					aria-pressed={range === "month"}
					onClick={() => {
						setRange("month");
						setSelectedDay(3);
					}}
				>
					මෙම මාසය
				</button>
			</fieldset>

			<article className="progress-overview-card">
				<div
					className="progress-ring"
					style={{
						background: `conic-gradient(#ffc542 ${overall}%, rgba(255,255,255,.2) 0)`,
					}}
				>
					<div>
						<strong>{overall}%</strong>
						<span>සම්පූර්ණයි</span>
					</div>
				</div>
				<div className="progress-overview-copy">
					<p className="eyebrow">සමස්ත දියුණුව</p>
					<h2>ඔබ හොඳින් ඉදිරියට යනවා!</h2>
					<p>
						මෙම {range === "week" ? "සතියේ" : "මාසයේ"} තවත් කුසලතා 3ක් ශක්තිමත් කර ඇත.
					</p>
				</div>
				<div className="progress-overview-stats">
					<span>
						<strong>{totalXp}</strong>
						<small>XP ලකුණු</small>
					</span>
					<span>
						<strong>9</strong>
						<small>ක්‍රියාකාරකම්</small>
					</span>
					<span>
						<strong>82%</strong>
						<small>හොඳම ලකුණ</small>
					</span>
				</div>
			</article>

			<article className="activity-card">
				<div className="progress-card-heading">
					<div>
						<p className="eyebrow">ක්‍රියාකාරීත්වය</p>
						<h2>{range === "week" ? "මෙම සතිය" : "පසුගිය සති 4"}</h2>
					</div>
					<span>{activity[activeIndex].xp} XP</span>
				</div>
				<figure
					className={`activity-chart activity-chart--${range}`}
					aria-label="ඉගෙනුම් ක්‍රියාකාරීත්ව සටහන"
				>
					{activity.map((day, index) => (
						<button
							type="button"
							key={`${range}-${day.label}`}
							className={index === activeIndex ? "is-active" : ""}
							aria-label={`${day.label}: XP ${day.xp}`}
							aria-pressed={index === activeIndex}
							onClick={() => setSelectedDay(index)}
						>
							<i style={{ height: `${day.value}%` }}>
								<span>{day.xp}</span>
							</i>
							<small>{day.label}</small>
						</button>
					))}
				</figure>
			</article>

			<div className="section-heading progress-section-heading">
				<div>
					<p className="eyebrow">විෂය අනුව</p>
					<h2>කුසලතා දියුණුව</h2>
				</div>
				<small>විවෘත කිරීමට තට්ටු කරන්න</small>
			</div>
			<div className="progress-subjects">
				{progressSubjects.map((subject) => {
					const open = openSubject === subject.id;
					return (
						<article
							className={`progress-subject-card progress-subject-card--${subject.tone}${open ? " is-open" : ""}`}
							key={subject.id}
						>
							<button
								type="button"
								className="progress-subject-summary"
								aria-expanded={open}
								onClick={() => setOpenSubject(open ? null : subject.id)}
							>
								<span className="progress-subject-icon">{subject.symbol}</span>
								<span className="progress-subject-copy">
									<strong>{subject.title}</strong>
									<small>{subject.note}</small>
									<i>
										<b style={{ width: `${subject.percent}%` }} />
									</i>
								</span>
								<span className="progress-subject-score">
									<strong>{subject.percent}%</strong>
									<small>+{subject.xp} XP</small>
									<b aria-hidden="true">⌄</b>
								</span>
							</button>
							{open && (
								<div className="progress-skill-details">
									{subject.skills.map((skill) => (
										<div key={skill.title}>
											<span>
												<strong>{skill.title}</strong>
												<small>{skill.percent}%</small>
											</span>
											<i>
												<b style={{ width: `${skill.percent}%` }} />
											</i>
										</div>
									))}
									<button type="button" onClick={onLearn}>
										මෙම විෂය පුහුණු වන්න <AppIcon name="arrow" size={17} />
									</button>
								</div>
							)}
						</article>
					);
				})}
			</div>

			<button className="progress-insight" type="button" onClick={onPractice}>
				<span>
					<AppIcon name="sparkle" size={24} />
				</span>
				<span>
					<small>Mindyගේ යෝජනාව</small>
					<strong>බාග සහ හැඩතල සඳහා කෙටි පුහුණුවක් කරමු.</strong>
				</span>
				<b aria-hidden="true">›</b>
			</button>
		</section>
	);
}
