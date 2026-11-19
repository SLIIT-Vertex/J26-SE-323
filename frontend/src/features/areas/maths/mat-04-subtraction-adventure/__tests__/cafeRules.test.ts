import { describe, expect, it } from "vitest";
import {
	cafeResponse,
	cafeTrainingPlace,
	canOpen,
	exchangesFor,
	MISSION_SKILLS,
	missionOrder,
	NO_EXCHANGE_SKILL_ID,
	operands,
	readOrder,
	solveColumns,
	workingDigits,
} from "../cafeRules";

const TAKE_AWAY = readOrder({
	places: ["hundreds", "tens", "ones"],
	width: 3,
	minuend: 685,
	subtrahend: 339,
});
const STORY = readOrder({
	places: ["hundreds", "tens", "ones"],
	width: 3,
	relationship: "how_many_more",
	asset: "cookie",
	quantities: [
		{ source: "first", label_si: "ගූගූ කෑ කුකී", value: 319 },
		{ source: "second", label_si: "බුබු කෑ කුකී", value: 425 },
	],
});

describe("Monster café rules", () => {
	it("opens a pack by taking one from a column and giving ten to its right", () => {
		expect(workingDigits([6, 8, 5], [1])).toEqual([6, 7, 15]);
		expect(workingDigits([7, 2, 0], [0, 1])).toEqual([6, 11, 10]);
		expect(canOpen([6, 0, 5], [], 1)).toBe(false);
		expect(canOpen([6, 0, 5], [0], 1)).toBe(true);
		expect(canOpen([6, 8, 5], [], 2)).toBe(false);
	});

	it("lists exchanges rightmost first, as the server does", () => {
		expect(exchangesFor(["hundreds", "tens", "ones"], [0, 1])).toEqual([
			{ from_place: "tens", to_place: "ones" },
			{ from_place: "hundreds", to_place: "tens" },
		]);
	});

	it("builds the column answer only when every column has a digit", () => {
		expect(cafeResponse(TAKE_AWAY, null, [3, 4, null], [1])).toBeNull();
		expect(cafeResponse(TAKE_AWAY, null, [3, 4, 6], [1])).toEqual({
			kind: "column_subtraction",
			result_digits: [3, 4, 6],
			exchanges: [{ from_place: "tens", to_place: "ones" }],
		});
	});

	it("answers a two-monster order from the order the child put on top", () => {
		expect(STORY.story?.relationship).toBe("how_many_more");
		expect(STORY.snack).toBe("cookie");
		expect(operands(STORY, null)).toBeNull();
		expect(operands(STORY, "second")).toEqual({ top: 425, bottom: 319 });
		expect(cafeResponse(STORY, "second", [1, 0, 6], [])).toEqual({
			kind: "difference_story",
			relationship: "how_many_more",
			minuend_source: "second",
			subtrahend_source: "first",
			result_digits: [1, 0, 6],
			result: 106,
		});
	});

	it("solves the textbook examples for worked examples and hints", () => {
		expect(solveColumns(685, 339, 3)).toEqual({
			opens: [1],
			digits: [3, 4, 6],
		});
		expect(solveColumns(720, 512, 3)).toEqual({
			opens: [1],
			digits: [2, 0, 8],
		});
		expect(solveColumns(4497, 2359, 4)).toEqual({
			opens: [2],
			digits: [2, 1, 3, 8],
		});
		expect(solveColumns(5312, 2847, 4)).toEqual({
			opens: [2, 1, 0],
			digits: [2, 4, 6, 5],
		});
	});

	it("never takes the same kind of order twice in a row, and lines up the rest behind it", () => {
		const order = missionOrder(MISSION_SKILLS[0], () => 0);
		expect(order[0]).not.toBe(MISSION_SKILLS[0]);
		expect(new Set(order)).toEqual(new Set(MISSION_SKILLS));
		expect(order.at(-1)).toBe(MISSION_SKILLS[0]);
	});

	it("feeds the fluffballs for the plainest help and swaps snacks for the rest", () => {
		expect(cafeTrainingPlace("visual_guidance", MISSION_SKILLS[1])).toBe(
			"fluffball-feast",
		);
		expect(cafeTrainingPlace("simpler_same_game", MISSION_SKILLS[0])).toBe(
			"fluffball-feast",
		);
		expect(cafeTrainingPlace("prerequisite_repair", NO_EXCHANGE_SKILL_ID)).toBe(
			"fluffball-feast",
		);
		expect(cafeTrainingPlace("step_by_step_guidance", MISSION_SKILLS[1])).toBe(
			"snack-swap",
		);
		expect(
			cafeTrainingPlace("worked_parallel_example", MISSION_SKILLS[2]),
		).toBe("snack-swap");
	});
});
