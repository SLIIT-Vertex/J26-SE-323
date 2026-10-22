import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";

export type FamilyLink = { sequence: number; source: string; target: string };

export function familyLinkResponse(
	commandToken: string,
	links: FamilyLink[],
	sources: string[],
	trace: string[],
): ConstructedResponse {
	return {
		kind: "family_bilingual_links",
		command_token: commandToken,
		links: links.map((link) => ({
			sequence: link.sequence,
			english_token: link.source,
			sinhala_token: link.target,
		})),
		unlinked_english_tokens: sources.filter(
			(source) => !links.some((link) => link.source === source),
		),
		interaction_trace: trace,
		revisions: trace.filter((event) => event.startsWith("replace:")).length,
		invalid_link_count: 0,
		tap_alternative_used: true,
	};
}
