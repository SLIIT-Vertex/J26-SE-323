/**
 * Everything support left behind, counted after teardown. The server withdraws help only when
 * this receipt names the exact revisions and every count is zero.
 */
export type TeardownReceipt = {
	receipt_version: "pillam-teardown-receipt-v1";
	support_revision_id: string;
	manifest_revision_id: string;
	phaser_support_objects_remaining: number;
	dom_support_nodes_remaining: number;
	listeners_remaining: number;
	live_region_cleared: boolean;
	cached_solution_cleared: boolean;
};

export class SupportTeardownRegistry {
	private objects = new Set<{ destroy(): void }>();
	private listeners = new Set<() => void>();
	private cachedSolution: unknown = null;

	track(object: { destroy(): void }) {
		this.objects.add(object);
		return object;
	}
	listen(remove: () => void) {
		this.listeners.add(remove);
	}
	cache(solution: unknown) {
		this.cachedSolution = solution;
	}
	get liveCount() {
		return this.objects.size + this.listeners.size;
	}
	/** Destroy, then count what is still there. Counting before destroying proves nothing. */
	teardown(
		root: ParentNode | null,
		liveRegion: HTMLElement | null,
		revisions: { support: string; manifest: string },
	): TeardownReceipt {
		for (const object of this.objects) object.destroy();
		this.objects.clear();
		for (const remove of this.listeners) remove();
		this.listeners.clear();
		this.cachedSolution = null;
		if (liveRegion) liveRegion.textContent = "";
		const nodes = root?.querySelectorAll("[data-support-node]").length ?? 0;
		return {
			receipt_version: "pillam-teardown-receipt-v1",
			support_revision_id: revisions.support,
			manifest_revision_id: revisions.manifest,
			phaser_support_objects_remaining: this.objects.size,
			dom_support_nodes_remaining: nodes,
			listeners_remaining: this.listeners.size,
			live_region_cleared: (liveRegion?.textContent ?? "") === "",
			cached_solution_cleared: this.cachedSolution === null,
		};
	}
}
