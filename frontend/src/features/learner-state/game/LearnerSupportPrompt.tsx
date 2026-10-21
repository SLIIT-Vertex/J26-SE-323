// A gentle, dismissible prompt after an answer. It encourages the child; it never says the child
// is confused or not paying attention, and it promises no help the app cannot give.

import "./camera.css";

import type { SupportPrompt } from "./supportPrompts";

const PROMPTS: Record<SupportPrompt, { icon: string; title: string; body: string; action: string }> =
	{
		"take-a-break": {
			icon: "🌿",
			title: "කෙටි විවේකයක් ගනිමු",
			body: "ගැඹුරු හුස්මක් ගන්න, ඇස්වලට තත්පර කිහිපයක් විවේක දෙන්න. ඊට පස්සේ නැවත පටන් ගමු!",
			action: "මම සූදානම්!",
		},
		"keep-going": {
			icon: "⭐",
			title: "ඔබට පුළුවන්!",
			body: "මෙය ටිකක් අභියෝගයක්. හෙමින්, පියවරෙන් පියවර හිතලා බලමු.",
			action: "හරි, බලමු!",
		},
	};

export function LearnerSupportPrompt({
	prompt,
	onDismiss,
}: {
	prompt: SupportPrompt;
	onDismiss(): void;
}) {
	const copy = PROMPTS[prompt];
	return (
		<aside
			className={`learner-support-prompt learner-support-prompt--${prompt}`}
			aria-labelledby="learner-support-prompt-title"
			aria-live="polite"
		>
			<span className="learner-support-prompt__icon" aria-hidden="true">
				{copy.icon}
			</span>
			<div>
				<h2 id="learner-support-prompt-title">{copy.title}</h2>
				<p>{copy.body}</p>
			</div>
			<button type="button" className="primary-action" onClick={onDismiss}>
				{copy.action}
			</button>
		</aside>
	);
}
