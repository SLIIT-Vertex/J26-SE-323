/** Visible prose, leaving out charts, hidden tables, legends, tick labels and numbers. */

export function proseWordCount(root: ParentNode): number {
	const clone = (root as HTMLElement).cloneNode(true) as HTMLElement;
	for (const node of clone.querySelectorAll(
		"svg, .sr-only, .rd-tick, .rd-legend, .rd-num",
	))
		node.remove();
	clone.querySelectorAll("details:not([open])").forEach((node) => {
		const summary = node.querySelector("summary");
		node.replaceChildren(...(summary ? [summary] : []));
	});
	return (clone.textContent ?? "")
		.replace(/[·•→✓✗★✕—–]/g, " ")
		.split(/\s+/)
		.filter((word) => word && !/^[\d.,%/+-]+$/.test(word) && !/^\d/.test(word))
		.length;
}
