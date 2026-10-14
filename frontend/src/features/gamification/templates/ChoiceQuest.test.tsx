import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { ManifestView } from "../api/generated";
import { ChoiceQuest } from "./ChoiceQuest";

const manifest: ManifestView = {
  item_id: "fixture",
  language: "si",
  template_key: "choice_quest",
  question_text: "භාග",
  options: [{ option_id: "A", text: "එක් කාණ්ඩය" }],
};

describe("ChoiceQuest", () => {
  it("renders a Sinhala fixture", () => {
    const html = renderToStaticMarkup(
      <ChoiceQuest
        manifest={manifest}
        selectedOptionId={null}
        reducedMotion={false}
        onSelect={() => undefined}
      />,
    );
    expect(html).toContain("භාග");
    expect(html).toContain('lang="si"');
  });

  it("sets a zero animation duration when motion is reduced", () => {
    const html = renderToStaticMarkup(
      <ChoiceQuest
        manifest={manifest}
        selectedOptionId="A"
        reducedMotion
        onSelect={() => undefined}
      />,
    );
    expect(html).toContain("reduced-motion");
    expect(html).toContain("animation-duration:0ms");
  });
});
