import type { BridgeCommand, GameEventBridge } from "../../bridge/GameEventBridge";

/** Domain commands only. Pointer streams stay inside Phaser and never cross this bridge. */
export class BuildManipulateSceneController {
  manifestId: string | null = null;
  supportVisible = false;
  disposed = false;
  paused = false;

  constructor(private readonly bridge: GameEventBridge) {}

  apply(command: BridgeCommand): void {
    if (command.type === "DISPOSE") {
      this.disposed = true;
      this.supportVisible = false;
      return;
    }
    if (this.disposed) return;
    if (command.type === "LOAD_MANIFEST") this.manifestId = command.manifest.item_id;
    if (command.type === "PAUSE") this.paused = true;
    if (command.type === "PRESENT_SUPPORT") this.supportVisible = true;
    if (command.type === "WITHDRAW_SUPPORT") this.supportVisible = false;
    if (command.type === "PRESENT_VERIFICATION") this.supportVisible = false;
  }

  select(optionId: string): void {
    if (this.disposed || this.supportVisible) return;
    this.bridge.emit({ type: "option_changed", optionId });
  }
}
