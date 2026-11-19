import { describe, expect, it } from "vitest";
import {
	beadResponse,
	costumePlaces,
	costumeResponse,
	costumeValue,
	emptyLine,
	numberFromRods,
	paradeResponse,
	placeOfDigit,
	placeToy,
	readParade,
	removeToy,
	rodPower,
	rodsFromNumber,
	spaced,
	stepRod,
} from "../toyRules";

describe("Toy parade rules", () => {
	it("places, moves and swaps toys between slots", () => {
		let line = emptyLine(4);
		line = placeToy(line, 2, 0);
		line = placeToy(line, 0, 1);
		expect(line).toEqual([2, 0, null, null]);
		line = placeToy(line, 2, 1);
		expect(line).toEqual([0, 2, null, null]);
		line = placeToy(line, 3, 0);
		expect(line).toEqual([3, 2, null, null]);
		line = removeToy(line, 2);
		expect(line).toEqual([3, null, null, null]);
		expect(placeToy(line, 1, 9)).toBe(line);
	});

	it("answers with the values in slot order once every slot is filled", () => {
		const values = [3721, 5831, 4210, 7021];
		expect(paradeResponse([0, 2, null, 3], values)).toBeNull();
		expect(paradeResponse([0, 2, 1, 3], values)).toEqual({
			kind: "number_order",
			order: [3721, 4210, 5831, 7021],
		});
	});

	it("reads the server's parade and defaults to smallest first", () => {
		expect(
			readParade({ values: [3105, 3721, "x", -1], ascending: false }),
		).toEqual({
			values: [3105, 3721],
			ascending: false,
		});
		expect(readParade(undefined).ascending).toBe(true);
		expect(spaced(40205)).toBe("40 205");
	});
});

describe("Bead toy rules", () => {
	it("counts beads per rod into a six-place number", () => {
		expect(rodsFromNumber(40205)).toEqual([0, 4, 0, 2, 0, 5]);
		expect(numberFromRods([0, 4, 0, 2, 0, 5])).toBe(40205);
		expect(stepRod([0, 0, 0, 0, 0, 9], 5, 1)).toEqual([0, 0, 0, 0, 0, 9]);
		expect(stepRod([0, 0, 0, 0, 0, 0], 5, -1)).toEqual([0, 0, 0, 0, 0, 0]);
		expect(rodPower(0)).toBe(5);
		expect(beadResponse([0, 4, 0, 2, 0, 5])).toEqual({
			kind: "bead_placement",
			rods: [0, 4, 0, 2, 0, 5],
		});
	});
});

describe("Costume shop rules", () => {
	it("offers one costume per place and answers the right question", () => {
		expect(costumePlaces(52014)).toEqual([0, 1, 2, 3, 4]);
		expect(placeOfDigit(52014, 2)).toBe(3);
		expect(placeOfDigit(52512, 5)).toBeNull();
		expect(costumeValue(8, 2)).toBe(800);
		expect(costumeResponse("position", 8, null)).toBeNull();
		expect(costumeResponse("position", 8, 2)).toEqual({
			kind: "drag_to_slot",
			selected_place: 2,
		});
		expect(costumeResponse("represented", 8, 2)).toEqual({
			kind: "drag_to_slot",
			represented_value: 800,
		});
	});
});
