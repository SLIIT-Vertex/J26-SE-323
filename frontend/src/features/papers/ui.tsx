import type { ReactNode } from "react";

// The shared look of the paper screens. The shapes come from the MindBridge logo: two arches that
// overlap and blend where they cross (blue + pink = navy, blue + yellow = green, pink + yellow =
// orange), with a small sun between them.

export function ArchMark({ rays = true, className }: { rays?: boolean; className?: string }) {
  return (
    <svg className={className} viewBox="0 0 272 214" aria-hidden="true" focusable="false">
      <g transform="translate(0 44)">
        <path className="mb-arch mb-arch--sky" d="M34 136V92a66 66 0 0 1 132 0v44" />
        <path className="mb-arch mb-arch--rose" d="M106 136V92a66 66 0 0 1 132 0v44" />
        <circle className="mb-sun" cx="136" cy="130" r="32" />
      </g>
      {rays ? (
        <g className="mb-rays">
          <path d="M136 6v26" />
          <path d="M96 18l14 22" />
          <path d="M176 18l-14 22" />
        </g>
      ) : null}
    </svg>
  );
}

const LETTER_COLOURS = ["sky", "rose", "sun", "mint", "sky", "rose", "sun", "mint", "sky", "rose"];

export function Wordmark() {
  return (
    <span className="mb-wordmark" role="img" aria-label="MindBridge">
      {"MindBridge".split("").map((letter, index) => (
        <span
          // the letters never change order, so the position is a stable key
          // biome-ignore lint/suspicious/noArrayIndexKey: fixed word
          key={index}
          className={`mb-wordmark__${LETTER_COLOURS[index]}`}
          aria-hidden="true"
        >
          {letter}
        </span>
      ))}
    </span>
  );
}

export function ScreenHeader({
  title,
  kicker,
  back,
  children,
}: {
  title: string;
  kicker?: string;
  back?: { href: string; label: string };
  children?: ReactNode;
}) {
  return (
    <header className="mb-head">
      <ArchMark className="mb-head__arches" rays={false} />
      <div className="mb-head__text">
        {back ? (
          <a className="mb-back" href={back.href}>
            <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false">
              <path d="M12.5 4 6.5 10l6 6" />
            </svg>
            {back.label}
          </a>
        ) : null}
        {kicker ? <p className="mb-kicker">{kicker}</p> : null}
        <h1 className="mb-title">{title}</h1>
        {children}
      </div>
    </header>
  );
}

export type Tone = "sky" | "rose" | "sun" | "mint" | "ink" | "plain";

export function Chip({
  tone = "plain",
  children,
  icon,
}: {
  tone?: Tone;
  children: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <span className={`mb-chip mb-chip--${tone}`}>
      {icon}
      {children}
    </span>
  );
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div className="mb-loading" role="status">
      <span className="mb-loading__dots" aria-hidden="true">
        <i />
        <i />
        <i />
      </span>
      <span>{label}</span>
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="mb-note mb-note--rose" role="alert">
      <p>{message}</p>
      {onRetry ? (
        <button type="button" className="mb-btn mb-btn--ghost mb-btn--small" onClick={onRetry}>
          Try again
        </button>
      ) : null}
    </div>
  );
}

export function Tick({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" aria-hidden="true" focusable="false">
      <path d="m4.5 10.5 3.6 3.6 7.4-8" />
    </svg>
  );
}

/** A sheet of paper with the four black corner squares, as the parent should see it. */
export function PageGuide() {
  return (
    <svg className="mb-guide" viewBox="0 0 120 150" aria-hidden="true" focusable="false">
      <rect x="6" y="4" width="108" height="142" rx="6" className="mb-guide__sheet" />
      <rect x="12" y="10" width="11" height="11" className="mb-guide__mark" />
      <rect x="97" y="10" width="11" height="11" className="mb-guide__mark" />
      <rect x="12" y="129" width="11" height="11" className="mb-guide__mark" />
      <rect x="97" y="129" width="11" height="11" className="mb-guide__mark" />
      <g className="mb-guide__lines">
        <path d="M30 40h60M30 54h46M30 74h60M30 88h38M30 108h52" />
      </g>
    </svg>
  );
}

/** Ten stepping stones, filled up to the value. Unknown is drawn as empty dashed stones. */
export function StoneMeter({
  value,
  tone,
  label,
}: {
  value: number | null;
  tone: Tone;
  label: string;
}) {
  const filled = value === null ? 0 : Math.max(0, Math.min(10, Math.round(value * 10)));
  return (
    <span className={`mb-stones mb-stones--${tone}`} role="img" aria-label={label}>
      {Array.from({ length: 10 }, (_, index) => (
        <i
          // biome-ignore lint/suspicious/noArrayIndexKey: ten fixed stones
          key={index}
          className={value === null ? "is-unknown" : index < filled ? "is-filled" : undefined}
        />
      ))}
    </span>
  );
}

export function PaperIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M7 3.5h7.5L19 8v12.5H7z" />
      <path d="M14.5 3.5V8H19" />
      <path d="M10 12.5h6M10 16h6" />
    </svg>
  );
}

export function GrowthIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M4 19.5V13a8 8 0 0 1 16 0v6.5" />
      <path d="M9 19.5V14a3 3 0 0 1 6 0v5.5" />
    </svg>
  );
}

export function HistoryIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M5 7.5h14M7 4h10M4.5 11h15v8.5h-15z" />
      <path d="M9.5 15h5" />
    </svg>
  );
}
