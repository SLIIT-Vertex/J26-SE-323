// biome-ignore-all lint/a11y/useButtonType: this application contains no HTML forms; all buttons are application actions.

import { Back } from "./common";

export function RewardsHub({ onBack }: { onBack(): void }) {
	const achievements = [
		{
			icon: "★",
			title: "පළමු පියවර",
			note: "පළමු මෙහෙයුම",
			tone: "violet",
			earned: true,
		},
		{
			icon: "🔥",
			title: "දින 3 මාලාව",
			note: "දින තුනක් අඛණ්ඩව",
			tone: "orange",
			earned: true,
		},
		{
			icon: "½",
			title: "බාග වීරයා",
			note: "බාග 5ක් නිවැරදිව",
			tone: "teal",
			earned: false,
		},
		{
			icon: "◇",
			title: "කුතුහලය",
			note: "පාඩම් 10ක් උත්සාහ කරන්න",
			tone: "sky",
			earned: false,
		},
	];
	return (
		<section className="tab-screen rewards-screen">
			<Back onClick={onBack} />
			<div className="page-title-row">
				<div>
					<p className="eyebrow">මගේ එකතුව</p>
					<h1>ත්‍යාග</h1>
				</div>
				<div className="coin-balance">
					● <strong>28</strong>
				</div>
			</div>
			<article className="level-card">
				<div className="level-medal">
					<span>2</span>
				</div>
				<div>
					<small>දැනට මට්ටම</small>
					<h2>පුංචි ගවේෂකයා</h2>
					<p>මට්ටම 3 දක්වා තවත් XP 40යි</p>
				</div>
				<div
					className="level-progress"
					role="progressbar"
					aria-label="මට්ටමේ ප්‍රගතිය"
					aria-valuemin={0}
					aria-valuemax={100}
					aria-valuenow={60}
				>
					<span style={{ width: "60%" }} />
				</div>
			</article>
			<div className="section-heading">
				<div>
					<p className="eyebrow">ලාංඡන</p>
					<h2>ඔබගේ ජයග්‍රහණ</h2>
				</div>
				<span className="earned-count">2 / 4</span>
			</div>
			<div className="achievement-grid">
				{achievements.map((achievement) => (
					<article
						className={`achievement-card achievement-card--${achievement.tone}${achievement.earned ? "" : " achievement-card--locked"}`}
						key={achievement.title}
					>
						<div className="achievement-icon">
							{achievement.earned ? achievement.icon : "⌁"}
						</div>
						<h3>{achievement.title}</h3>
						<p>{achievement.note}</p>
					</article>
				))}
			</div>
			<article className="streak-card">
				<span className="streak-flame">🔥</span>
				<div>
					<small>මෙම සතියේ මාලාව</small>
					<h2>දින 3ක් අඛණ්ඩව!</h2>
					<div className="week-dots">
						{["ස", "අ", "බ", "බ්‍ර", "සි", "සෙ", "ඉ"].map((day, index) => (
							<span
								className={index < 3 ? "week-dot week-dot--done" : "week-dot"}
								key={day}
							>
								{index < 3 ? "✓" : day}
							</span>
						))}
					</div>
				</div>
			</article>
		</section>
	);
}
