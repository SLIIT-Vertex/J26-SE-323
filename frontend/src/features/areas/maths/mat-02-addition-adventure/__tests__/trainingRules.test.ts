import { describe, expect, it } from "vitest";
import { collect, crystalResponse, stepEnergy } from "../crystalRules";
import { binLayout } from "../factoryScene";
import {
	allFed,
	bundle,
	canBundle,
	digitsByPower,
	emptyFactory,
	factoryResponse,
	feed,
	placesFor,
	solveFactory,
} from "../factoryRules";

describe("Number Factory rules", () => {
	it("feeds digits into place bins and bundles ten into the next place", () => {
		const addends = [458, 379];
		let state = emptyFactory(addends);
		expect(state.places).toBe(3);
		state = feed(state, addends, 0);
		state = feed(state, addends, 0);
		expect(state.counts).toEqual([8, 5, 4]);
		expect(allFed(state)).toBe(false);
		state = feed(state, addends, 1);
		expect(state.counts).toEqual([17, 12, 7]);
		expect(canBundle(state, 0)).toBe(true);
		state = bundle(state, 0);
		expect(state.counts).toEqual([7, 13, 7]);
		state = bundle(state, 1);
		expect(state.counts).toEqual([7, 3, 8]);
		expect(canBundle(state, 2)).toBe(false);
		expect(bundle(state, 2)).toBe(state);
		expect(state.bundled).toEqual([1, 1, 0]);
	});

	it("answers with the output wheels and the places the child bundled", () => {
		const addends = [458, 379];
		let state = emptyFactory(addends);
		expect(factoryResponse(state, [7, 3, 8])).toBeNull();
		state = feed(feed(state, addends, 0), addends, 1);
		state = bundle(bundle(state, 0), 1);
		expect(factoryResponse(state, [7, 3, null])).toEqual({
			kind: "regroup_carry",
			total: 37,
			carry_count: 2,
			aligned: true,
		});
		expect(factoryResponse(state, [7, null, 8])).toBeNull();
		expect(factoryResponse(state, [7, 3, 8])).toMatchObject({
			total: 837,
			carry_count: 2,
		});
	});

	it("makes room for a thousands place and solves a three-number worked example", () => {
		expect(placesFor([382, 728, 298])).toBe(4);
		const solved = solveFactory([382, 728, 298]);
		expect(solved.counts).toEqual([8, 0, 4, 1]);
		expect(solved.bundled).toEqual([1, 2, 1, 0]);
		expect(digitsByPower(1408, 4)).toEqual([8, 0, 4, 1]);
	});

	it("shrinks crowded bins so every block stays inside", () => {
		const roomy = binLayout(7, 0, 300);
		const crowded = binLayout(29, 2, 250);
		expect(roomy.scale).toBe(1);
		expect(crowded.scale).toBeLessThan(1);
		for (const position of crowded.positions) {
			expect(position.y).toBeGreaterThan(0);
			expect(position.x).toBeLessThan(250);
		}
	});
});

describe("Crystal flight rules", () => {
	it("needs every crystal and an energy total", () => {
		expect(collect([0], 0)).toEqual([0]);
		expect(collect([0], 1)).toEqual([0, 1]);
		expect(stepEnergy(null, 1)).toBe(1);
		expect(stepEnergy(0, -1)).toBe(0);
		expect(crystalResponse(2, [0], 11)).toBeNull();
		expect(crystalResponse(2, [0, 1], null)).toBeNull();
		expect(crystalResponse(2, [1, 0], 11)).toEqual({
			kind: "combine_quantities",
			combined: true,
			total: 11,
		});
	});
});
