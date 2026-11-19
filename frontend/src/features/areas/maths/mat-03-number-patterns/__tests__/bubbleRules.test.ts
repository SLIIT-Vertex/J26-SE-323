import { describe, expect, it } from "vitest";
import { bubbleTrainingPlace } from "../NimoBubbleTrouble";
import {
	applyRule,
	GATE_RULES,
	MISSION_SKILLS,
	missionOrder,
	patternResponse,
	patternRule,
	pickMissionSkill,
	readPattern,
	ringChoices,
	solvePattern,
} from "../bubbleRules";

describe("Bubble Trouble rules", () => {
	it("reads the server's pattern and solves it only for help games", () => {
		const board = readPattern({
			operation: "multiply",
			visible_terms: [8, 40, null, null],
			missing_indices: [2, 3],
		});
		expect(board).toEqual({
			terms: [8, 40, null, null],
			blanks: [2, 3],
			operation: "multiply",
		});
		expect(patternRule(board)).toEqual({ operation: "multiply", step: 5 });
		expect(solvePattern(board)).toEqual([200, 1000]);
		const down = readPattern({
			operation: "subtract",
			visible_terms: [12, 10, 8, 6, null, null],
		});
		expect(down.blanks).toEqual([4, 5]);
		expect(solvePattern(down)).toEqual([4, 2]);
	});

	it("offers the same moves at every junction, so the rings never give the rule away", () => {
		expect(ringChoices(40, 8)).toEqual([200, 80, 72, 42, 38]);
		expect(ringChoices(7, 5)).toEqual([35, 14, 9, 5]);
		// Whatever the pattern, the next number by any gate rule is among the rings.
		for (const previous of [3, 12, 48, 150, 6]) {
			for (const rule of GATE_RULES) {
				const next = applyRule(rule, previous);
				if (next <= 1000) expect(ringChoices(previous, null)).toContain(next);
			}
		}
		expect(ringChoices(400, 80).every((value) => value <= 1000)).toBe(true);
	});

	it("builds the scored response from the chosen rule and rings", () => {
		const times = GATE_RULES[3] ?? null;
		const plus = GATE_RULES[0] ?? null;
		expect(patternResponse(times, [200], 2)).toBeNull();
		expect(patternResponse(null, [200, 1000], 2)).toBeNull();
		expect(patternResponse(times, [200, 1000], 2)).toEqual({
			kind: "constant_ratio_pattern",
			multiplier: 5,
			completed_terms: [200, 1000],
		});
		expect(patternResponse(plus, [9, 11], 2)).toEqual({
			kind: "constant_difference_pattern",
			operation: "add",
			difference: 2,
			completed_terms: [9, 11],
		});
	});

	it("never races the same pattern twice in a row", () => {
		let previous: string | null = null;
		for (const roll of [0, 0.3, 0.6, 0.99, 0, 0]) {
			const next = pickMissionSkill(previous, () => roll);
			expect(MISSION_SKILLS).toContain(next);
			expect(next).not.toBe(previous);
			previous = next;
		}
	});

	it("lines up every other pattern behind the race's pattern, the last race's at the end", () => {
		const order = missionOrder(MISSION_SKILLS[3], () => 0);
		expect(order).toHaveLength(4);
		expect(new Set(order)).toEqual(new Set(MISSION_SKILLS));
		expect(order[0]).not.toBe(MISSION_SKILLS[3]);
		expect(order.at(-1)).toBe(MISSION_SKILLS[3]);
	});

	it("sends adding patterns to Tiki and multiplying ones to the jellyfish", () => {
		expect(bubbleTrainingPlace("worked_parallel_example", "add")).toBe(
			"tiki-steps",
		);
		expect(bubbleTrainingPlace("step_by_step_guidance", "subtract")).toBe(
			"tiki-steps",
		);
		expect(bubbleTrainingPlace("step_by_step_guidance", "multiply")).toBe(
			"jellyfish-party",
		);
		expect(bubbleTrainingPlace("prerequisite_repair", "multiply")).toBe(
			"jellyfish-party",
		);
		expect(bubbleTrainingPlace("visual_guidance", "multiply")).toBe(
			"tiki-steps",
		);
		expect(bubbleTrainingPlace("simpler_same_game", "multiply")).toBe(
			"tiki-steps",
		);
	});
});
