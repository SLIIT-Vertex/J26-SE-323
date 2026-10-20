import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	DivisionWorkedDemo,
	EqualSharingActivity,
	LongDivisionWorkspace,
} from "../DivisionAdventureJourney";
import {
	canonicalLongDivision,
	writtenDivisionResponse,
} from "../divisionLogic";
import { DIVISION_GAMES, DIVISION_SKILLS } from "../manifest";

describe("Division Adventure", () => {
	let host: HTMLDivElement;
	let root: Root;
	beforeEach(() => {
		host = document.createElement("div");
		document.body.append(host);
		root = createRoot(host);
	});
	afterEach(async () => {
		await act(async () => root.unmount());
		host.remove();
	});

	it("contains exactly three games and five activities", () => {
		expect(DIVISION_GAMES.map((game) => game.challengeCount)).toEqual([
			2, 2, 1,
		]);
		expect(DIVISION_SKILLS).toHaveLength(5);
		expect(
			DIVISION_GAMES.every((game) =>
				game.asset.startsWith("/curriculum/game/G5-AREA-MAT-08/"),
			),
		).toBe(true);
	});

	it("submits the actual equal-sharing group quantities", async () => {
		const onResponse = vi.fn();
		await act(async () =>
			root.render(
				<EqualSharingActivity
					dividend={4}
					divisor={2}
					onResponse={onResponse}
				/>,
			),
		);
		const groups = host.querySelectorAll<HTMLButtonElement>(".sharing-group");
		await act(async () => groups[0].click());
		await act(async () => groups[1].click());
		await act(async () => groups[0].click());
		await act(async () => groups[1].click());
		const two = host.querySelector<HTMLButtonElement>(
			'button[aria-label="අංක 2"]',
		);
		await act(async () => two?.click());
		expect(onResponse).toHaveBeenLastCalledWith({
			kind: "equal_sharing",
			dividend: 4,
			divisor: 2,
			group_quantities: [2, 2],
			quotient: 2,
			remainder: 0,
		});
	});

	it("fills quotient, multiplication, subtraction and bring-down cells", async () => {
		const onComplete = vi.fn();
		await act(async () =>
			root.render(
				<LongDivisionWorkspace
					dividend={84}
					divisor={4}
					stepCount={2}
					onComplete={onComplete}
				/>,
			),
		);
		const press = async (cellLabel: string, digit: number) => {
			const cell = host.querySelector<HTMLButtonElement>(
				`button[aria-label="${cellLabel}"]`,
			);
			const key = host.querySelector<HTMLButtonElement>(
				`button[aria-label="අංක ${digit}"]`,
			);
			await act(async () => cell?.click());
			await act(async () => key?.click());
		};
		await press("1 පියවරේ බෙදිය යුතු කොටස", 8);
		await press("1 පියවරේ 1 ස්ථානයේ ලබ්ධි ඉලක්කම", 2);
		await press("1 පියවරේ ගුණිතය", 8);
		await press("1 පියවරේ අඩු කිරීමේ ඉතිරිය", 0);
		await press("1 පියවරේ පහළට ගෙනෙන ඉලක්කම", 4);
		await press("2 පියවරේ බෙදිය යුතු කොටස", 4);
		await press("2 පියවරේ 2 ස්ථානයේ ලබ්ධි ඉලක්කම", 1);
		await press("2 පියවරේ ගුණිතය", 4);
		await press("2 පියවරේ අඩු කිරීමේ ඉතිරිය", 0);
		await press("අවසාන ලබ්ධිය", 2);
		const keyOne = host.querySelector<HTMLButtonElement>(
			'button[aria-label="අංක 1"]',
		);
		await act(async () => keyOne?.click());
		await press("අවසාන ඉතිරිය", 0);
		expect(onComplete).toHaveBeenLastCalledWith(
			writtenDivisionResponse(84, 4, canonicalLongDivision(84, 4), 21, 0),
		);
		expect(
			host.querySelector('[data-cell-type="brought-down-digit"]'),
		).not.toBeNull();
	});

	it("reveals exact intermediate answers only in earned worked support", async () => {
		const response = writtenDivisionResponse(
			408,
			4,
			canonicalLongDivision(408, 4),
			102,
			0,
		);
		const example = {
			game: {
				response_kind: "written_division",
				dividend: 408,
				divisor: 4,
				step_count: 3,
			},
			correct_response: response,
		};
		await act(async () =>
			root.render(
				<DivisionWorkedDemo
					example={{ ...example, correct_response: null }}
					stage={3}
				/>,
			),
		);
		expect(host.textContent).not.toContain("2 × 4 = 8");
		await act(async () =>
			root.render(<DivisionWorkedDemo example={example} stage={3} />),
		);
		expect(host.textContent).toContain("1 × 4 = 4");
		expect(host.textContent).toContain("0 × 4 = 0");
		expect(host.textContent).toContain("2 × 4 = 8");
		expect(host.textContent).toContain("102");
	});

	it("keeps interactive grid cells and keypad targets at least 48px", async () => {
		host.style.width = "320px";
		await act(async () =>
			root.render(
				<LongDivisionWorkspace dividend={84} divisor={4} stepCount={2} />,
			),
		);
		const cell = host.querySelector<HTMLElement>(".division-cell");
		const key = host.querySelector<HTMLElement>(".division-keypad button");
		const workspace = host.querySelector<HTMLElement>(
			".long-division-workspace",
		);
		expect(getComputedStyle(cell as HTMLElement).minHeight).toBe("48px");
		expect(getComputedStyle(key as HTMLElement).minHeight).toBe("48px");
		expect(workspace?.style.maxWidth).toBe("100%");
		expect(workspace?.style.overflowX).toBe("clip");
		expect(
			host.querySelector('[aria-label="1 පියවරේ බෙදිය යුතු කොටස"]'),
		).not.toBeNull();
	});
});
