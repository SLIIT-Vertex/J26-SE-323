import { lazy, Suspense } from "react";

import type { ManifestView } from "../../../api/generated";
import { useReducedMotion } from "../../../accessibility/reducedMotion";

const BuildManipulate = lazy(() =>
  import("./BuildManipulate").then((module) => ({ default: module.BuildManipulate })),
);

const preview: ManifestView = {
  item_id: "preview-fraction-bar",
  language: "en",
  template_key: "build_manipulate",
  question_text: "Shade one equal part.",
  options: [
    { option_id: "A", text: "One of two parts" },
    { option_id: "B", text: "The whole bar" },
  ],
};

export function BuildPreview() {
  const reducedMotion = useReducedMotion();
  return (
    <section>
      <p className="eyebrow">Template preview</p>
      <h2>Fraction bar</h2>
      <p lang="en">{preview.question_text}</p>
      <Suspense fallback={<p>Loading the fraction bar…</p>}>
        <BuildManipulate manifest={preview} reducedMotion={reducedMotion} onSelect={() => undefined} />
      </Suspense>
    </section>
  );
}
