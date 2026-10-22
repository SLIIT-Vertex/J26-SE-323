import type { ConstructedResponse } from "../mobile-learning-flow/api/generated";
export type Link = { sequence: number; source: string; target: string };
const revisions = (t: string[]) =>
	t.filter((x) => x.startsWith("replace") || x.startsWith("clear")).length;
export const bilingualResponse = (
	c: string,
	l: Link[],
	s: string[],
	t: string[],
): ConstructedResponse => ({
	kind: "information_bilingual_links",
	command_token: c,
	links: l.map((x) => ({
		sequence: x.sequence,
		english_token: x.source,
		sinhala_token: x.target,
	})),
	unlinked_english_tokens: s.filter((x) => !l.some((y) => y.source === x)),
	interaction_trace: t,
	revisions: revisions(t),
	invalid_link_count: 0,
	tap_alternative_used: true,
});
export const objectResponse = (
	c: string,
	l: Link[],
	s: string[],
	t: string[],
): ConstructedResponse => ({
	kind: "information_object_mapping",
	command_token: c,
	placements: l.map((x) => ({
		sequence: x.sequence,
		word_token: x.source,
		object_token: x.target,
	})),
	unplaced_word_tokens: s.filter((x) => !l.some((y) => y.source === x)),
	interaction_trace: t,
	revisions: revisions(t),
	invalid_drop_count: 0,
	tap_alternative_used: true,
});
