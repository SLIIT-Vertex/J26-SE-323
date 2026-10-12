# 07 — Frontend (React + Capacitor) and testing on an iPhone

## 1. What this component adds to the app

The main app shell, login and design system belong to teammates. This component supplies these screens/modules (build them as a self-contained feature folder `src/features/papers` so they drop into the shared app):

| Screen | Purpose |
| --- | --- |
| **Papers list** | A child's papers, newest first, with status chips. |
| **Create paper** | Choose number of questions and minutes (defaults 15 / 25); shows progress while generating; then "Open PDF to print". |
| **Upload pages** | One row per page: status (not uploaded, checking, ready, retake needed), "Take photo" / "Choose photo" button, clear retake messages. |
| **Review unclear answers** | Shows the cropped image, what the system read, and lets the parent decide. Never shows correct/wrong before the decision. |
| **Mastery** | 30 skills in four groups (aptitude, maths, language, environment); unknown shown as "Not enough questions yet"; plain-language note under the title: "Chance of answering a medium paper question correctly". |

## 2. Project setup

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install @capacitor/core @capacitor/camera @capacitor/share @capacitor/browser \
            @tanstack/react-query react-router-dom
npm install -D @capacitor/cli openapi-typescript vitest
npm install @capacitor/ios @capacitor/android
npx cap init MindBridge <your.bundle.id> --web-dir=dist     # pick your own reverse-domain id
npm run build
npx cap add ios
npx cap add android
npx cap sync
```

Configuration: `VITE_API_BASE_URL` (see the testing options below). Use the TypeScript types generated from the backend's `openapi.json` for every API call. Use TanStack Query for fetching, with polling (`refetchInterval: 2000`) on `GET /submissions/{id}` while `status === 'uploaded'`.

Fonts: use *Noto Sans Sinhala* for Sinhala UI text. The PDF is generated on the server; the app only opens it.

## 3. Key behaviours

### Taking a photo
```ts
import { Camera, CameraResultType, CameraSource } from '@capacitor/camera';
import { Capacitor } from '@capacitor/core';

async function takePagePhoto(): Promise<Blob> {
  if (Capacitor.isNativePlatform()) {
    const photo = await Camera.getPhoto({
      quality: 90, allowEditing: false, correctOrientation: true,
      resultType: CameraResultType.Uri, source: CameraSource.Camera,
    });
    return await (await fetch(photo.webPath!)).blob();
  }
  // Browser fallback (iPhone Safari, desktop): hidden <input type="file" accept="image/*" capture="environment">
  return pickFileFromInput();
}
```
- Upload with `FormData` (`image`) to `POST /papers/{id}/pages/{page}/photo`. Do not resize aggressively on the client (the backend needs detail for handwriting); a 12-megapixel JPEG at quality 90 is fine.
- Before the first photo show a short guide image: "Place the page flat. All four black squares must be inside the picture. Good light, no shadow across the page. Hold the phone straight above the page."
- Map failure reasons to friendly text: `markers_missing` → "We could not see all four black squares. Please retake and keep every corner in the picture."; `blurry` → "The photo is blurry. Hold steady and retake."; `wrong_paper` / `wrong_page` → "This looks like a different paper or page."

### Opening the PDF for printing
Use `Browser.open({ url: pdf_url })` (opens a system browser view where the parent can use Share → Print/AirPrint) or `Share.share({ url })`. Remind the parent: *Print at Actual size (100%)*.

### Review screen
- MCQ item: show the crop, then buttons for each option label plus "No answer". Pre-select nothing.
- Short item: show the crop, a text field (Sinhala keyboard works), and "No answer".
- Submit all decisions with `POST /submissions/{id}/confirm`.

### Mastery screen
Call `GET /students/{id}/mastery`. Show bars for known skills; for `null` skills show "Not enough questions yet (n answered)". Do not show 0.5 or any placeholder number for them.

## 4. Backend settings the app needs

- CORS must allow the origins: `http://localhost:5173` (Vite), `http://localhost` and `capacitor://localhost` (the iOS app), `https://localhost` (Android app default), and your laptop's LAN address if you test through it. Set `CORS_ORIGINS` accordingly.
- The iPhone WebView blocks plain `http://` calls to non-local servers (App Transport Security). See the testing options.

## 5. Testing on an iPhone — what is possible

**Short answer: yes.** React + Capacitor apps can run on an iPhone. What changes is whether you have a Mac.

### Option A — you have a Mac (or can borrow/use a lab Mac): real native app on your iPhone
Requirements: macOS, Xcode (free from the App Store), an Apple ID, a USB cable.

1. `npm run build && npx cap sync ios && npx cap open ios` (opens Xcode).
2. In Xcode: select the *App* target → *Signing & Capabilities* → tick *Automatically manage signing* → choose your Apple ID as *Team* (a free "Personal Team" works) → give the bundle id a unique value.
3. On the iPhone: *Settings → Privacy & Security → Developer Mode* → on (restart). Connect with USB, tap *Trust*.
4. Choose your iPhone as the run destination in Xcode and press Run. First time: on the iPhone open *Settings → General → VPN & Device Management* and trust your developer profile.
5. Live reload while developing: `npx cap run ios --livereload --external` (the app loads from your laptop's dev server on the same Wi-Fi). If a flag differs in your version, check `npx cap run --help`.

Limits of a free Apple ID: the installed app **expires after 7 days** (just run again from Xcode) and you can have only a few such apps on a device. TestFlight or the App Store need the paid Apple Developer Program (about US$99 per year); you do not need it just to test on your own iPhone.

`ios/App/App/Info.plist` must contain usage texts, otherwise the camera crashes the app:
```xml
<key>NSCameraUsageDescription</key><string>MindBridge uses the camera to photograph answered paper pages.</string>
<key>NSPhotoLibraryUsageDescription</key><string>MindBridge can upload a photo of a paper page from your photos.</string>
<key>NSLocalNetworkUsageDescription</key><string>Development only: connects to the MindBridge test server on your network.</string>
```

### Option B — no Mac: test the web version in iPhone Safari
Windows and Linux **cannot build the iOS app** (Xcode only runs on macOS). You can still test almost everything:

1. Start the backend with `--host 0.0.0.0` and the frontend with `npm run dev -- --host`.
2. Put the iPhone and laptop on the same Wi-Fi and open `http://<laptop-ip>:5173` in Safari.
3. Safari only allows live camera access (`getUserMedia`) on **HTTPS**. The file-input approach above (`capture="environment"`) works without it, and it opens the iPhone camera app directly, which is exactly what you need for page photos. For an HTTPS URL during development use a free tunnel such as `cloudflared tunnel --url http://localhost:5173`, and give the backend its own tunnel as `VITE_API_BASE_URL`.
4. Optional: "Add to Home Screen" in Safari makes it behave like an installed web app.

Cloud macOS build services (Codemagic, GitHub Actions macOS runners) can compile the iOS app without owning a Mac, but installing the result on a real iPhone still requires signing with an Apple Developer account, so they are a poor fit for early testing.

### Option C — Android (if a teammate has an Android phone or you use Android Studio)
`npx cap run android` works on Windows, Linux and macOS. Good for testing the Capacitor-specific code (camera plugin, share) when no Mac is available.

### Which API address the iPhone app should use
| Situation | `VITE_API_BASE_URL` |
| --- | --- |
| Native app on iPhone, backend on laptop | An HTTPS tunnel URL (recommended). Using `http://<laptop-ip>:8000` also needs an App Transport Security exception for local networking in `Info.plist` and the local-network permission prompt; use the tunnel if it fails. |
| Safari testing, same Wi-Fi | `http://<laptop-ip>:8000` (needs CORS entry for the page origin) |
| Production | The deployed HTTPS URL |

## 6. Tests (Vitest)
- API client: status mapping and failure-reason text.
- Review screen: cannot submit until every flagged item has a decision; no correctness shown.
- Mastery screen: `null` skills render the "not enough questions" state.
- Upload screen: polling stops on `graded`, `needs_review`, `failed_alignment`.
