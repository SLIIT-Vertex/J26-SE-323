import { describe, expect, it } from "vitest";
import { partnerUnit } from "../PuppetShow";
import {
	durationAnswer,
	durationResponse,
	durationText,
	fromMinutes,
	MISSION_SKILLS,
	missionOrder,
	periodText,
	readTask,
	studioTrainingPlace,
	to24,
} from "../studioRules";

const ELAPSED = readTask({
	response_kind: "elapsed_time",
	start_hour: 6,
	start_minute: 20,
	end_hour: 7,
	end_minute: 10,
});
const ADD = readTask({
	response_kind: "time_arithmetic",
	operation: "add",
	left_hours: 3,
	left_minutes: 25,
	right_hours: 2,
	right_minutes: 45,
});
const TAKE = readTask({
	response_kind: "time_arithmetic",
	operation: "subtract",
	left_hours: 2,
	left_minutes: 20,
	right_hours: 1,
	right_minutes: 50,
});

describe("Movie studio rules", () => {
	it("counts time in groups of 60 minutes", () => {
		expect(fromMinutes(70)).toEqual({ hours: 1, minutes: 10 });
		expect(durationAnswer(ELAPSED)).toEqual({ hours: 0, minutes: 50 });
		expect(durationAnswer(ADD)).toEqual({ hours: 6, minutes: 10 });
		expect(durationAnswer(TAKE)).toEqual({ hours: 0, minutes: 30 });
		expect(durationText({ hours: 0, minutes: 50 })).toBe("මිනිත්තු 50");
		expect(durationText({ hours: 6, minutes: 10 })).toBe("පැය 6 මිනිත්තු 10");
	});

	it("always sends minutes under 60, as the server expects", () => {
		expect(durationResponse(ELAPSED, 70, false)).toEqual({
			kind: "elapsed_time",
			hours: 1,
			minutes: 10,
		});
		expect(durationResponse(ADD, 370, true)).toEqual({
			kind: "time_arithmetic",
			hours: 6,
			minutes: 10,
			regrouped: true,
		});
	});

	it("turns call-sheet times into the 24-hour clock, with noon and midnight", () => {
		expect(to24(1, "pm")).toBe(13);
		expect(to24(12, "pm")).toBe(12);
		expect(to24(12, "am")).toBe(0);
		expect(to24(7, "am")).toBe(7);
		expect(periodText(1, 30, "pm")).toBe("1.30 ප.ව.");
	});

	it("pairs each unit with the bigger unit it makes", () => {
		expect(partnerUnit([60, "minutes"])).toBe("hours");
		expect(partnerUnit([365, "days"])).toBe("ordinary_years");
		expect(partnerUnit([366, "days"])).toBe("leap_years");
		expect(partnerUnit([7, "days"])).toBe("weeks");
	});

	it("sends durations to the editing room and clocks and units to the puppets", () => {
		expect(studioTrainingPlace(ELAPSED)).toBe("fast-forward");
		expect(studioTrainingPlace(ADD)).toBe("fast-forward");
		expect(
			studioTrainingPlace(readTask({ response_kind: "time_conversion" })),
		).toBe("puppet-show");
		expect(
			studioTrainingPlace(readTask({ response_kind: "analog_clock" })),
		).toBe("puppet-show");
		expect(
			studioTrainingPlace(readTask({ response_kind: "time_unit_match" })),
		).toBe("puppet-show");
	});

	it("never films the same kind of scene twice in a row", () => {
		const order = missionOrder(MISSION_SKILLS[0], () => 0);
		expect(order[0]).not.toBe(MISSION_SKILLS[0]);
		expect(new Set(order)).toEqual(new Set(MISSION_SKILLS));
	});
});
