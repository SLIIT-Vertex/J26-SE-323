/** Isolated parts keep one/many literal, without depending on composite art sheets. */
export function PlantPicture({
	visual,
	count = 1,
}: {
	visual: string;
	count?: number;
}) {
	const key = visual.replace(/^plant-/, "").replace(/-slot$/, "");
	const single: Record<string, string> = {
		roots: "root system",
		leaves: "leaf",
		leaf: "leaf",
		buds: "bud",
		bud: "bud",
		branches: "branch",
		branch: "branch",
		flowers: "flower",
		fruits: "fruit",
		petals: "petal",
	};
	const noun = single[key] ?? key;
	const name =
		count === 1
			? noun
			: noun === "leaf"
				? "leaves"
				: noun === "branch"
					? "branches"
					: `${noun}s`;
	return (
		<svg
			viewBox="0 0 150 60"
			role="img"
			aria-label={`${count === 1 ? "One" : count === 2 ? "Two" : "Three"} ${name}`}
			className="word-drop-plant-picture"
		>
			{Array.from({ length: count }, (_, i) => {
				const x = 75 + (i - (count - 1) / 2) * 42;
				return (
					<g key={`${key}-${x}`} transform={`translate(${x} 30)`}>
						{/root/.test(key) ? (
							<g stroke="#95613d" strokeWidth="3" fill="none">
								<path d="M0 -22V24M0 -15L-16 0M0 -5L18 12M0 5L-17 23M0 15L16 26" />
							</g>
						) : /stem|trunk|branch/.test(key) ? (
							<g
								stroke={/stem/.test(key) ? "#4d9048" : "#95613d"}
								strokeWidth="7"
								strokeLinecap="round"
							>
								<path d="M0 23V-22" />
								{/branch/.test(key) && <path d="M0 0L17 -15M0 10L-15 -5" />}
							</g>
						) : /leaf|leaves/.test(key) ? (
							<g>
								<ellipse rx="12" ry="22" fill="#62a056" />
								<path d="M0 -17V23" stroke="#29613a" strokeWidth="2" />
							</g>
						) : /bud/.test(key) ? (
							<g>
								<path d="M0 0V25" stroke="#4d9048" strokeWidth="3" />
								<ellipse cy="-6" rx="11" ry="16" fill="#df6d9d" />
								<path d="M-11 2L0 12L11 2" fill="#75a658" />
							</g>
						) : /petal/.test(key) ? (
							<ellipse rx="10" ry="22" fill="#ed88b1" />
						) : (
							<text
								textAnchor="middle"
								dominantBaseline="central"
								fontSize="34"
							>
								{/fruit/.test(key) ? "🥭" : "🌸"}
							</text>
						)}
					</g>
				);
			})}
		</svg>
	);
}
