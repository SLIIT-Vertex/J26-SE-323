import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";
export type Link = { sequence: number; source: string; target: string };
const revisions = (t: string[]) =>
	t.filter((x) => x.startsWith("replace") || x.startsWith("clear")).length;
export const vocabularyResponse = (
	c: string,
	l: Link[],
	s: string[],
	t: string[],
): ConstructedResponse => ({
	kind: "place_vocabulary_mapping",
	command_token: c,
	placements: l.map((x) => ({
		sequence: x.sequence,
		word_token: x.source,
		scene_token: x.target,
	})),
	unplaced_word_tokens: s.filter((x) => !l.some((y) => y.source === x)),
	interaction_trace: t,
	revisions: revisions(t),
	invalid_drop_count: 0,
	tap_alternative_used: true,
});
export const groupResponse = (
	c: string,
	l: Link[],
	s: string[],
	t: string[],
): ConstructedResponse => ({
	kind: "lesson_place_group_sort",
	command_token: c,
	placements: l.map((x) => ({
		sequence: x.sequence,
		entry_token: x.source,
		heading_token: x.target,
	})),
	unplaced_entry_tokens: s.filter((x) => !l.some((y) => y.source === x)),
	interaction_trace: t,
	revisions: revisions(t),
	invalid_drop_count: 0,
	tap_alternative_used: true,
});
export const sequenceResponse = (
	c: string,
	p: string,
	o: string[],
	all: string[],
	t: string[],
): ConstructedResponse => ({
	kind: "place_name_sequence",
	command_token: c,
	place_token: p,
	ordered_chunk_tokens: o,
	unused_chunk_tokens: all.filter((x) => !o.includes(x)),
	interaction_trace: t,
	revisions: revisions(t),
	invalid_drop_count: 0,
	tap_alternative_used: true,
});
