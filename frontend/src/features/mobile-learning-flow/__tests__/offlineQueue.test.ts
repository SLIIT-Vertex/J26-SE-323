import { describe, expect, it } from "vitest";
import {
	EncryptedEventQueue,
	MemoryEncryptedStore,
	WebCryptoLocalStore,
	type EncryptionKeyProvider,
} from "../offline/EncryptedEventQueue";

const stream = "episode-1";

class TestKeyProvider implements EncryptionKeyProvider {
	private key?: CryptoKey;
	async getOrCreate() {
		this.key ??= await crypto.subtle.generateKey(
			{ name: "AES-GCM", length: 256 },
			false,
			["encrypt", "decrypt"],
		);
		return this.key;
	}
}

describe("encrypted offline event queue contract", () => {
	it("preserves event IDs and sequence across restart and duplicate retry", async () => {
		const store = new MemoryEncryptedStore();
		const first = new EncryptedEventQueue(store);
		await first.initialize();
		const event = await first.enqueue(stream, { event_type: "answer_submitted" }, true);
		const batch = first.takeBatch(stream);
		const restarted = new EncryptedEventQueue(store);
		await restarted.initialize();
		expect(restarted.takeBatch(stream)?.events[0]).toEqual(batch?.events[0]);
		expect(event).not.toBeNull();
		expect(restarted.takeBatch(stream)?.batch_id).toBe(batch?.batch_id);
		expect(restarted.takeBatch(stream)?.events[0]?.event_id).toBe(event?.event_id);
		await restarted.acknowledge(stream, 2);
		expect(restarted.pendingCount).toBe(0);
		expect(restarted.nextSequenceFor(stream)).toBe(2);
	});

	it("preserves critical events before optional summaries and detects gaps", async () => {
		const queue = new EncryptedEventQueue(new MemoryEncryptedStore(), 2);
		await queue.initialize();
		await queue.enqueue(stream, { event_type: "object_selected" });
		await queue.enqueue(stream, { event_type: "answer_submitted" }, true);
		await queue.enqueue(stream, { event_type: "withdrawal_acknowledged" }, true);
		expect(
			queue.takeBatch(stream)?.events.map((event) => event.payload.event_type),
		).toEqual(["answer_submitted", "withdrawal_acknowledged"]);
		expect(queue.takeBatch(stream)?.events.map((event) => event.sequence)).toEqual([
			1, 2,
		]);
		await expect(queue.reconcileExpectedSequence(stream, 0)).rejects.toThrow(
			"UNRECOVERABLE_SEQUENCE_GAP",
		);
		expect([500, 1000, 2000, 4000, 8000, 16000, 30000]).toEqual(
			Array.from({ length: 7 }, () => queue.nextBackoffMs()),
		);
	});

	it("encrypts persisted event payloads when WebCrypto storage is available", async () => {
		localStorage.clear();
		const keys = new TestKeyProvider();
		const queue = new EncryptedEventQueue(
			new WebCryptoLocalStore("mobile-learning-test-data", keys),
		);
		await queue.initialize();
		await queue.enqueue(stream, { event_type: "answer_submitted" }, true);
		const persisted = localStorage.getItem("mobile-learning-test-data");
		expect(persisted).toContain("ciphertext");
		expect(persisted).not.toContain("answer_submitted");
		const restored = new EncryptedEventQueue(
			new WebCryptoLocalStore("mobile-learning-test-data", keys),
		);
		await restored.initialize();
		expect(restored.takeBatch(stream)?.events[0]?.payload.event_type).toBe(
			"answer_submitted",
		);
		expect(localStorage.getItem("mobile-learning-test-key")).toBeNull();
	});
});
