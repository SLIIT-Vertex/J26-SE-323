import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";

export type LongDivisionStep = {
	step_index: number;
	partial_dividend: number;
	quotient_digit: number;
	quotient_column: number;
	partial_product: number;
	subtraction_result: number;
	brought_down_digit: number | null;
};

export type WrittenDivisionResponse = Extract<
	ConstructedResponse,
	{ kind: "written_division" }
>;

export function validateDivisionOperands(
	dividend: number,
	divisor: number,
): void {
	if (!Number.isSafeInteger(dividend) || !Number.isSafeInteger(divisor))
		throw new Error("DIVISION_OPERANDS_MUST_BE_INTEGERS");
	if (dividend < 0 || dividend > 999 || divisor < 1 || divisor > 9)
		throw new Error("DIVISION_OPERANDS_OUT_OF_RANGE");
}

export function integerDivision(dividend: number, divisor: number) {
	validateDivisionOperands(dividend, divisor);
	const quotient = Math.floor(dividend / divisor);
	const remainder = dividend % divisor;
	if (remainder < 0 || remainder >= divisor)
		throw new Error("INVALID_REMAINDER");
	return { quotient, remainder };
}

export function canonicalLongDivision(
	dividend: number,
	divisor: number,
): LongDivisionStep[] {
	validateDivisionOperands(dividend, divisor);
	const digits = String(dividend).split("").map(Number);
	const steps: LongDivisionStep[] = [];
	let partial = 0;
	let started = false;
	for (let column = 0; column < digits.length; column += 1) {
		partial = partial * 10 + digits[column];
		if (!started && partial < divisor && column < digits.length - 1) continue;
		started = true;
		const quotientDigit = Math.floor(partial / divisor);
		const product = quotientDigit * divisor;
		const subtraction = partial - product;
		steps.push({
			step_index: steps.length,
			partial_dividend: partial,
			quotient_digit: quotientDigit,
			quotient_column: column,
			partial_product: product,
			subtraction_result: subtraction,
			brought_down_digit:
				column + 1 < digits.length ? digits[column + 1] : null,
		});
		partial = subtraction;
	}
	return steps;
}

export function writtenDivisionResponse(
	dividend: number,
	divisor: number,
	workingSteps: LongDivisionStep[],
	finalQuotient: number,
	finalRemainder: number,
): WrittenDivisionResponse {
	return {
		kind: "written_division",
		dividend,
		divisor,
		working_steps: workingSteps,
		quotient_digits: workingSteps.map((step) => step.quotient_digit),
		partial_dividends: workingSteps.map((step) => step.partial_dividend),
		partial_products: workingSteps.map((step) => step.partial_product),
		subtraction_results: workingSteps.map((step) => step.subtraction_result),
		brought_down_digits: workingSteps.flatMap((step) =>
			step.brought_down_digit === null ? [] : [step.brought_down_digit],
		),
		final_quotient: finalQuotient,
		final_remainder: finalRemainder,
	};
}

export function validateWorkingTrace(
	dividend: number,
	divisor: number,
	trace: LongDivisionStep[],
): { valid: boolean; firstIncorrectStep: number | null } {
	const expected = canonicalLongDivision(dividend, divisor);
	const fields: Array<keyof LongDivisionStep> = [
		"step_index",
		"partial_dividend",
		"quotient_digit",
		"quotient_column",
		"partial_product",
		"subtraction_result",
		"brought_down_digit",
	];
	for (
		let index = 0;
		index < Math.max(expected.length, trace.length);
		index += 1
	) {
		if (
			!expected[index] ||
			!trace[index] ||
			fields.some((field) => expected[index][field] !== trace[index][field])
		)
			return { valid: false, firstIncorrectStep: index };
	}
	return { valid: true, firstIncorrectStep: null };
}

export function contextualRemainderInterpretation(
	quotient: number,
	remainder: number,
): string {
	return `complete_groups:${quotient};leftover:${remainder}`;
}
