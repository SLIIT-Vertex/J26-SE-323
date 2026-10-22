/**
 * Post-scoring reveal only. Accurate emojis where one exists; simple labelled code-built
 * drawings otherwise, so කොස්ස and ඉදල stay distinct and no generic bird stands for කොකා.
 */
const EMOJI: Record<string, [string, string]> = {
	monaraa: ["🦚", "මොනරා"],
	jiraaf: ["🦒", "ජිරාෆ්"],
	itipandama: ["🕯️", "ඉටිපන්දම"],
	handa: ["🌙", "හඳ"],
	bolaya: ["⚽", "බෝලය"],
	kudaya: ["☂️", "කුඩය"],
	kochchiya: ["🚂", "කෝච්චිය"],
	dedunna: ["🌈", "දේදුන්න"],
	samanalayaa: ["🦋", "සමනලයා"],
	yathura: ["🔑", "යතුර"],
	sarungalaya: ["🪁", "සරුංගලය"],
	bimmala: ["🍄", "බිම්මල"],
};
const DRAWN: Record<string, string> = {
	kokaa: "කොකා",
	kossa: "කොස්ස",
	idala: "ඉදල",
	goviya: "ගොවියා",
	dora: "දොර",
	roti: "රොටී",
	oralosuwa: "ඔරලෝසුව",
	karawila: "කරවිල",
	panaawa: "පනාව",
	ahasa: "අහස",
};
const INK = "#3b2a63";

function Drawing({ id }: { id: string }) {
	switch (id) {
		case "kossa": // a long handle with a short brush head
			return (
				<>
					<line x1="20" y1="8" x2="58" y2="58" stroke={INK} strokeWidth="4" />
					<path
						d="M52 54 l16 10 -10 12 -14 -14 z"
						fill="#c9a66b"
						stroke={INK}
						strokeWidth="2"
					/>
				</>
			);
		case "idala": // a bundle of fanned coconut sticks, no handle
			return (
				<>
					{[-24, -14, -4, 6, 16, 26].map((dx) => (
						<line
							key={dx}
							x1="40"
							y1="10"
							x2={40 + dx}
							y2="70"
							stroke="#8a6240"
							strokeWidth="2"
						/>
					))}
					<rect x="34" y="8" width="12" height="12" rx="3" fill="#b7895c" />
				</>
			);
		case "roti":
			return (
				<>
					<circle
						cx="32"
						cy="42"
						r="20"
						fill="#e8c07a"
						stroke={INK}
						strokeWidth="2"
					/>
					<circle
						cx="48"
						cy="38"
						r="20"
						fill="#f1d396"
						stroke={INK}
						strokeWidth="2"
					/>
				</>
			);
		case "dora":
			return (
				<>
					<rect
						x="22"
						y="6"
						width="36"
						height="68"
						rx="3"
						fill="#c9a66b"
						stroke={INK}
						strokeWidth="3"
					/>
					<circle cx="50" cy="42" r="3" fill={INK} />
				</>
			);
		case "oralosuwa":
			return (
				<>
					<circle
						cx="40"
						cy="40"
						r="30"
						fill="#fff"
						stroke={INK}
						strokeWidth="4"
					/>
					<line x1="40" y1="40" x2="40" y2="20" stroke={INK} strokeWidth="3" />
					<line x1="40" y1="40" x2="54" y2="40" stroke={INK} strokeWidth="3" />
				</>
			);
		case "panaawa":
			return (
				<>
					<rect x="10" y="30" width="60" height="10" rx="3" fill="#8b65b5" />
					{[14, 19, 24, 30, 35, 40, 45, 50, 56, 61, 66].map((x) => (
						<line
							key={x}
							x1={x}
							y1="40"
							x2={x}
							y2="56"
							stroke="#8b65b5"
							strokeWidth="2"
						/>
					))}
				</>
			);
		case "karawila":
			return (
				<ellipse
					cx="40"
					cy="40"
					rx="14"
					ry="32"
					fill="#6aa84f"
					stroke={INK}
					strokeWidth="2"
					strokeDasharray="3 2"
				/>
			);
		case "ahasa":
			return (
				<>
					<rect x="4" y="4" width="72" height="72" rx="10" fill="#cfe8ff" />
					<circle cx="56" cy="22" r="9" fill="#f4d06f" />
				</>
			);
		case "goviya":
			return (
				<>
					<circle cx="34" cy="16" r="7" fill="#c98f5f" />
					<line x1="34" y1="23" x2="34" y2="50" stroke={INK} strokeWidth="4" />
					<line x1="34" y1="50" x2="26" y2="72" stroke={INK} strokeWidth="4" />
					<line x1="34" y1="50" x2="42" y2="72" stroke={INK} strokeWidth="4" />
					<line
						x1="36"
						y1="32"
						x2="60"
						y2="62"
						stroke="#8a6240"
						strokeWidth="3"
					/>
					<path d="M56 60 l10 2 -4 8 z" fill="#777" />
				</>
			);
		default: // kokaa: a long-legged white wader, deliberately not a generic bird emoji
			return (
				<>
					<ellipse
						cx="40"
						cy="34"
						rx="16"
						ry="10"
						fill="#fff"
						stroke={INK}
						strokeWidth="2"
					/>
					<line x1="52" y1="28" x2="60" y2="12" stroke={INK} strokeWidth="2" />
					<line
						x1="60"
						y1="12"
						x2="72"
						y2="14"
						stroke="#e0a030"
						strokeWidth="3"
					/>
					<line x1="36" y1="44" x2="34" y2="74" stroke={INK} strokeWidth="2" />
					<line x1="44" y1="44" x2="46" y2="74" stroke={INK} strokeWidth="2" />
				</>
			);
	}
}

export function RiddleReveal({ revealKey }: { revealKey: string }) {
	const emoji = EMOJI[revealKey];
	if (emoji)
		return (
			<p className="rd-reveal">
				<span role="img" aria-label={emoji[1]}>
					{emoji[0]}
				</span>{" "}
				<strong>{emoji[1]}</strong>
			</p>
		);
	const label = DRAWN[revealKey];
	if (!label) return null;
	return (
		<figure className="rd-reveal">
			<svg
				viewBox="0 0 80 80"
				width="80"
				height="80"
				role="img"
				aria-label={label}
			>
				<Drawing id={revealKey} />
			</svg>
			<figcaption>{label}</figcaption>
		</figure>
	);
}
