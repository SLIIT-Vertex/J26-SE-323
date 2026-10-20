export const PLACES = ["thousands", "hundreds", "tens", "ones"] as const;

export type Exchange = {
	from_place: "thousands" | "hundreds" | "tens";
	to_place: "hundreds" | "tens" | "ones";
};

export function digitsOf(value: number, width: number) {
	return String(Math.max(0, value)).padStart(width, "0").slice(-width).split("").map(Number);
}

export function applyExchanges(digits: number[], places: string[], exchanges: Exchange[]) {
	const working = digits.slice();
	for (const exchange of exchanges) {
		const source = places.indexOf(exchange.from_place);
		const destination = places.indexOf(exchange.to_place);
		if (source < 0 || destination !== source + 1 || working[source] <= 0) continue;
		working[source] -= 1;
		working[destination] += 10;
	}
	return working;
}

export function adjacent(places: string[], fromPlace: string, toPlace: string) {
	return places.indexOf(toPlace) === places.indexOf(fromPlace) + 1;
}
