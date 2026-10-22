import type { ConstructedResponsePayload } from "../../../mobile-learning-flow/api/generated";

export type TimeValue = { hours: number; minutes: number };

export function normalizeTime(hours: number, minutes: number): TimeValue {
	const total = Math.max(0, Math.trunc(hours) * 60 + Math.trunc(minutes));
	return { hours: Math.floor(total / 60), minutes: total % 60 };
}

export function to24Hour(hour: number, period: "am" | "pm"): number {
	if (period === "am") return hour === 12 ? 0 : hour;
	return hour === 12 ? 12 : hour + 12;
}

export function from24Hour(hour24: number): { hour: number; period: "am" | "pm" } {
	const hour = ((hour24 % 24) + 24) % 24;
	return { hour: hour % 12 || 12, period: hour < 12 ? "am" : "pm" };
}

export function elapsedTime(start: TimeValue, end: TimeValue): TimeValue {
	let difference = end.hours * 60 + end.minutes - (start.hours * 60 + start.minutes);
	if (difference < 0) difference += 24 * 60;
	return { hours: Math.floor(difference / 60), minutes: difference % 60 };
}

export function addTime(left: TimeValue, right: TimeValue): TimeValue {
	return normalizeTime(left.hours + right.hours, left.minutes + right.minutes);
}

export function subtractTime(left: TimeValue, right: TimeValue): TimeValue {
	const total = left.hours * 60 + left.minutes - (right.hours * 60 + right.minutes);
	return normalizeTime(0, total);
}

export const unitMatchResponse = (matches: number[]): ConstructedResponsePayload => ({ kind: "time_unit_match", matches });
export const analogClockResponse = (hour: number, minute: number): ConstructedResponsePayload => ({ kind: "analog_clock", hour, minute });
export const conversionResponse = (hour24: number, minute: number): ConstructedResponsePayload => ({ kind: "time_conversion", hour24, minute });
export const elapsedResponse = (hours: number, minutes: number): ConstructedResponsePayload => ({ kind: "elapsed_time", hours, minutes });
export const arithmeticResponse = (hours: number, minutes: number, regrouped: boolean): ConstructedResponsePayload => ({ kind: "time_arithmetic", hours, minutes, regrouped });
