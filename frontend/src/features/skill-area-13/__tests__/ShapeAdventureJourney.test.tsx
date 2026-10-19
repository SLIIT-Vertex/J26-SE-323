import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ShapeActivity, ShapeWorkedDemo } from "../ShapeAdventureJourney";
import { SHAPE_GAMES, SHAPE_SKILLS } from "../manifest";

describe("Shape Adventure", () => {
	let host: HTMLDivElement;
	let root: Root;
	beforeEach(() => {
		host = document.createElement("div");
		host.style.width = "320px";
		document.body.append(host);
		root = createRoot(host);
	});
	afterEach(async () => {
		await act(async () => root.unmount());
		host.remove();
	});
	it("contains exactly three games and three activities", () => {
		expect(SHAPE_GAMES).toHaveLength(3);
		expect(SHAPE_SKILLS).toHaveLength(3);
		expect(SHAPE_GAMES.map((game) => game.challengeLabel)).toEqual([
			"අභියෝග 1ක්",
			"අභියෝග 1ක්",
			"අභියෝග 1ක්",
		]);
	});
	it("renders a 320px table with labelled 48px fill cells and emits full evidence", async () => {
		const onResponse = vi.fn();
		await act(async () =>
			root.render(
				<ShapeActivity
					game={{ response_kind: "shape_property_table", row_ids: ["cube"] }}
					onResponse={onResponse}
				/>,
			),
		);
		const cells = [
			...host.querySelectorAll(".shape-table td button"),
		] as HTMLButtonElement[];
		expect(cells).toHaveLength(3);
		expect(cells[0].getAttribute("aria-label")).toContain("මුහුණත්");
		expect(getComputedStyle(cells[0]).minHeight).toBe("48px");
		for (const [index, value] of [6, 8, 12].entries()) {
			await act(async () => cells[index].click());
			const pad = [...host.querySelectorAll(".shape-keypad button")].find(
				(button) => button.textContent === String(value),
			) as HTMLButtonElement;
			await act(async () => pad.click());
		}
		expect(onResponse).toHaveBeenLastCalledWith(
			expect.objectContaining({
				kind: "shape_property_table",
				rows: [{ solid_id: "cube", faces: 6, vertices: 8, edges: 12 }],
			}),
		);
		expect(host.scrollWidth).toBeLessThanOrEqual(320);
	});
	it("uses visual examples and dropdowns for horizontal and vertical", async () => {
		const onResponse = vi.fn();
		await act(async () =>
			root.render(
				<ShapeActivity
					game={{
						response_kind: "orientation_identification",
						example_ids: ["spirit_level", "plumb_line"],
					}}
					onResponse={onResponse}
				/>,
			),
		);
		expect(host.querySelectorAll("svg[role=img]")).toHaveLength(2);
		const selects = [...host.querySelectorAll("select")] as HTMLSelectElement[];
		await act(async () => {
			selects[0].value = "horizontal";
			selects[0].dispatchEvent(new Event("change", { bubbles: true }));
		});
		await act(async () => {
			selects[1].value = "vertical";
			selects[1].dispatchEvent(new Event("change", { bubbles: true }));
		});
		expect(onResponse).toHaveBeenLastCalledWith(
			expect.objectContaining({
				kind: "orientation_identification",
				selections: [
					{ example_id: "spirit_level", orientation: "horizontal" },
					{ example_id: "plumb_line", orientation: "vertical" },
				],
			}),
		);
	});
	it("includes and matches all four textbook solids", async () => {
		const onResponse = vi.fn(),
			ids = ["cube", "cuboid", "cylinder", "triangular_pyramid"];
		await act(async () =>
			root.render(
				<ShapeActivity
					game={{
						response_kind: "solid_net_match",
						solid_ids: ids,
						net_ids: ids,
					}}
					onResponse={onResponse}
				/>,
			),
		);
		expect(host.textContent).toContain("ඝනකය");
		expect(host.textContent).toContain("ඝනකාභය");
		expect(host.textContent).toContain("සිලින්ඩරය");
		expect(host.textContent).toContain("ත්‍රිකෝණ පිරමීඩය");
		const sections = host.querySelectorAll(".net-match section");
		for (let index = 0; index < ids.length; index += 1) {
			const solid = sections[0].querySelectorAll("button")[
					index
				] as HTMLButtonElement,
				net = sections[1].querySelectorAll("button")[
					index
				] as HTMLButtonElement;
			await act(async () => solid.click());
			await act(async () => net.click());
		}
		expect(onResponse).toHaveBeenLastCalledWith(
			expect.objectContaining({
				kind: "solid_net_match",
				matches: expect.arrayContaining([
					{ solid_id: "cylinder", net_id: "cylinder" },
				]),
			}),
		);
	});
	it("reveals exact intermediate answers in worked support", async () => {
		const example = {
			mode: "exact_failed_activity" as const,
			prompt_si: "වගුව පුරවන්න",
			game: {
				schema_version: "shape-adventure-item-v1" as const,
				chapter: "shape_table" as const,
			},
			correct_response: {
				kind: "shape_property_table" as const,
				rows: [{ solid_id: "cube", faces: 6, vertices: 8, edges: 12 }],
				filled_cells: ["cube:faces", "cube:vertices", "cube:edges"],
			},
			steps_si: ["මුහුණත්", "ශීර්ෂ", "දාර", "අවසන්"],
		};
		await act(async () =>
			root.render(<ShapeWorkedDemo example={example} stage={3} />),
		);
		expect(host.textContent).toContain("මුහුණත් 6");
		expect(host.textContent).toContain("ශීර්ෂ 8");
		expect(host.textContent).toContain("දාර 12");
	});
});
