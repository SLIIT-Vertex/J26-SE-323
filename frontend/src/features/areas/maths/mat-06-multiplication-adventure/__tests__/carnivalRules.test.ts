import { describe, expect, it } from "vitest";
import {
	carnivalResponse,
	carnivalTrainingPlace,
	groupsOf,
	MISSION_SKILLS,
	missionOrder,
	readTask,
	seatBlocks,
	wheelCount,
} from "../carnivalRules";

const WRITTEN = readTask({
	response_kind: "written_multiplication",
	multiplicand: 214,
	multiplier: 8,
	blank_count: 4,
});
const STORY = readTask({
	response_kind: "multiplication_story",
	group_size: 7,
	group_count: 9,
	asset: "balloon",
});
const FACT = readTask({
	response_kind: "multiplication_fact",
	multiplicand: 3,
	multiplier: 4,
});

describe("Sports carnival rules", () => {
	it("reads every kind of task and its equal groups", () => {
		expect(WRITTEN).toEqual({
			kind: "written",
			multiplicand: 214,
			multiplier: 8,
			width: 4,
		});
		expect(groupsOf(WRITTEN)).toEqual({ count: 8, size: 214 });
		expect(groupsOf(STORY)).toEqual({ count: 9, size: 7 });
		expect(groupsOf(FACT)).toEqual({ count: 4, size: 3 });
		expect(wheelCount(WRITTEN)).toBe(4);
		expect(wheelCount(STORY)).toBe(3);
	});

	it("builds each kind of scored answer from the score wheels", () => {
		expect(carnivalResponse(WRITTEN, [1, 7, 1, 2])).toEqual({
			kind: "written_multiplication",
			multiplicand: 214,
			multiplier: 8,
			result_digits: [1, 7, 1, 2],
			product: 1712,
		});
		expect(carnivalResponse(STORY, [0, 6, 3])).toEqual({
			kind: "multiplication_story",
			group_size: 7,
			group_count: 9,
			product: 63,
		});
		expect(carnivalResponse(FACT, [0, 1, 2])).toEqual({
			kind: "multiplication_fact",
			multiplicand: 3,
			multiplier: 4,
			product: 12,
		});
	});

	it("splits a stand's seats into place blocks without zeros", () => {
		expect(seatBlocks(214)).toEqual([
			{ place: "hundreds", value: 200 },
			{ place: "tens", value: 10 },
			{ place: "ones", value: 4 },
		]);
		expect(seatBlocks(305)).toEqual([
			{ place: "hundreds", value: 300 },
			{ place: "ones", value: 5 },
		]);
		expect(seatBlocks(28)).toEqual([
			{ place: "tens", value: 20 },
			{ place: "ones", value: 8 },
		]);
	});

	it("sends written products to the stadium and facts and stories to bowling", () => {
		expect(carnivalTrainingPlace(WRITTEN)).toBe("dancing-stadium");
		expect(carnivalTrainingPlace(STORY)).toBe("bowling-buddies");
		expect(carnivalTrainingPlace(FACT)).toBe("bowling-buddies");
	});

	it("never races the same kind twice in a row, with every other kind behind it", () => {
		const order = missionOrder(MISSION_SKILLS[3], () => 0);
		expect(order[0]).not.toBe(MISSION_SKILLS[3]);
		expect(new Set(order)).toEqual(new Set(MISSION_SKILLS));
		expect(order.at(-1)).toBe(MISSION_SKILLS[3]);
	});
});
