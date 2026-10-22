import { describe, expect, it } from "vitest";
import {
	buildResponse,
	type ComponentCard,
	composePreview,
	graphemes,
	matchResponse,
	placeMatch,
	SupportTeardownRegistry,
	standaloneSign,
	toggleComponent,
} from "../pillamLogic";

const card = (
	compose_si: string,
	logical_rank: number,
	extra: Partial<ComponentCard> = {},
): ComponentCard => ({
	token_id: `t-${compose_si}-${logical_rank}`,
	compose_si,
	logical_rank,
	visual_placement: "right",
	display_si: `◌${compose_si}`,
	accessible_label_si: "කොටස",
	...extra,
});

describe("composePreview", () => {
	it("shapes compounds in logical order whatever the placement order", () => {
		const kombuva = card("ෙ", 0);
		const alapilla = card("ා", 1);
		const hal = card("්", 2);
		expect(composePreview("ක", [alapilla, kombuva])).toBe("කො");
		expect(composePreview("ක", [hal, alapilla, kombuva])).toBe("කෝ");
		expect(composePreview("ක", [kombuva, kombuva])).toBe("කෛ");
		expect(composePreview("ක", [card("ෘ", 1), card("ෘ", 1)])).toBe("කෲ");
	});
	it("refuses forms that are not a reviewed akshara instead of showing broken marks", () => {
		expect(composePreview("ක", [card("ා", 1), card("්", 2)])).toBeNull();
		expect(composePreview("ක", [])).toBeNull();
	});
	it("never previews papili with the font, which would hide a wrong shape", () => {
		expect(
			composePreview("ල", [card("ු", 1, { allograph_shape: "vak" })]),
		).toBeNull();
	});
	it("stores NFC", () => {
		const text = composePreview("ක", [card("ෙ", 0), card("්", 2)]);
		expect(text).toBe(text?.normalize("NFC"));
	});
});

describe("graphemes", () => {
	it("keeps pilla and ZWJ conjuncts inside one tile", () => {
		expect(graphemes("කෝලු")).toEqual(["කෝ", "ලු"]);
		const conjunct = graphemes("ක්‍ෂ");
		expect(conjunct.join("")).toContain("‍");
		expect(conjunct.every((part) => !part.startsWith("‍"))).toBe(true);
	});
	it("the dotted circle is display only", () => {
		expect(standaloneSign("ි")).toBe("◌ි");
		expect(JSON.stringify(buildResponse("b", ["c"]))).not.toContain("◌");
	});
});

describe("responses", () => {
	it("name mode is one-to-one, vowel mode lets cards share a dock", () => {
		let rows = placeMatch([], "a", "d1", "name");
		rows = placeMatch(rows, "b", "d1", "name");
		expect(rows).toEqual([{ source: "b", destination: "d1" }]);
		let shared = placeMatch([], "a", "u", "vowel");
		shared = placeMatch(shared, "b", "u", "vowel");
		expect(shared).toHaveLength(2);
		expect(matchResponse("vowel", shared)).toMatchObject({
			kind: "sinhala_pillam_match",
			schema_version: "sinhala-pillam-response-v1",
			placements: [
				{ source_token_id: "a", destination_id: "u" },
				{ source_token_id: "b", destination_id: "u" },
			],
		});
	});
	it("keeps the child's placement order and respects the card limit", () => {
		expect(toggleComponent(["x"], "y", 4, false)).toEqual(["x", "y"]);
		expect(toggleComponent(["x", "y"], "x", 4, false)).toEqual(["y"]);
		expect(toggleComponent(["x"], "y", 4, true)).toEqual(["y"]);
		expect(toggleComponent(["a", "b"], "c", 2, false)).toEqual(["a", "b"]);
	});
});

describe("teardown receipt", () => {
	it("destroys before counting and names the exact revisions", () => {
		const registry = new SupportTeardownRegistry();
		let destroyed = 0;
		registry.track({ destroy: () => destroyed++ });
		registry.listen(() => destroyed++);
		registry.cache({ answer: 1 });
		const root = document.createElement("div");
		const liveRegion = document.createElement("p");
		liveRegion.textContent = "හරි";
		const receipt = registry.teardown(root, liveRegion, {
			support: "s@v1",
			manifest: "m@v1",
		});
		expect(destroyed).toBe(2);
		expect(receipt).toMatchObject({
			support_revision_id: "s@v1",
			manifest_revision_id: "m@v1",
			phaser_support_objects_remaining: 0,
			listeners_remaining: 0,
			dom_support_nodes_remaining: 0,
			live_region_cleared: true,
			cached_solution_cleared: true,
		});
	});
	it("reports support DOM that is still mounted", () => {
		const root = document.createElement("div");
		root.innerHTML = "<p data-support-node>ඉඟිය</p>";
		const receipt = new SupportTeardownRegistry().teardown(root, null, {
			support: "s",
			manifest: "m",
		});
		expect(receipt.dom_support_nodes_remaining).toBe(1);
	});
});
