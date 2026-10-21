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
				aria-haspopup="dialog"
				aria-expanded={open}
				onClick={() => setOpen(true)}
			>
				Research
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
