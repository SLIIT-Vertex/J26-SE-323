// biome-ignore-all lint/a11y/useButtonType: this application contains no HTML forms; all buttons are application actions.

import { useRef, useState } from "react";
import { AppIcon, type AvatarTone, BrandMark, LearnerAvatar } from "./common";

export function Splash({ onContinue }: { onContinue(): void }) {
	return (
		<section className="center-screen splash-screen">
			<div className="splash-orbit splash-orbit--one" />
			<div className="splash-orbit splash-orbit--two" />
			<BrandMark variant="primary" className="brand-mark--hero" />
			<h1>ඉගෙන ගමු. ක්‍රීඩා කරමු. දියුණු වෙමු.</h1>
			<p>ඔබට ගැළපෙන සතුටුදායක ඉගෙනුම් ගමනක්.</p>
			<button className="primary-action" onClick={onContinue}>
				මගේ පැතිකඩට යන්න
			</button>
		</section>
	);
}

export const onboardingSlides = [
	{
		icon: "book" as const,
		kicker: "ඔබට ගැළපෙන ඉගෙනීම",
		title: "කුඩා පියවර, ලොකු දියුණුව",
		body: "ඔබගේ වේගයට ගැළපෙන කෙටි පාඩම් සහ සරල පැහැදිලි කිරීම්.",
		tone: "violet",
	},
	{
		icon: "game" as const,
		kicker: "ක්‍රීඩාවෙන් පුහුණුව",
		title: "සෙල්ලම් කරන අතරතුර ඉගෙන ගන්න",
		body: "අභියෝග සම්පූර්ණ කර XP, කාසි සහ නව ලාංඡන දිනා ගන්න.",
		tone: "orange",
	},
	{
		icon: "sparkle" as const,
		kicker: "අවශ්‍ය විට සහාය",
		title: "Mindy හැම පියවරකම ඔබ සමඟයි",
		body: "පිළිතුර නොදී, ඔබටම සොයා ගන්නට උපකාරී වන කුඩා ඉඟි.",
		tone: "teal",
	},
];

export function Onboarding({
	onBack,
	onContinue,
}: {
	onBack(): void;
	onContinue(): void;
}) {
	const [index, setIndex] = useState(0);
	const pointerStart = useRef<number | null>(null);
	const slide = onboardingSlides[index];
	const moveSlide = (direction: -1 | 1) => {
		setIndex((current) =>
			Math.max(0, Math.min(onboardingSlides.length - 1, current + direction)),
		);
	};
	return (
		// Swiping is a touch shortcut; the previous/next buttons give keyboard and screen-reader
		// users the same navigation.
		<section
			className="onboarding-screen"
			aria-roledescription="carousel"
			aria-label="MindBridge හඳුන්වාදීම"
			onPointerDown={(event) => {
				pointerStart.current = event.clientX;
			}}
			onPointerUp={(event) => {
				if (pointerStart.current === null) return;
				const distance = event.clientX - pointerStart.current;
				pointerStart.current = null;
				if (Math.abs(distance) > 48) moveSlide(distance > 0 ? -1 : 1);
			}}
			onPointerCancel={() => {
				pointerStart.current = null;
			}}
		>
			<header className="onboarding-brand">
				<button
					type="button"
					className="setup-back"
					aria-label="ආරම්භක පිටුවට ආපසු"
					onClick={onBack}
				>
					<AppIcon name="back" size={19} />
				</button>
				<span className="onboarding-wordmark">
					<BrandMark variant="submark" /> MindBridge
				</span>
				<small>
					{index + 1} / {onboardingSlides.length}
				</small>
			</header>
			<div className={`onboarding-art onboarding-art--${slide.tone}`}>
				<button
					type="button"
					className="slide-arrow slide-arrow--previous"
					aria-label="පෙර විනිවිදකය"
					disabled={index === 0}
					onClick={() => moveSlide(-1)}
				>
					<AppIcon name="back" size={18} />
				</button>
				<div className="onboarding-art__ring" />
				<AppIcon name={slide.icon} size={72} />
				<span className="art-star art-star--one">✦</span>
				<span className="art-star art-star--two">✦</span>
				<button
					type="button"
					className="slide-arrow slide-arrow--next"
					aria-label="ඊළඟ විනිවිදකය"
					disabled={index === onboardingSlides.length - 1}
					onClick={() => moveSlide(1)}
				>
					<AppIcon name="arrow" size={18} />
				</button>
			</div>
			<div className="onboarding-copy" aria-live="polite">
				<p className="eyebrow">{slide.kicker}</p>
				<h1>{slide.title}</h1>
				<p>{slide.body}</p>
			</div>
			<nav
				className="pager"
				aria-label={`${index + 1} / ${onboardingSlides.length}`}
			>
				{onboardingSlides.map((item, itemIndex) => (
					<button
						key={item.title}
						className={
							itemIndex === index ? "pager-dot pager-dot--active" : "pager-dot"
						}
						aria-label={`${itemIndex + 1} වන පිටුව`}
						onClick={() => setIndex(itemIndex)}
					/>
				))}
			</nav>
			<div className="onboarding-actions">
				<button className="text-action" onClick={onContinue}>
					මඟ හරින්න
				</button>
				<button
					className="primary-action"
					onClick={() =>
						index === onboardingSlides.length - 1
							? onContinue()
							: setIndex(index + 1)
					}
				>
					{index === onboardingSlides.length - 1 ? "ආරම්භ කරමු" : "ඊළඟට"}{" "}
					<span aria-hidden="true">→</span>
				</button>
			</div>
		</section>
	);
}

export function LanguageSetup({
	onBack,
	onContinue,
}: {
	onBack(): void;
	onContinue(): void;
}) {
	const [selected, setSelected] = useState(true);
	const [previewOpen, setPreviewOpen] = useState(false);
	return (
		<section className="setup-screen language-setup">
			<SetupProgress current={2} onBack={onBack} />
			<div className="setup-icon">
				<AppIcon name="globe" size={34} />
			</div>
			<p className="eyebrow">ඉගෙනුම් භාෂාව</p>
			<h1>සිංහල මාධ්‍ය ඉගෙනීම</h1>
			<p className="quiet">මෙම ඉගෙනුම් ගමන 5 ශ්‍රේණිය සඳහා සිංහලෙන් සකස් කර ඇත.</p>
			<div className="language-list">
				<button
					type="button"
					className={
						selected ? "language-card language-card--selected" : "language-card"
					}
					aria-pressed={selected}
					onClick={() => setSelected((value) => !value)}
				>
					<span className="language-sample">ආයුබෝවන්</span>
					<span>
						<strong>සිංහල</strong>
						<small>Sinhala · 5 ශ්‍රේණිය</small>
					</span>
					<span className="selection-check" aria-hidden="true">
						✓
					</span>
				</button>
			</div>
			<button
				className="language-preview-toggle"
				type="button"
				aria-expanded={previewOpen}
				onClick={() => setPreviewOpen((open) => !open)}
			>
				<span>
					<AppIcon name="book" size={19} /> භාෂා පෙරදසුන
				</span>
				<b aria-hidden="true">{previewOpen ? "−" : "+"}</b>
			</button>
			{previewOpen && (
				<div className="language-preview" aria-live="polite">
					<p>
						<span>ආයුබෝවන්</span>
						<small>සුබ පැතුමක්</small>
					</p>
					<p>
						<span>ගණිතය</span>
						<small>අංක සහ හැඩතල</small>
					</p>
					<p>
						<span>පරිසරය</span>
						<small>අප වටා ලෝකය</small>
					</p>
				</div>
			)}
			<p className="language-help">
				<AppIcon name="shield" size={17} /> පසුව පැතිකඩෙන් භාෂාව නැවත තහවුරු කළ හැක.
			</p>
			<button
				className="primary-action setup-continue"
				disabled={!selected}
				onClick={onContinue}
			>
				ඉදිරියට යමු
			</button>
		</section>
	);
}

export function SetupProgress({
	current,
	onBack,
}: {
	current: number;
	onBack(): void;
}) {
	return (
		<header className="setup-progress-row">
			<button
				type="button"
				className="setup-back"
				aria-label="පෙර පිටුවට"
				onClick={onBack}
			>
				<AppIcon name="back" size={19} />
			</button>
			<div
				className="setup-progress-track"
				role="progressbar"
				aria-label="පැතිකඩ සැකසීමේ ප්‍රගතිය"
				aria-valuemin={1}
				aria-valuemax={3}
				aria-valuenow={current}
			>
				<span style={{ width: `${(current / 3) * 100}%` }} />
			</div>
			<small>{current} / 3</small>
		</header>
	);
}

export function ProfileSetup({
	name,
	onNameChange,
	avatarTone,
	onAvatarToneChange,
	onBack,
	onContinue,
}: {
	name: string;
	onNameChange(value: string): void;
	avatarTone: AvatarTone;
	onAvatarToneChange(value: AvatarTone): void;
	onBack(): void;
	onContinue(): void | Promise<void>;
}) {
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const tones: AvatarTone[] = ["violet", "sky", "teal", "orange"];
	const toneLabels: Record<AvatarTone, string> = {
		violet: "දම්",
		sky: "නිල්",
		teal: "කොළ",
		orange: "තැඹිලි",
	};
	return (
		<section className="setup-screen profile-setup">
			<SetupProgress current={3} onBack={onBack} />
			<p className="eyebrow">අවසන් පියවර</p>
			<h1>ඔබව හඳුනා ගනිමු</h1>
			<p className="quiet">ඔබගේ ඉගෙනුම් ගමන පුද්ගලීකරණය කිරීමට මෙය උපකාරී වේ.</p>
			<div className="avatar-picker">
				<LearnerAvatar tone={avatarTone} />
				<button
					className="avatar-edit"
					aria-label="අවතාරයේ වර්ණය වෙනස් කරන්න"
					onClick={() => {
						const index = tones.indexOf(avatarTone);
						onAvatarToneChange(tones[(index + 1) % tones.length]);
					}}
				>
					✎
				</button>
			</div>
			<fieldset className="setup-avatar-tones">
				<legend>ඔබ කැමති වර්ණය</legend>
				<div>
					{tones.map((tone) => (
						<button
							className={`avatar-tone avatar-tone--${tone}`}
							type="button"
							key={tone}
							aria-label={`${toneLabels[tone]} වර්ණය`}
							aria-pressed={avatarTone === tone}
							onClick={() => onAvatarToneChange(tone)}
						>
							{avatarTone === tone && <span>✓</span>}
						</button>
					))}
				</div>
			</fieldset>
			<label className="field-card">
				<span>
					ඔබේ නම <small>{name.length} / 24</small>
				</span>
				<input
					value={name}
					maxLength={24}
					onChange={(event) => onNameChange(event.target.value)}
					placeholder="උදා: කවිඳු"
				/>
			</label>
			<fieldset className="field-card grade-field">
				<legend>ශ්‍රේණිය</legend>
				<div>
					<span className="grade-pill grade-pill--selected">5 ශ්‍රේණිය</span>
				</div>
			</fieldset>
			<div className="privacy-note">
				<AppIcon name="shield" size={20} />
				<span>ඔබගේ තොරතුරු ආරක්ෂිතව තබා ගනී.</span>
			</div>
			{error && <p role="alert">{error}</p>}
			<button
				className="primary-action setup-continue"
				disabled={saving || !name.trim()}
				onClick={async () => {
					if (saving) return;
					setSaving(true);
					setError(null);
					try {
						await onContinue();
					} catch {
						setError("නම සුරැකීමට නොහැකි විය. නැවත උත්සාහ කරන්න.");
					} finally {
						setSaving(false);
					}
				}}
			>
				මගේ ගමන අරඹන්න
			</button>
		</section>
	);
}
