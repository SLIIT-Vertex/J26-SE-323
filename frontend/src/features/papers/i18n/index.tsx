import { Fragment, type ReactNode, useSyncExternalStore } from "react";
import type { MessageKey } from "./messages.en";
import { en } from "./messages.en";
import { si } from "./messages.si";
import { ta } from "./messages.ta";

// The practice screens speak Sinhala unless the parent picks English or Tamil in the settings sheet.
// The choice is remembered on the phone. Words live in the three messages.* files.

export type { MessageKey };
export type Language = "si" | "en" | "ta";

export const LANGUAGE_CHOICES: { code: Language; native: string }[] = [
  { code: "si", native: "සිංහල" },
  { code: "en", native: "English" },
  { code: "ta", native: "தமிழ்" },
];

const DICTIONARIES: Record<Language, Record<MessageKey, string>> = {
  si,
  en,
  ta,
};
const LOCALES: Record<Language, string> = {
  si: "si-LK",
  en: "en-GB",
  ta: "ta-LK",
};

export const DEFAULT_LANGUAGE: Language = "si";
const STORAGE_KEY = "mindbridge.practiceLanguage";

function isLanguage(value: unknown): value is Language {
  return value === "si" || value === "en" || value === "ta";
}

/** The saved choice, or Sinhala when there is none (or the phone will not let us read it). */
export function initialLanguage(): Language {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (isLanguage(saved)) return saved;
  } catch {
    // private window or blocked storage: fall through to the default
  }
  return DEFAULT_LANGUAGE;
}

let current: Language = initialLanguage();
const listeners = new Set<() => void>();

export function getLanguage(): Language {
  return current;
}

export function setLanguage(language: Language, options: { remember?: boolean } = {}): void {
  if (language === current) return;
  current = language;
  if (options.remember !== false) {
    try {
      localStorage.setItem(STORAGE_KEY, language);
    } catch {
      // not remembered, but the screens still change
    }
  }
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Re-renders the component when the language changes. */
export function useLanguage(): Language {
  return useSyncExternalStore(subscribe, getLanguage, getLanguage);
}

export function locale(): string {
  return LOCALES[current];
}

type Params = Record<string, string | number>;

function fill(text: string, params?: Params): string {
  if (!params) return text;
  return text.replace(/\{(\w+)\}/g, (whole, name: string) => (name in params ? String(params[name]) : whole));
}

/** The words for a key, in the language now selected, with {name} filled in from params. */
export function t(key: MessageKey, params?: Params): string {
  return fill(DICTIONARIES[current][key] ?? en[key], params);
}

type CountKey<K extends string> = K extends `${infer Base}.one` ? Base : never;
export type CountBase = CountKey<MessageKey>;

/** A pair of keys, "<base>.one" and "<base>.other": the first for exactly 1, the second otherwise. */
export function tn(base: CountBase, count: number, params?: Params): string {
  return t(`${base}.${count === 1 ? "one" : "other"}` as MessageKey, {
    n: count,
    ...params,
  });
}

/** Like t, but **words in double stars** come out bold. */
export function rich(key: MessageKey, params?: Params): ReactNode {
  const parts = t(key, params).split("**");
  return parts.map((part, index) =>
    // biome-ignore lint/suspicious/noArrayIndexKey: a fixed split of one sentence
    index % 2 === 1 ? <strong key={index}>{part}</strong> : <Fragment key={index}>{part}</Fragment>,
  );
}

/** Used by tests: every dictionary, so they can be compared with the English master list. */
export const dictionaries = DICTIONARIES;
