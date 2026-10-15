import type { ManifestView } from "../api/generated";

type ChoiceQuestProps = {
  manifest: ManifestView;
  selectedOptionId: string | null;
  reducedMotion: boolean;
  onSelect: (optionId: string) => void;
};

export function ChoiceQuest({
  manifest,
  selectedOptionId,
  reducedMotion,
  onSelect,
}: ChoiceQuestProps) {
  return (
    <section className={reducedMotion ? "choice-quest reduced-motion" : "choice-quest"}>
      <p className="question" lang={manifest.language}>
        {manifest.question_text}
      </p>
      <div className="options">
        {manifest.options.map((option) => (
          <button
            key={option.option_id}
            type="button"
            className={option.option_id === selectedOptionId ? "option option--selected" : "option"}
            style={{ animationDuration: reducedMotion ? "0ms" : "160ms" }}
            onClick={() => onSelect(option.option_id)}
          >
            <span className="option-id">{option.option_id}</span>
            <span lang={manifest.language}>{option.text}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
