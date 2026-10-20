import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FractionActivity, StackedFraction } from "../FractionAdventureJourney";
import { FRACTION_GAMES, FRACTION_SKILLS } from "../manifest";
import {
	groupingResponse,
	quarterTableResponse,
	shadingResponse,
	tenthsResponse,
} from "../fractionLogic";

describe("Fraction Adventure", () => {
	let host: HTMLDivElement;
	let root: Root;
	const onResponse = vi.fn();
	beforeEach(() => {
		host = document.createElement("div");
		document.body.append(host);
		root = createRoot(host);
		onResponse.mockReset();
	});
	afterEach(async () => {
		await act(async () => root.unmount());
		host.remove();
	});

	it("orders three games easy-to-hard with 2, 3, and 2 challenges", () => {
		expect(FRACTION_GAMES.map((game) => game.difficulty)).toEqual([
			"පහසු",
			"මධ්‍යම",
			"අභියෝගාත්මක",
		]);
		expect(FRACTION_GAMES.map((game) => game.challengeCount)).toEqual([
			2, 3, 2,
		]);
		expect(FRACTION_SKILLS).toHaveLength(7);
	});

	it("renders four equal keyboard-operable regions and accepts any selected quarter", async () => {
		await act(async () =>
			root.render(
				<FractionActivity
					game={{
						response_kind: "fraction_shading",
						representation: "rectangle",
						denominator: 4,
						requested_numerator: 1,
						region_count: 4,
					}}
					onResponse={onResponse}
				/>,
			),
		);
		const regions = host.querySelectorAll<HTMLButtonElement>(".region");
		expect(regions).toHaveLength(4);
		await act(async () => regions[3].click());
		expect(onResponse).toHaveBeenLastCalledWith(
			{
				kind: "fraction_shading",
				representation: "rectangle",
				denominator: 4,
				shaded_indices: [3],
			},
			false,
		);
	});

	it("renders every apple and four visible sharing containers", async () => {
		await act(async () =>
			root.render(
				<FractionActivity
					game={{ response_kind: "equal_grouping", denominator: 4, total: 12 }}
					onResponse={onResponse}
				/>,
			),
		);
		expect(host.querySelectorAll(".apple-token")).toHaveLength(12);
		expect(host.querySelectorAll(".sharing-bowl")).toHaveLength(4);
		expect(
			host.querySelector<HTMLButtonElement>(".apple-token")?.draggable,
		).toBe(true);
		await act(async () =>
			host.querySelectorAll<HTMLButtonElement>(".sharing-bowl")[2].click(),
		);
		await act(async () =>
			host.querySelectorAll<HTMLButtonElement>(".apple-token")[0].click(),
		);
		expect(onResponse).toHaveBeenLastCalledWith(
			expect.objectContaining({
				kind: "equal_grouping",
				denominator: 4,
				assignments: expect.arrayContaining([2]),
			}),
			false,
		);
	});

	it("updates the correct semantic table cell and exposes 48px controls", async () => {
		await act(async () =>
			root.render(
				<FractionActivity
					game={{
						response_kind: "fraction_quantity_table",
						denominator: 4,
						total: 12,
					}}
					onResponse={onResponse}
				/>,
			),
		);
		const plus = host.querySelectorAll<HTMLButtonElement>(
			'button[aria-label*="එකතු"]',
		);
		expect(plus).toHaveLength(3);
		await act(async () => plus[1].click());
		expect(onResponse).toHaveBeenLastCalledWith(
			quarterTableResponse(12, [0, 1, 0]),
		);
		expect(getComputedStyle(plus[1]).minWidth).toBe("48px");
	});

	it("renders ten parts, stacked notation, and resets on a fresh revision mount", async () => {
		await act(async () =>
			root.render(
				<>
					<StackedFraction numerator={4} denominator={10} />
					<FractionActivity
						key="a"
						game={{
							response_kind: "tenths_representation",
							representation: "strip",
							denominator: 10,
							requested_numerator: 4,
							region_count: 10,
							stimulus_shaded_indices: [],
						}}
						onResponse={onResponse}
					/>
				</>,
			),
		);
		expect(host.querySelectorAll(".region")).toHaveLength(10);
		expect(
			host.querySelector(".stacked-fraction")?.getAttribute("aria-label"),
		).toBe("4 බෙදීම 10");
		await act(async () =>
			host.querySelectorAll<HTMLButtonElement>(".region")[0].click(),
		);
		await act(async () =>
			root.render(
				<FractionActivity
					key="b"
					game={{
						response_kind: "tenths_representation",
						representation: "strip",
						denominator: 10,
						requested_numerator: 2,
						region_count: 10,
						stimulus_shaded_indices: [],
					}}
					onResponse={onResponse}
				/>,
			),
		);
		expect(host.querySelectorAll(".region.shaded")).toHaveLength(0);
	});

	it("builds every strict response shape", () => {
		expect(shadingResponse("circle", 2, [1, 1])).toEqual({
			kind: "fraction_shading",
			representation: "circle",
			denominator: 2,
			shaded_indices: [1],
		});
		expect(groupingResponse(2, [0, 1])).toEqual({
			kind: "equal_grouping",
			denominator: 2,
			assignments: [0, 1],
		});
		expect(tenthsResponse("strip", 2, [4, 1])).toEqual({
			kind: "tenths_representation",
			representation: "strip",
			numerator: 2,
			denominator: 10,
			shaded_indices: [1, 4],
		});
	});
});
