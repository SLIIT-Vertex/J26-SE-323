import {
	assertBridgeCommand,
	assertSceneEvent,
	type BridgeCommand,
	type SceneDomainEvent,
} from "./contracts";

export class MobileLearningBridge {
	private commandListeners = new Set<(command: BridgeCommand) => void>();
	private eventListeners = new Set<(event: SceneDomainEvent) => void>();

	command(command: BridgeCommand): void {
		assertBridgeCommand(command);
		for (const listener of this.commandListeners) listener(command);
	}

	emit(event: SceneDomainEvent): void {
		assertSceneEvent(event);
		for (const listener of this.eventListeners) listener(event);
	}

	onCommand(listener: (command: BridgeCommand) => void): () => void {
		this.commandListeners.add(listener);
		return () => this.commandListeners.delete(listener);
	}

	onEvent(listener: (event: SceneDomainEvent) => void): () => void {
		this.eventListeners.add(listener);
		return () => this.eventListeners.delete(listener);
	}

	dispose(): void {
		this.commandListeners.clear();
		this.eventListeners.clear();
	}

	get listenerCount(): number {
		return this.commandListeners.size + this.eventListeners.size;
	}
}
