import { lazy, Suspense, useState } from "react";
import "./research-dashboard.css";

const ResearchDashboard = lazy(() =>
	import("./ResearchDashboard").then((module) => ({
		default: module.ResearchDashboard,
	})),
);

/** Floating entry to the research dashboard. The caller mounts it only in research mode. */
export function ResearchButton({ learnerId }: { learnerId: string }) {
	const [open, setOpen] = useState(false);
	return (
		<>
			<button
				type="button"
				className="rd-fab"
				lang="en"
				aria-label="Open learning research dashboard"
				title="Learning research dashboard"
				aria-haspopup="dialog"
				aria-expanded={open}
				onClick={() => setOpen(true)}
			>
				<svg
					width="24"
					height="24"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					strokeWidth="2"
					strokeLinecap="round"
					strokeLinejoin="round"
					aria-hidden="true"
				>
					<path d="M4 3v17h17M8 16v-4m5 4V8m5 8V5" />
				</svg>
			</button>
			{open && (
				<Suspense fallback={null}>
					<ResearchDashboard
						learnerId={learnerId}
						onClose={() => setOpen(false)}
					/>
				</Suspense>
			)}
		</>
	);
}
