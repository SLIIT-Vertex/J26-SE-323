/**
 * Rules for Nimo's crystal flight, free of Phaser and React. Nimo flies through every energy
 * crystal, then the child sets how much energy they make together. The server alone decides
 * whether the total is correct.
 */

import type { ConstructedResponse } from "../../../mobile-learning-flow/api/generated";

export const MAX_ENERGY = 99;

export function collect(collected: readonly number[], index: number): number[] {
	return collected.includes(index) ? [...collected] : [...collected, index];
}

export function stepEnergy(energy: number | null, delta: 1 | -1): number {
	if (energy === null) return delta > 0 ? 1 : 0;
	return Math.min(MAX_ENERGY, Math.max(0, energy + delta));
}

export function crystalResponse(
	crystalCount: number,
	collected: readonly number[],
	energy: number | null,
): ConstructedResponse | null {
	if (crystalCount === 0 || energy === null) return null;
	if (collected.length < crystalCount) return null;
	return { kind: "combine_quantities", combined: true, total: energy };
}
