import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, extname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const dist = resolve(dirname(fileURLToPath(import.meta.url)), "../dist");
const files = walk(dist).filter((path) =>
	[".html", ".js", ".css"].includes(extname(path)),
);
const artifact = files.map((path) => readFileSync(path, "utf8")).join("\n");
const required = [
	"mobile-shell",
	"ස්ථාන අගය සොයා ගණක රාමුව හදමු",
	"සමාන බෙදීමේ මැදිරිය",
	"කාල පලතුරු වත්ත",
	"දහයෙන් මෝසෙයික්",
	"ඔබම උත්සාහ කරන්න",
	"තාවකාලික උදව්",
	"දැන් අලුත් එකක් ඔබම උත්සාහ කරන්න",
];
const forbidden = [
	"Shared foundation",
	"Grade 4–5",
	"#/inspector",
	"EpisodeInspector",
	"#/build",
	"4 ශ්‍රේණිය",
	"தமிழ்",
	"width:min(100%,430px)",
	"0 0 0 9px #211e35",
];
for (const token of required) {
	if (!artifact.includes(token))
		throw new Error(`Built mobile-learning shell token missing: ${token}`);
}
for (const token of forbidden) {
	if (artifact.includes(token))
		throw new Error(`Legacy child artifact token present: ${token}`);
}
process.stdout.write(
	`mobile-learning artifact inspection passed (${files.length} files).\n`,
);

function walk(path) {
	return readdirSync(path).flatMap((entry) => {
		const child = resolve(path, entry);
		return statSync(child).isDirectory() ? walk(child) : [child];
	});
}
