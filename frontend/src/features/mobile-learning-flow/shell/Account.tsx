// biome-ignore-all lint/a11y/useButtonType: this application contains no HTML forms; all buttons are application actions.

import { useState } from "react";
import { AppIcon, type AvatarTone, BrandMark, LearnerAvatar } from "./common";

export function Account({
	name,
	onNameChange,
	avatarTone,
	onAvatarToneChange,
	onBack,
	onRewards,
	onSettings,
	onOnboarding,
}: {
	name: string;
	onNameChange(value: string): void;
	avatarTone: AvatarTone;
	onAvatarToneChange(value: AvatarTone): void;
	onBack(): void;
	onRewards(): void;
	onSettings(): void;
	onOnboarding(): void;
}) {
	const [editing, setEditing] = useState(false);
	const [draftName, setDraftName] = useState(name);
	const [draftTone, setDraftTone] = useState<AvatarTone>(avatarTone);
	const [parentNoteOpen, setParentNoteOpen] = useState(false);
	const avatarChoices: Array<{ tone: AvatarTone; label: string }> = [
		{ tone: "violet", label: "දම්" },
		{ tone: "sky", label: "නිල්" },
		{ tone: "teal", label: "කොළ" },
		{ tone: "orange", label: "තැඹිලි" },
	];
	const openEditor = () => {
		setDraftName(name);
		setDraftTone(avatarTone);
		setEditing(true);
	};
	return (
		<section className="tab-screen account-screen">
			<header className="profile-topbar">
				<button
					className="icon-button"
					type="button"
					aria-label="මුල් පිටුවට ආපසු"
					onClick={onBack}
				>
					<AppIcon name="back" size={20} />
				</button>
				<div>
					<p className="eyebrow">MindBridge</p>
					<h1>මගේ පැතිකඩ</h1>
				</div>
				<button
					className="icon-button"
					type="button"
					aria-label="යෙදුම් සැකසුම්"
					onClick={onSettings}
				>
					<AppIcon name="settings" size={20} />
				</button>
			</header>
			<div className="profile-hero">
				<button
					className="profile-avatar-button"
					type="button"
					aria-label="පැතිකඩ සංස්කරණය කරන්න"
					onClick={openEditor}
				>
					<LearnerAvatar tone={avatarTone} />
					<span aria-hidden="true">✎</span>
				</button>
				<div className="profile-hero-copy">
					<p className="eyebrow">පුංචි ගවේෂකයා</p>
					<h1>{name}</h1>
					<p>5 ශ්‍රේණිය · සිංහල</p>
				</div>
				<button
					className="profile-edit-button"
					type="button"
					onClick={openEditor}
				>
					වෙනස් කරන්න
				</button>
			</div>

			{editing && (
				<section
					className="profile-edit-panel"
					aria-labelledby="profile-edit-title"
				>
					<div className="profile-edit-heading">
						<div>
							<p className="eyebrow">පුද්ගලීකරණය</p>
							<h2 id="profile-edit-title">ඔබේ පැතිකඩ වෙනස් කරන්න</h2>
						</div>
						<button
							type="button"
							aria-label="සංස්කරණය වසන්න"
							onClick={() => setEditing(false)}
						>
							×
						</button>
					</div>
					<label className="field-card">
						<span>ඔබේ නම</span>
						<input
							value={draftName}
							maxLength={24}
							onChange={(event) => setDraftName(event.target.value)}
						/>
					</label>
					<fieldset className="avatar-tone-field">
						<legend>අවතාර වර්ණය</legend>
						<div>
							{avatarChoices.map((choice) => (
								<button
									className={`avatar-tone avatar-tone--${choice.tone}`}
									type="button"
									key={choice.tone}
									aria-label={`${choice.label} වර්ණය`}
									aria-pressed={draftTone === choice.tone}
									onClick={() => setDraftTone(choice.tone)}
								>
									{draftTone === choice.tone && <span>✓</span>}
								</button>
							))}
						</div>
					</fieldset>
					<div className="profile-edit-actions">
						<button
							className="text-action"
							type="button"
							onClick={() => setEditing(false)}
						>
							අවලංගු කරන්න
						</button>
						<button
							className="primary-action"
							type="button"
							disabled={!draftName.trim()}
							onClick={() => {
								onNameChange(draftName.trim());
								onAvatarToneChange(draftTone);
								setEditing(false);
							}}
						>
							වෙනස්කම් සුරකින්න
						</button>
					</div>
				</section>
			)}
			<div className="profile-stats">
				<div>
					<strong>2</strong>
					<span>මට්ටම</span>
				</div>
				<div>
					<strong>60</strong>
					<span>මුළු XP</span>
				</div>
				<button
					type="button"
					onClick={onRewards}
					aria-label="ලාංඡන 2ක් — ත්‍යාග බලන්න"
				>
					<strong>2</strong>
					<span>ලාංඡන ›</span>
				</button>
			</div>
			<h2 className="list-title">පැතිකඩ සහ යෙදුම</h2>
			<div className="settings-list">
				<button onClick={onSettings}>
					<span className="settings-icon">
						<AppIcon name="settings" size={21} />
					</span>
					<span>
						<strong>යෙදුම් සැකසුම්</strong>
						<small>ප්‍රවේශතාව සහ සමමුහුර්ත කිරීම</small>
					</span>
					<b>›</b>
				</button>
				<button onClick={onOnboarding}>
					<span className="settings-icon settings-icon--orange">
						<AppIcon name="sparkle" size={21} />
					</span>
					<span>
						<strong>හැඳින්වීම නැවත බලන්න</strong>
						<small>MindBridge භාවිත කරන ආකාරය</small>
					</span>
					<b>›</b>
				</button>
				<button
					type="button"
					onClick={() => setParentNoteOpen((open) => !open)}
					aria-expanded={parentNoteOpen}
				>
					<span className="settings-icon settings-icon--teal">
						<AppIcon name="shield" size={21} />
					</span>
					<span>
						<strong>දෙමාපිය ප්‍රදේශය</strong>
						<small>වැඩිහිටි අවසරය අවශ්‍යයි</small>
					</span>
					<b>›</b>
				</button>
			</div>
			{parentNoteOpen && (
				<div className="parent-note" role="status">
					<AppIcon name="shield" size={21} />
					<p>
						<strong>වැඩිහිටියෙකු සමඟ විවෘත කරන්න.</strong> කැමරා අවසර සහ ප්‍රවේශතා පාලන
						යෙදුම් සැකසුම් තුළ ඇත.
					</p>
					<button className="text-action" type="button" onClick={onSettings}>
						සැකසුම් බලන්න
					</button>
				</div>
			)}
			<div className="profile-brand">
				<BrandMark variant="submark" />
				<span>MindBridge</span>
				<small>Learn · Play · Grow</small>
			</div>
		</section>
	);
}
