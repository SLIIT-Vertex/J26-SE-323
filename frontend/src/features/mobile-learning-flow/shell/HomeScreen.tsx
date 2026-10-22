// biome-ignore-all lint/a11y/useButtonType: this application contains no HTML forms; all buttons are application actions.

import { useState } from "react";
import { ENGLISH_LEARNING_AREAS, learningAreaName } from "../learningAreas";
import { AppIcon, type AvatarTone, LearnerAvatar } from "./common";

export const FEATURED_GAMES = [
	...Array.from({ length: 16 }, (_, index) => {
		const areaId = `G5-AREA-MAT-${String(index + 1).padStart(2, "0")}`;
		return { areaId, title: learningAreaName(areaId), subject: "ගණිතය" };
	}),
	...ENGLISH_LEARNING_AREAS.map((area) => ({ ...area, subject: "ඉංග්‍රීසි" })),
];

export function HomeScreen({
	name,
	avatarTone,
	onProfile,
	onMission,
	onLearn,
	onPractice,
	onMindy,
	onProgress,
	onRewards,
}: {
	name: string;
	avatarTone: AvatarTone;
	onProfile(): void;
	onMission(areaId: string): void;
	onLearn(): void;
	onPractice(): void;
	onMindy(): void;
	onProgress(): void;
	onRewards(): void;
}) {
	const [featuredGame] = useState(
		() => FEATURED_GAMES[Math.floor(Math.random() * FEATURED_GAMES.length)],
	);
	const [notificationsOpen, setNotificationsOpen] = useState(false);
	const [hasUnread, setHasUnread] = useState(true);
	return (
		<section className="tab-screen home-screen">
			<header className="home-header">
				<button
					className="home-identity"
					type="button"
					aria-label={`${name}ගේ පැතිකඩ බලන්න`}
					onClick={onProfile}
				>
					<LearnerAvatar tone={avatarTone} />
					<span>
						<p>සුබ දවසක්!</p>
						<h1>{name} 👋</h1>
					</span>
				</button>
				<button
					className="notification-button"
					type="button"
					aria-label={hasUnread ? "නව දැනුම්දීම් 1ක්" : "දැනුම්දීම්"}
					aria-expanded={notificationsOpen}
					onClick={() => setNotificationsOpen((open) => !open)}
				>
					<AppIcon name="bell" size={21} />
					{hasUnread && <span aria-hidden="true" />}
				</button>
			</header>

			{notificationsOpen && (
				<aside className="home-notification-panel" aria-label="දැනුම්දීම්">
					<span className="notification-symbol" aria-hidden="true">
						★
					</span>
					<div>
						<strong>අද මෙහෙයුම සූදානම්!</strong>
						<p>
							{featuredGame.title} — {featuredGame.subject} ක්‍රීඩාවක් ඔබ බලා සිටී.
						</p>
					</div>
					<button
						type="button"
						aria-label="දැනුම්දීම කියවූ ලෙස සලකුණු කරන්න"
						onClick={() => {
							setHasUnread(false);
							setNotificationsOpen(false);
						}}
					>
						✓
					</button>
				</aside>
			)}

			<ul className="stats" aria-label="අද ප්‍රගතිය">
				<li>
					<span className="stat-icon stat-icon--fire">
						<AppIcon name="fire" size={18} />
					</span>
					<strong>දින 3</strong>
					<small>අඛණ්ඩ මාලාව</small>
				</li>
				<li>
					<span className="stat-icon stat-icon--star">
						<AppIcon name="trophy" size={18} />
					</span>
					<strong>60 XP</strong>
					<small>මුළු ලකුණු</small>
				</li>
				<li>
					<span className="stat-icon stat-icon--coin">●</span>
					<strong>28</strong>
					<small>කාසි</small>
				</li>
			</ul>

			<article className="mission-card home-mission-card">
				<img
					className="home-mission-art"
					src="/curriculum/game/shared/child-celebrating-stars.png"
					alt=""
					aria-hidden="true"
				/>
				<p className="eyebrow">
					<AppIcon name="target" size={16} /> අද මෙහෙයුම
				</p>
				<h2>{featuredGame.title}</h2>
				<p>ක්‍රීඩාවක් සමඟ අද අලුත් දෙයක් ඉගෙන ගනිමු.</p>
				<button
					className="primary-action"
					type="button"
					onClick={() => onMission(featuredGame.areaId)}
					data-area-id={featuredGame.areaId}
				>
					අභියෝගය අරඹමු <AppIcon name="arrow" size={18} />
				</button>
			</article>

			<button
				className="recommendation-card"
				type="button"
				onClick={onPractice}
			>
				<span className="recommendation-icon">
					<AppIcon name="document" size={23} />
				</span>
				<span>
					<small>ඔබට නිර්දේශිතයි</small>
					<strong>පසුගිය ප්‍රශ්න පත්‍ර පුහුණුව</strong>
					<em>කෙටි ප්‍රශ්න 5ක් · මිනිත්තු 8යි</em>
				</span>
				<b aria-hidden="true">›</b>
			</button>

			<button className="smart-support-card" type="button" onClick={onMindy}>
				<span>
					<AppIcon name="sparkle" size={23} />
				</span>
				<span>
					<strong>Mindyගෙන් උදව්වක් ඕනෑ ද?</strong>
					<small>පිළිතුර නොකියා ඔබටම සොයා ගන්නට කුඩා ඉඟියක්</small>
				</span>
				<b aria-hidden="true">›</b>
			</button>

			<div className="section-heading home-section-heading">
				<div>
					<p className="eyebrow">ඉක්මන් පිවිසුම්</p>
					<h2>දැන් මොනවා කරමු ද?</h2>
				</div>
			</div>
			<div className="feature-grid">
				<button type="button" onClick={onLearn}>
					<span className="feature-icon feature-icon--purple">
						<AppIcon name="game" size={24} />
					</span>
					<strong>ක්‍රීඩා කරමින් ඉගෙන ගන්න</strong>
					<small>විෂයක් තෝරා අලුත් අභියෝගයක් අරඹන්න.</small>
				</button>
				<button type="button" onClick={onProgress}>
					<span className="feature-icon feature-icon--sky">
						<AppIcon name="chart" size={24} />
					</span>
					<strong>මගේ ප්‍රගතිය බලන්න</strong>
					<small>ඔබ දියුණු වූ කුසලතා එකම තැනකින් බලන්න.</small>
				</button>
				<button type="button" onClick={onRewards}>
					<span className="feature-icon feature-icon--orange">
						<AppIcon name="trophy" size={24} />
					</span>
					<strong>ත්‍යාග සහ ලාංඡන</strong>
					<small>ඔබ දිනාගත් ලාංඡන සහ මාලාව පරීක්ෂා කරන්න.</small>
				</button>
				<button type="button" onClick={onProfile}>
					<span className="feature-icon feature-icon--teal">
						<AppIcon name="user" size={24} />
					</span>
					<strong>මගේ පැතිකඩ</strong>
					<small>නම, අවතාරය සහ යෙදුම් සැකසුම් වෙනස් කරන්න.</small>
				</button>
			</div>
		</section>
	);
}
