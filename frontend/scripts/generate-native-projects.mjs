import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const check = process.argv.includes("--check");
const capCli = resolve(frontend, "node_modules/@capacitor/cli/bin/capacitor");

for (const platform of ["android", "ios"]) {
  const directory = resolve(frontend, platform);
  if (!existsSync(directory)) {
    if (check) throw new Error(`${platform} project is missing; run npm run native:generate`);
    const result = spawnSync(process.execPath, [capCli, "add", platform], {
      cwd: frontend,
      stdio: "inherit",
    });
    if (result.status !== 0) process.exit(result.status ?? 1);
  }
}

const androidPath = resolve(frontend, "android/app/src/main/AndroidManifest.xml");
let android = readFileSync(androidPath, "utf8");
if (!android.includes('android:screenOrientation="portrait"')) {
  android = android.replace(
    'android:launchMode="singleTask"',
    'android:launchMode="singleTask"\n            android:screenOrientation="portrait"',
  );
}

const iosPath = resolve(frontend, "ios/App/App/Info.plist");
let ios = readFileSync(iosPath, "utf8");
ios = replacePlistArray(ios, "UISupportedInterfaceOrientations", [
  "UIInterfaceOrientationPortrait",
]);
ios = replacePlistArray(ios, "UISupportedInterfaceOrientations~ipad", [
  "UIInterfaceOrientationPortrait",
  "UIInterfaceOrientationPortraitUpsideDown",
]);
ios = ensurePlistEntry(
  ios,
  "NSLocalNetworkUsageDescription",
  "MindBridge connects to the local development server while the app is being tested.",
);
ios = ensurePlistDictionary(ios, "NSAppTransportSecurity", [
  ["NSAllowsLocalNetworking", "<true/>"],
]);
ios = ensurePlistDictionary(ios, "UIApplicationSceneManifest", [
  ["UIApplicationSupportsMultipleScenes", "<false/>"],
  [
    "UISceneConfigurations",
    `<dict>
			<key>UIWindowSceneSessionRoleApplication</key>
			<array>
				<dict>
					<key>UISceneConfigurationName</key>
					<string>Default Configuration</string>
					<key>UISceneDelegateClassName</key>
					<string>$(PRODUCT_MODULE_NAME).SceneDelegate</string>
					<key>UISceneStoryboardFile</key>
					<string>Main</string>
				</dict>
			</array>
		</dict>`,
  ],
]);

const appDelegatePath = resolve(frontend, "ios/App/App/AppDelegate.swift");
const appDelegate = readFileSync(appDelegatePath, "utf8");
if (
  !appDelegate.includes("configurationForConnecting") ||
  !appDelegate.includes("class SceneDelegate: UIResponder, UIWindowSceneDelegate")
) {
  throw new Error("iOS scene lifecycle configuration drifted");
}

if (check) {
  if (readFileSync(androidPath, "utf8") !== android)
    throw new Error("Android portrait configuration drifted");
  if (readFileSync(iosPath, "utf8") !== ios)
    throw new Error("iOS portrait configuration drifted");
} else {
  writeFileSync(androidPath, android);
  writeFileSync(iosPath, ios);
}

function replacePlistArray(source, key, values) {
  const body = values.map((value) => `\t\t<string>${value}</string>`).join("\n");
  const pattern = new RegExp(
    `(\\t<key>${escapeRegExp(key)}</key>\\n\\t<array>)[\\s\\S]*?(\\n\\t</array>)`,
  );
  if (!pattern.test(source)) throw new Error(`Missing iOS orientation key: ${key}`);
  return source.replace(pattern, `$1\n${body}$2`);
}

function ensurePlistEntry(source, key, value) {
  if (source.includes(`<key>${key}</key>`)) return source;
  return source.replace(
    "</dict>\n</plist>",
    `\t<key>${key}</key>\n\t<string>${value}</string>\n</dict>\n</plist>`,
  );
}

function ensurePlistDictionary(source, key, entries) {
  if (source.includes(`<key>${key}</key>`)) return source;
  const body = entries
    .map(([entryKey, entryValue]) => `\t\t<key>${entryKey}</key>\n\t\t${entryValue}`)
    .join("\n");
  return source.replace(
    "</dict>\n</plist>",
    `\t<key>${key}</key>\n\t<dict>\n${body}\n\t</dict>\n</dict>\n</plist>`,
  );
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
