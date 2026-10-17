import type { TelemetryBatch, TelemetryEvent } from "../api/generated";

interface QueueState {
	streams: Record<
		string,
		{
			nextSequence: number;
			events: Array<TelemetryEvent & { critical: boolean }>;
		}
	>;
}

export interface EncryptedStore {
	read(): Promise<QueueState | null>;
	write(state: QueueState): Promise<void>;
}

export interface EncryptionKeyProvider {
	getOrCreate(): Promise<CryptoKey>;
}

export class IndexedDbNonExtractableKeyProvider implements EncryptionKeyProvider {
	constructor(
		private readonly databaseName = "mindbridge-mobile-learning-keys-v1",
		private readonly keyId = "telemetry-queue-aes-gcm-v1",
	) {}

	async getOrCreate(): Promise<CryptoKey> {
		const database = await new Promise<IDBDatabase>((resolve, reject) => {
			const request = indexedDB.open(this.databaseName, 1);
			request.onupgradeneeded = () => request.result.createObjectStore("keys");
			request.onerror = () => reject(request.error);
			request.onsuccess = () => resolve(request.result);
		});
		try {
			const existing = await idbRequest<CryptoKey | undefined>(
				database.transaction("keys", "readonly").objectStore("keys").get(this.keyId),
			);
			if (existing) return existing;
			const key = await crypto.subtle.generateKey(
				{ name: "AES-GCM", length: 256 },
				false,
				["encrypt", "decrypt"],
			);
			await idbRequest(
				database
					.transaction("keys", "readwrite")
					.objectStore("keys")
					.put(key, this.keyId),
			);
			return key;
		} finally {
			database.close();
		}
	}
}

export class WebCryptoLocalStore implements EncryptedStore {
	constructor(
		private readonly dataKey = "mindbridge.mobile-learning.queue.v1",
		private readonly keyProvider: EncryptionKeyProvider =
			new IndexedDbNonExtractableKeyProvider(),
	) {}

	async read(): Promise<QueueState | null> {
		const encoded = localStorage.getItem(this.dataKey);
		if (!encoded) return null;
		const key = await this.keyProvider.getOrCreate();
		const { iv, ciphertext } = JSON.parse(encoded) as {
			iv: string;
			ciphertext: string;
		};
		const clear = await crypto.subtle.decrypt(
			{ name: "AES-GCM", iv: new Uint8Array(fromBase64(iv)) },
			key,
			fromBase64(ciphertext),
		);
		return JSON.parse(new TextDecoder().decode(clear)) as QueueState;
	}

	async write(state: QueueState): Promise<void> {
		const key = await this.keyProvider.getOrCreate();
		const iv = crypto.getRandomValues(new Uint8Array(12));
		const ciphertext = await crypto.subtle.encrypt(
			{ name: "AES-GCM", iv },
			key,
			new TextEncoder().encode(JSON.stringify(state)),
		);
		localStorage.setItem(
			this.dataKey,
			JSON.stringify({
				iv: toBase64(iv),
				ciphertext: toBase64(new Uint8Array(ciphertext)),
			}),
		);
	}
}

export class MemoryEncryptedStore implements EncryptedStore {
	state: QueueState | null = null;
	async read() {
		return this.state ? structuredClone(this.state) : null;
	}
	async write(state: QueueState) {
		this.state = structuredClone(state);
	}
}

export class EncryptedEventQueue {
	private state: QueueState = { streams: {} };
	private retryCount = 0;

	constructor(
		private readonly store: EncryptedStore,
		private readonly capacity = 200,
	) {}

	async initialize(): Promise<void> {
		this.state = (await this.store.read()) ?? this.state;
	}

	async enqueue(
		streamId: string,
		payload: Record<string, string | number | boolean>,
		critical = false,
	): Promise<TelemetryEvent | null> {
		if (Object.keys(payload).length > 8)
			throw new Error("PAYLOAD_OUT_OF_BOUNDS");
		const stream = this.stream(streamId);
		const criticalReserve = Math.min(20, this.capacity);
		if (!critical && stream.events.length >= this.capacity - criticalReserve)
			return null;
		if (stream.events.length >= this.capacity)
			throw new Error("CRITICAL_QUEUE_CAPACITY_EXCEEDED");
		const sequence = stream.nextSequence;
		stream.nextSequence += 1;
		const event = {
			event_id: crypto.randomUUID(),
			sequence,
			version: 1 as const,
			payload,
			client_occurred_at: new Date().toISOString(),
			critical,
		};
		stream.events.push(event);
		await this.store.write(this.state);
		return event;
	}

	takeBatch(streamId: string, limit = 50): TelemetryBatch | null {
		const events = this.stream(streamId).events.slice(0, Math.min(50, limit));
		if (!events[0]) return null;
		return {
			batch_id: events[0].event_id,
			first_sequence: events[0].sequence,
			events: events.map(
				({ critical: _critical, ...event }) => event,
			),
		};
	}

	async acknowledge(streamId: string, nextSequence: number): Promise<void> {
		const stream = this.stream(streamId);
		stream.events = stream.events.filter(
			(event) => event.sequence >= nextSequence,
		);
		this.retryCount = 0;
		await this.store.write(this.state);
	}

	async reconcileExpectedSequence(streamId: string, expected: number): Promise<void> {
		const stream = this.stream(streamId);
		stream.events = stream.events.filter(
			(event) => event.sequence >= expected,
		);
		if (stream.events[0] && stream.events[0].sequence !== expected) {
			throw new Error("UNRECOVERABLE_SEQUENCE_GAP");
		}
		await this.store.write(this.state);
	}

	nextBackoffMs(): number {
		const delay = Math.min(30_000, 500 * 2 ** this.retryCount);
		this.retryCount = Math.min(this.retryCount + 1, 6);
		return delay;
	}

	get pendingCount(): number {
		return Object.values(this.state.streams).reduce(
			(total, stream) => total + stream.events.length,
			0,
		);
	}
	pendingCountFor(streamId: string): number {
		return this.stream(streamId).events.length;
	}
	nextSequenceFor(streamId: string): number {
		return this.stream(streamId).nextSequence;
	}

	private stream(streamId: string) {
		if (!this.state.streams[streamId]) {
			this.state.streams[streamId] = { nextSequence: 1, events: [] };
		}
		return this.state.streams[streamId];
	}
}

function toBase64(bytes: Uint8Array): string {
	return btoa(String.fromCharCode(...bytes));
}

function fromBase64(value: string): ArrayBuffer {
	return Uint8Array.from(atob(value), (character) => character.charCodeAt(0))
		.buffer as ArrayBuffer;
}

function idbRequest<T>(request: IDBRequest<T>): Promise<T> {
	return new Promise((resolve, reject) => {
		request.onsuccess = () => resolve(request.result);
		request.onerror = () => reject(request.error);
	});
}
