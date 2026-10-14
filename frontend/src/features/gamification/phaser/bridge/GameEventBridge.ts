export type BridgeCommand =
  | { type: "LOAD_MANIFEST"; manifest: { item_id: string; options: { option_id: string }[] } }
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
