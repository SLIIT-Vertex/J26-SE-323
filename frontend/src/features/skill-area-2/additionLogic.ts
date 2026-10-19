export function carryingCount(addends: number[]): number {
	if (
		(addends.length !== 2 && addends.length !== 3) ||
		addends.some(
			(value) => !Number.isSafeInteger(value) || value < 0 || value > 9999,
		)
	) {
		throw new Error("INVALID_ADDENDS");
	}
	let carry = 0;
	let count = 0;
	const width = Math.max(...addends.map((value) => String(value).length), 1);
	for (let place = 0; place < width; place += 1) {
		const power = 10 ** place;
		const total =
			carry +
			addends.reduce((sum, value) => sum + (Math.floor(value / power) % 10), 0);
		carry = Math.floor(total / 10);
		if (carry > 0) count += 1;
	}
	return count;
}

export function cumulativeTotals(values: number[], start = 0): number[] {
	let running = start;
	return values.map((value) => {
		running += value;
		return running;
	});
}

export function expandedTerms(value: number): number[] {
	if (!Number.isSafeInteger(value) || value < 0 || value > 99999) {
		throw new Error("INVALID_NUMBER");
	}
	return String(value)
		.split("")
		.map((digit, index, digits) =>
			Number(digit) * 10 ** (digits.length - index - 1),
		)
		.filter((term) => term > 0);
}

export function tableRowTotals(table: number[][]): number[] {
	if (table.length === 0 || table.some((row) => row.length === 0)) {
		throw new Error("INVALID_TABLE");
	}
	return table.map((row) =>
		row.reduce((sum, value) => {
			if (!Number.isSafeInteger(value)) throw new Error("INVALID_TABLE_CELL");
			return sum + value;
		}, 0),
	);
}

export function maximumRowIndex(table: number[][]): number {
	const totals = tableRowTotals(table);
	return totals.reduce(
		(best, value, index) => (value > totals[best] ? index : best),
		0,
	);
}

export function selectedTableTotal(
	table: number[][],
	cells: Array<[number, number]>,
): number {
	return cells.reduce((sum, [row, column]) => {
		const value = table[row]?.[column];
		if (!Number.isSafeInteger(value)) throw new Error("INVALID_TABLE_CELL");
		return sum + value;
	}, 0);
}

export function placeColumns(addends: number[]): number[][] {
	return addends.map((value) =>
		[1000, 100, 10, 1].map((place) => Math.floor(value / place) % 10),
	);
}

export function isValidRunningTotals(
	values: number[],
	totals: number[],
): boolean {
	const expected = cumulativeTotals(values);
	return (
		totals.length === expected.length &&
		totals.every((value, index) => value === expected[index])
	);
}

export function isValidRegrouping(
	addends: number[],
	total: number,
	carries: number,
): boolean {
	return (
		addends.reduce((sum, value) => sum + value, 0) === total &&
		carryingCount(addends) === carries
	);
}

export function sameCellSelection(
	expected: string[],
	selected: string[],
): boolean {
	return (
		expected.length === selected.length &&
		[...expected]
			.sort()
			.every((value, index) => value === [...selected].sort()[index])
	);
}
