export type BridgeCommand =
	| {
			type: "LOAD_MANIFEST";
			manifest: { item_id: string; options: { option_id: string }[] };
	  }
	| { type: "PAUSE" }
	| { type: "PRESENT_SUPPORT" }
	| { type: "WITHDRAW_SUPPORT" }
	| { type: "PRESENT_VERIFICATION" }
	| { type: "DISPOSE" };

export type BridgeEvent = { type: "option_changed"; optionId: string };

export class GameEventBridge {
	private listeners = new Set<(event: BridgeEvent) => void>();

	emit(event: BridgeEvent): void {
		for (const listener of this.listeners) listener(event);
	}

	subscribe(listener: (event: BridgeEvent) => void): () => void {
		this.listeners.add(listener);
		return () => this.listeners.delete(listener);
	}
}

/**
 * A typed two-way channel between React and one scene. React sends commands (the model to
 * draw); the scene sends semantic events (what the child did). Scenes never call APIs.
 */
export class SceneBridge<Command, Event> {
	private toScene = new Set<(command: Command) => void>();
	private toReact = new Set<(event: Event) => void>();
	private last: Command | null = null;

	send(command: Command): void {
		this.last = command;
		for (const listener of this.toScene) listener(command);
	}

	onCommand(listener: (command: Command) => void): () => void {
		this.toScene.add(listener);
		if (this.last !== null) listener(this.last);
		return () => this.toScene.delete(listener);
	}

	emit(event: Event): void {
		for (const listener of this.toReact) listener(event);
	}

	onEvent(listener: (event: Event) => void): () => void {
		this.toReact.add(listener);
		return () => this.toReact.delete(listener);
	}

	get listenerCount(): number {
		return this.toScene.size + this.toReact.size;
	}

	clear(): void {
		this.toScene.clear();
		this.toReact.clear();
		this.last = null;
	}
}
