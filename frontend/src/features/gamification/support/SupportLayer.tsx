import { useEffect, useState } from "react";

import type { SupportView } from "../api/generated";

type SupportLayerProps = {
  support: SupportView | null;
  reducedMotion: boolean;
};

export function SupportLayer({ support, reducedMotion }: SupportLayerProps) {
  const [hintExceeded, setHintExceeded] = useState(false);

  useEffect(() => {
    setHintExceeded(false);
    if (!support) return;
    const timer = window.setTimeout(() => setHintExceeded(true), support.maximum_duration_ms);
    return () => window.clearTimeout(timer);
  }, [support]);

  if (!support) return null;
  const shownSteps = support.steps.slice(0, support.maximum_number_of_steps);
  return (
    <aside
      data-support-layer
      data-hint-exceeded={hintExceeded ? "true" : "false"}
      className={reducedMotion ? "support-layer reduced-motion" : "support-layer"}
    >
      <p className="eyebrow">Support</p>
      <h2>{support.title}</h2>
      {support.scaffold_type === "visual_guidance" ? (
        <FractionDiagram diagram={support.diagram} />
      ) : (
        <ol>
          {shownSteps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      )}
      <p className="hint">
        Suggested limit: {support.maximum_number_of_steps} steps, {support.maximum_duration_ms} ms.
        The server decides when support ends.
      </p>
    </aside>
  );
}

function FractionDiagram({ diagram }: { diagram: SupportView["diagram"] }) {
  const count = typeof diagram?.count === "number" ? diagram.count : 4;
  const groups = typeof diagram?.groups === "number" ? diagram.groups : 2;
  const cells = Array.from({ length: count }, (_, index) => index);
  return (
    <svg viewBox={`0 0 ${count * 28} 36`} role="img" aria-label="Fraction groups">
      {cells.map((index) => (
        <rect
          key={index}
          x={index * 28 + 2}
          y={6}
          width={24}
          height={24}
          rx={4}
          fill={index < Math.ceil(count / groups) ? "#087443" : "#d7e5dc"}
        />
      ))}
    </svg>
  );
}
