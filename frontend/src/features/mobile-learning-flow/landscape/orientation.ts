import { ScreenOrientation } from "@capacitor/screen-orientation";

export type AppOrientation = "portrait" | "landscape";

/**
 * Locks the screen to one orientation. On the phone apps this always works; in a browser it works
 * only where the browser allows it (usually full screen on Android), so a failure is not an error:
 * the landscape stage then asks the child to turn the phone instead.
 */
export async function lockOrientation(
	orientation: AppOrientation,
): Promise<boolean> {
	try {
		await ScreenOrientation.lock({ orientation });
		return true;
	} catch {
		return false;
	}
}
