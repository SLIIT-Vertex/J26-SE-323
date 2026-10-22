export type ShapeChapter =
	| "shape_table"
	| "orientation_lab"
	| "solid_net_match";

export const SHAPE_SKILLS = [
	{
		id: "G5-MAT-SHAPE-TABLE-01",
		chapter: "shape_table",
		name: "හැඩතල වගුව පුරවමු",
	},
	{
		id: "G5-MAT-ORIENTATION-01",
		chapter: "orientation_lab",
		name: "තිරස් හා සිරස් හඳුනාගනිමු",
	},
	{
		id: "G5-MAT-SOLID-NET-01",
		chapter: "solid_net_match",
		name: "ඝන වස්තුවට පතරොම ගළපමු",
	},
] as const;

export const SHAPE_GAMES = [
	{
		id: "shape_table",
		title: "හැඩතල වගුව",
		difficulty: "පහසු",
		challengeLabel: "අභියෝග 1ක්",
	},
	{
		id: "orientation_lab",
		title: "තිරස් ද? සිරස් ද?",
		difficulty: "මධ්‍යම",
		challengeLabel: "අභියෝග 1ක්",
	},
	{
		id: "solid_net_match",
		title: "පතරොම් ගළපමු",
		difficulty: "අභියෝගාත්මක",
		challengeLabel: "අභියෝග 1ක්",
	},
] as const;

export const SOLID_LABELS: Record<string, string> = {
	cube: "ඝනකය",
	cuboid: "ඝනකාභය",
	cylinder: "සිලින්ඩරය",
	triangular_pyramid: "ත්‍රිකෝණ පිරමීඩය",
};
