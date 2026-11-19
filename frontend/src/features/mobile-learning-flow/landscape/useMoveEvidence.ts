import { useCallback, useMemo, useRef } from "react";

/**
 * Counts what the child did on the board for the server's interaction summary. A correction is
 * a return to a place the child had already set after working on another one.
 */
export function useMoveEvidence() {
	const started = useRef(Date.now());
	const state = useRef({
		moves: 0,
		corrections: 0,
		carries: 0,
		columns: 0,
		firstActionMs: null as number | null,
		touched: new Set<number>(),
		lastPlace: null as number | null,
	});

	const reset = useCallback(() => {
		started.current = Date.now();
		state.current = {
			moves: 0,
			corrections: 0,
			carries: 0,
			columns: 0,
			firstActionMs: null,
			touched: new Set(),
			lastPlace: null,
		};
	}, []);

	const note = useCallback(
		(action: "digit" | "carry" | "move", place?: number) => {
			const current = state.current;
			current.moves += 1;
			current.firstActionMs ??= Math.max(0, Date.now() - started.current);
			if (action === "carry") current.carries += 1;
			if (action === "digit" && place !== undefined) {
				current.columns += 1;
				if (current.touched.has(place) && current.lastPlace !== place)
					current.corrections += 1;
				current.touched.add(place);
				current.lastPlace = place;
			}
		},
		[],
	);

	const summary = useCallback(() => {
		const current = state.current;
		const elapsed = Math.max(0, Date.now() - started.current);
		return {
			response_time_ms: elapsed,
			interaction_summary: {
				move_count: current.moves,
				correction_count: current.corrections,
				carry_actions: current.carries,
				column_actions: current.columns,
				alignment_valid: true,
				first_action_ms: current.firstActionMs ?? 0,
				active_time_ms: elapsed,
				attempt_count: 1,
			},
		};
	}, []);

	return useMemo(() => ({ reset, note, summary }), [reset, note, summary]);
}
