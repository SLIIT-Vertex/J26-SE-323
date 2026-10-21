import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { dirname, extname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const root = resolve(frontend, "..");
const temporary = mkdtempSync(
	join(tmpdir(), "mindbridge-mobile-learning-e2e-"),
);
const python = resolve(root, "backend/.venv/bin/python");
const chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const processes = [];

try {
	const backend = spawn(
		python,
		["backend/tools/mobile_learning_e2e_server.py"],
		{
			cwd: root,
			env: {
				...process.env,
				PYTHONPATH: resolve(root, "backend"),
				DATABASE_URL: `sqlite:///${join(temporary, "mobile-learning.sqlite")}`,
				FRONTEND_ORIGIN: "http://127.0.0.1:4174",
				MOBILE_LEARNING_E2E_RATE_LIMIT: "500",
			},
			stdio: ["ignore", "inherit", "inherit"],
		},
	);
	processes.push(backend);
	await waitForUrl("http://127.0.0.1:8765/api/v1/health");

	for (const condition of ["baseline", "proposed"]) {
		const learnerId =
			condition === "baseline"
				? "00000000-0000-4000-8000-000000000721"
				: "00000000-0000-4000-8000-000000000722";
		build(condition, learnerId);
		const web = serveBuiltApp();
		try {
			await waitForUrl("http://127.0.0.1:4174");
			await runBrowserFlow(condition);
		} finally {
			await new Promise((resolveClose) => web.close(resolveClose));
		}
	}
	process.stdout.write(
		"mobile-learning real-backend E2E passed in baseline and proposed modes.\n",
	);
} finally {
	for (const processHandle of processes) processHandle.kill("SIGTERM");
}

function build(condition, learnerId) {
	const result = spawnSync("npm", ["run", "build:web"], {
		cwd: frontend,
		env: {
			...process.env,
			VITE_MOBILE_LEARNING_CONDITION: condition,
			VITE_MOBILE_LEARNING_LEARNER_ID: learnerId,
			VITE_API_URL: "http://127.0.0.1:8765/api/v1",
		},
		stdio: "inherit",
	});
	if (result.status !== 0) throw new Error(`Build failed for ${condition}`);
}

function serveBuiltApp() {
	const dist = resolve(frontend, "dist");
	const contentTypes = new Map([
		[".html", "text/html; charset=utf-8"],
		[".js", "text/javascript; charset=utf-8"],
		[".css", "text/css; charset=utf-8"],
		[".svg", "image/svg+xml"],
	]);
	const server = createServer((request, response) => {
		const requested =
			request.url === "/" ? "/index.html" : request.url.split("?")[0];
		let path = resolve(dist, `.${requested}`);
		if (!path.startsWith(dist) || !existsFile(path))
			path = resolve(dist, "index.html");
		response.setHeader(
			"Content-Type",
			contentTypes.get(extname(path)) ?? "application/octet-stream",
		);
		response.end(readFileSync(path));
	});
	server.listen(4174, "127.0.0.1");
	return server;
}

async function runBrowserFlow(condition) {
	const port = condition === "baseline" ? 9223 : 9224;
	const browser = spawn(
		chrome,
		[
			"--headless=new",
			`--remote-debugging-port=${port}`,
			`--user-data-dir=${join(temporary, `chrome-${condition}`)}`,
			"--no-first-run",
			"--disable-background-networking",
			"--disable-default-apps",
			"http://127.0.0.1:4174",
		],
		{ stdio: "ignore" },
	);
	processes.push(browser);
	try {
		const targets = await waitForJson(`http://127.0.0.1:${port}/json`);
		const page = targets.find((target) => target.type === "page");
		if (!page?.webSocketDebuggerUrl)
			throw new Error("Chrome page target unavailable");
		const cdp = await connectCdp(page.webSocketDebuggerUrl);
		await cdp.call("Runtime.enable");
		await evaluate(
			cdp,
			`(() => { window.__mindbridgeE2eErrors = []; addEventListener('error', (event) => window.__mindbridgeE2eErrors.push(String(event.error || event.message))); addEventListener('unhandledrejection', (event) => window.__mindbridgeE2eErrors.push(String(event.reason))); const original = console.error; console.error = (...values) => { window.__mindbridgeE2eErrors.push(values.map(String).join(' ')); original(...values); }; return true; })()`,
		);
		await cdp.call("Emulation.setDeviceMetricsOverride", {
			width: 320,
			height: 568,
			deviceScaleFactor: 2,
			mobile: true,
		});
		await cdp.call("Emulation.setEmulatedMedia", {
			features: [{ name: "prefers-reduced-motion", value: "reduce" }],
		});
		await waitFor(
			cdp,
			`document.querySelector('main')?.getAttribute('lang') === 'si'`,
		);
		await verifyViewportAndAccessibility(cdp, "small portrait");
		await clickText(cdp, "මගේ පැතිකඩට");
		await waitForText(cdp, "කුඩා පියවර");
		await clickText(cdp, "මඟ හරින්න");
		await waitForText(cdp, "ආයුබෝවන්");
		await clickText(cdp, "ඉදිරියට යමු");
		await clickText(cdp, "මගේ ගමන අරඹන්න");
		await cdp.call("Emulation.setDeviceMetricsOverride", {
			width: 568,
			height: 320,
			deviceScaleFactor: 2,
			mobile: true,
		});
		await verifyViewportAndAccessibility(cdp, "resized landscape");
		await cdp.call("Emulation.setDeviceMetricsOverride", {
			width: 320,
			height: 568,
			deviceScaleFactor: 2,
			mobile: true,
		});
		await clickText(cdp, "ක්‍රීඩා");
		await waitForText(cdp, "ගණිතය");
		if (process.env.MOBILE_LEARNING_E2E_CONVERSATION_ONLY === "1") {
			await clickText(cdp, "ඉංග්‍රීසි");
			await clickText(cdp, "Useful Expressions & Conversation Language");
			await runConversationStreetCoverage(cdp, condition);
			await assertBrowserHealth(cdp, `${condition} Conversation Street`);
			cdp.close();
			return;
		}
		if (process.env.MOBILE_LEARNING_E2E_CLASSROOM_LANGUAGE_ONLY === "1") {
			await clickText(cdp, "ඉංග්‍රීසි");
			await clickText(cdp, "Classroom Language");
			await runClassroomLanguageCoverage(cdp, condition);
			await assertBrowserHealth(cdp, `${condition} Classroom Language Live`);
			cdp.close();
			return;
		}
		if (process.env.MOBILE_LEARNING_E2E_HERITAGE_ONLY === "1") {
			await clickText(cdp, "ඉංග්‍රීසි");
			await clickText(cdp, "Our Past");
			await runHeritageMuseumCoverage(cdp, condition);
			await assertBrowserHealth(cdp, `${condition} Heritage Museum Quest`);
			cdp.close();
			return;
		}
		if (process.env.MOBILE_LEARNING_E2E_INFORMATION_ONLY === "1") {
			await clickText(cdp, "ඉංග්‍රීසි");
			await clickText(cdp, "Man & Information");
			await runInformationStationCoverage(cdp, condition);
			await assertBrowserHealth(cdp, `${condition} Information Station`);
			cdp.close();
			return;
		}
		if (process.env.MOBILE_LEARNING_E2E_WORKPLACE_ONLY === "1") {
			await clickText(cdp, "ඉංග්‍රීසි");
			await clickText(cdp, "Ways of Making work Easy");
			await runWorkplaceLinkCoverage(cdp, condition);
			await assertBrowserHealth(cdp, `${condition} Workplace Link City`);
			cdp.close();
			return;
		}
		if (process.env.MOBILE_LEARNING_E2E_EARTH_SKY_ONLY === "1") {
			await clickText(cdp, "ඉංග්‍රීසි");
			await clickText(cdp, "Earth & Sky");
			await runEarthSkyCoverage(cdp, condition);
			await assertBrowserHealth(cdp, `${condition} Earth & Sky Explorer`);
			cdp.close();
			return;
		}
		if (process.env.MOBILE_LEARNING_E2E_BLUEPRINT_ONLY === "1") {
			await clickText(cdp, "ඉංග්‍රීසි");
			await clickText(cdp, "Changes we can do");
			await runBlueprintCoverage(cdp, condition);
			await assertBrowserHealth(cdp, `${condition} Blueprint Quest`);
			cdp.close();
			return;
		}
		if (process.env.MOBILE_LEARNING_E2E_BLOOM_ONLY === "1") {
			await clickText(cdp, "ඉංග්‍රීසි");
			await clickText(cdp, "Home Garden");
			await runBloomBuilderCoverage(cdp, condition);
			await assertBrowserHealth(cdp, `${condition} Bloom Builder Garden`);
			cdp.close();
			return;
		}
		if (process.env.MOBILE_LEARNING_E2E_WARDROBE_ONLY === "1") {
			await clickText(cdp, "ඉංග්‍රීසි");
			await clickText(cdp, "Safety & protection");
			await runRainbowWardrobeCoverage(cdp, condition);
			await assertBrowserHealth(cdp, `${condition} Rainbow Wardrobe`);
			cdp.close();
			return;
		}
		if (process.env.MOBILE_LEARNING_E2E_FAMILY_ONLY === "1") {
			await clickText(cdp, "ඉංග්‍රීසි");
			await clickText(cdp, "Human Behaviour");
			await runFamilyConstellationCoverage(cdp, condition);
			await assertBrowserHealth(cdp, `${condition} Family Word Constellation`);
			cdp.close();
			return;
		}
		if (process.env.MOBILE_LEARNING_E2E_TRANSPORT_ONLY === "1") {
			await clickText(cdp, "ඉංග්‍රීසි");
			await clickText(cdp, "Transport");
			await runTransitTerminalCoverage(cdp, condition);
			await assertBrowserHealth(cdp, `${condition} Transit Terminal`);
			cdp.close();
			return;
		}
		if (process.env.MOBILE_LEARNING_E2E_WATER_ONLY === "1") {
			await clickText(cdp, "ඉංග්‍රීසි");
			await clickText(cdp, "Water");
			await runWaterWorksCoverage(cdp, condition);
			await assertBrowserHealth(cdp, `${condition} Water Works`);
			cdp.close();
			return;
		}
		if (process.env.MOBILE_LEARNING_E2E_FOOD_ONLY === "1") {
			await clickText(cdp, "ඉංග්‍රීසි");
			await clickText(cdp, "Our food");
			await runIslandFoodCoverage(cdp, condition);
			await assertBrowserHealth(cdp, `${condition} Island Food Festival`);
			cdp.close();
			return;
		}
		if (process.env.MOBILE_LEARNING_E2E_OBJECTS_ONLY === "1") {
			await clickText(cdp, "ඉංග්‍රීසි");
			await clickText(cdp, "What we use");
			await runEverydayObjectCoverage(cdp, condition);
			await assertBrowserHealth(cdp, `${condition} Everyday Object Quest`);
			cdp.close();
			return;
		}
		if (process.env.MOBILE_LEARNING_E2E_WILDLIFE_ONLY === "1") {
			await clickText(cdp, "ඉංග්‍රීසි");
			await clickText(cdp, "Animals around us");
			await runWildlifeRangerCoverage(cdp, condition);
			await assertBrowserHealth(cdp, `${condition} Wildlife Ranger`);
			cdp.close();
			return;
		}
		if (process.env.MOBILE_LEARNING_E2E_PLANT_ONLY === "1") {
			await clickText(cdp, "ඉංග්‍රීසි");
			await clickText(cdp, "Plants, Trees and Creepers");
			await runPlantExplorerCoverage(cdp, condition);
			await assertBrowserHealth(cdp, `${condition} Plant Explorer`);
			cdp.close();
			return;
		}
		if (process.env.MOBILE_LEARNING_E2E_SRI_LANKA_ONLY === "1") {
			await clickText(cdp, "ඉංග්‍රීසි");
			await clickText(cdp, "We are Sri Lankans");
			await runSriLankaDiscoveryCoverage(cdp, condition);
			await assertBrowserHealth(cdp, `${condition} Sri Lanka Discovery`);
			cdp.close();
			return;
		}
		if (process.env.MOBILE_LEARNING_E2E_ENGLISH_ONLY === "1") {
			await clickText(cdp, "ඉංග්‍රීසි");
			await clickText(cdp, "Our Good Behaviour");
			await runClassroomActionCoverage(cdp, condition);
			await assertBrowserHealth(cdp, `${condition} English`);
			cdp.close();
			return;
		}
		await clickText(cdp, "ගණිතය");
		await waitForText(cdp, "සංඛ්‍යා");
		await clickText(cdp, "සංඛ්‍යා");
		await runNumberWorldCoverage(cdp, condition);
		await clickText(cdp, "ආපසු");
		await clickText(cdp, "එකතු කිරීම");
		await runAdditionAdventureCoverage(cdp, condition);
		await clickText(cdp, "ආපසු");
		await clickText(cdp, "සංඛ්‍යා රටා");
		await runNumberPatternCoverage(cdp, condition);
		await clickText(cdp, "ආපසු");
		await clickText(cdp, "අඩු කිරීම");
		await runSubtractionCoverage(cdp, condition);
		await clickText(cdp, "ආපසු");
		await clickText(cdp, "ගුණ කිරීම");
		await runMultiplicationCoverage(cdp);
		await clickText(cdp, "ආපසු");
		await clickText(cdp, "කාලය");
		await runTimeAdventureCoverage(cdp);
		await clickText(cdp, "ආපසු");
		await clickText(cdp, "මුදල්");
		await runMoneyAdventureCoverage(cdp);
		await clickText(cdp, "ආපසු");
		await clickText(cdp, "පරිමාව හා ධාරිතාව");
		await runCapacityAdventureCoverage(cdp);
		await clickText(cdp, "ආපසු");
		await clickText(cdp, "බර මැනීම");
		await runMassAdventureCoverage(cdp);
		await clickText(cdp, "ආපසු");
		await clickText(cdp, "ආපසු");
		await clickText(cdp, "ඉංග්‍රීසි");
		await clickText(cdp, "Our Good Behaviour");
		await runClassroomActionCoverage(cdp, condition);
		await clickText(cdp, "ආපසු");
		await clickText(cdp, "ආපසු");
		await assertBrowserHealth(cdp, condition);
		cdp.close();
	} finally {
		browser.kill("SIGTERM");
	}
}

async function runClassroomActionCoverage(cdp, condition) {
	await waitForText(cdp, "Action Mirror");
	await clickText(cdp, "Action Mirror");
	await waitForSelector(cdp, ".classroom-action-quest .pose-controls");
	const command = await evaluate(
		cdp,
		"document.querySelector('.caq-command strong')?.textContent?.trim()",
	);
	const correctLabels = {
		Bend: "Bend",
		"Stretch your arms": "Stretch your arms",
		"Put your arms down": "Put your arms down",
		"Stand straight": "Stand straight",
		"Turn around": "Turn around",
		"Sit down": "Sit down",
	};
	const correctLabel = correctLabels[command];
	if (!correctLabel) throw new Error(`Unknown classroom command: ${command}`);
	await evaluate(
		cdp,
		`(() => { const correct = ${JSON.stringify(correctLabel)}; const button = [...document.querySelectorAll('.pose-controls button')].find((node) => !node.textContent.includes(correct)); button.click(); return true; })()`,
	);
	await clickText(cdp, "Check my action");
	await waitForSelector(cdp, ".caq-support");
	for (let step = 0; step < 8; step += 1) {
		const label = await evaluate(
			cdp,
			"document.querySelector('.caq-support button')?.textContent?.trim()",
		);
		await clickText(cdp, label);
		if (label === "Now I will try alone") break;
	}
	await waitForSelector(cdp, ".classroom-action-quest .pose-controls");
	const retryCommand = await evaluate(
		cdp,
		"document.querySelector('.caq-command strong')?.textContent?.trim()",
	);
	const retryLabel = correctLabels[retryCommand];
	if (!retryLabel) throw new Error(`Unknown retry command: ${retryCommand}`);
	await clickText(cdp, retryLabel);
	await clickText(cdp, "Check my action");
	await waitForText(cdp, "Great action!");
	const episodeUrl = await evaluate(
		cdp,
		`performance.getEntriesByType('resource').map((entry) => entry.name).filter((url) => url.includes('/episodes/') && url.endsWith('/after')).at(-1)`,
	);
	const episodeId = episodeUrl?.match(/\/episodes\/([0-9a-f-]+)\/after$/)?.[1];
	if (!episodeId) throw new Error("Classroom Action episode id unavailable");
	const reconstruction = await fetch(
		`http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`,
		{
			headers: {
				"X-Dev-Principal": "NOT_FOR_PRODUCTION",
				"X-Dev-Role": "researcher",
			},
		},
	);
	const evidence = await reconstruction.json();
	if (!reconstruction.ok || evidence.state?.status !== "completed")
		throw new Error("Classroom Action backend episode did not complete");
	if (evidence.state?.condition !== condition)
		throw new Error("Classroom Action condition was not preserved");
	if (!evidence.state?.withdrawal?.answer_revealing_state_cleared)
		throw new Error("Classroom Action support was not withdrawn");
	await clickText(cdp, "ආපසු");
}

async function runSriLankaDiscoveryCoverage(cdp, condition) {
	await waitForText(cdp, "Word Explorer");
	await clickText(cdp, "Word Explorer");
	await waitForSelector(cdp, ".sri-lanka-discovery .mapping-board");
	await completeSriLankaMapping(cdp, false);
	await clickText(cdp, "Check my discovery");
	await waitForSelector(cdp, ".sld-support");
	for (let step = 0; step < 8; step += 1) {
		const label = await evaluate(
			cdp,
			"document.querySelector('.sld-support button')?.textContent?.trim()",
		);
		await clickText(cdp, label);
		if (label === "Now I will try alone") break;
	}
	await waitForSelector(cdp, ".sri-lanka-discovery .mapping-board");
	await completeSriLankaMapping(cdp, true);
	await clickText(cdp, "Check my discovery");
	await waitForText(cdp, "Excellent discovery!");
	const episodeUrl = await evaluate(
		cdp,
		`performance.getEntriesByType('resource').map((entry) => entry.name).filter((url) => url.includes('/episodes/') && url.endsWith('/after')).at(-1)`,
	);
	const episodeId = episodeUrl?.match(/\/episodes\/([0-9a-f-]+)\/after$/)?.[1];
	if (!episodeId) throw new Error("Sri Lanka Discovery episode id unavailable");
	const reconstruction = await fetch(
		`http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`,
		{
			headers: {
				"X-Dev-Principal": "NOT_FOR_PRODUCTION",
				"X-Dev-Role": "researcher",
			},
		},
	);
	const evidence = await reconstruction.json();
	if (!reconstruction.ok || evidence.state?.status !== "completed")
		throw new Error("Sri Lanka Discovery backend episode did not complete");
	if (evidence.state?.condition !== condition)
		throw new Error("Sri Lanka Discovery condition was not preserved");
	if (!evidence.state?.model1 || !evidence.state?.model2)
		throw new Error("Sri Lanka Discovery model records are missing");
	if (!evidence.state?.withdrawal?.input_handlers_cleared)
		throw new Error("Sri Lanka Discovery support was not withdrawn");
	await clickText(cdp, "ආපසු");
}

async function completeSriLankaMapping(cdp, correct) {
	await evaluate(
		cdp,
		`(async () => {
		const meanings = { Temple: 'පන්සල', Church: 'පල්ලිය', Mosque: 'මස්ජිදය', Kovil: 'කෝවිල', Crib: 'ගවලෙන', 'Christmas Tree': 'නත්තල් ගස', Kolam: 'කෝලම් රටා', 'Vesak Lantern': 'වෙසක් කූඩුව' };
		const pause = () => new Promise((resolve) => setTimeout(resolve, 25));
		const sources = [...document.querySelectorAll('.sld-source-rail button')];
		const destinations = [...document.querySelectorAll('.sld-destination')];
		for (let index = 0; index < sources.length; index += 1) {
			const source = sources[index];
			const wanted = ${correct ? "meanings[source.textContent.trim()]" : "meanings[sources[(index + 1) % sources.length].textContent.trim()]"};
			const destination = destinations.find((node) => node.querySelector('strong')?.textContent.trim() === wanted);
			source.click(); await pause(); destination.click(); await pause();
		}
		return true;
	})()`,
	);
}

async function runPlantExplorerCoverage(cdp, condition) {
	await waitForText(cdp, "Garden Word Hunt");
	await clickText(cdp, "Garden Word Hunt");
	await waitForSelector(cdp, ".plant-explorer .plant-board");
	await completePlantMapping(cdp, false);
	await clickText(cdp, "Check my garden");
	await waitForSelector(cdp, ".plant-explorer .caq-support");
	for (let step = 0; step < 8; step += 1) {
		const label = await evaluate(
			cdp,
			"document.querySelector('.plant-explorer .caq-support button')?.textContent?.trim()",
		);
		await clickText(cdp, label);
		if (label === "Now I will try alone") break;
	}
	await waitForSelector(cdp, ".plant-explorer .plant-board");
	await completePlantMapping(cdp, true);
	await clickText(cdp, "Check my garden");
	await waitForText(cdp, "Great growing!");
	const episodeUrl = await evaluate(
		cdp,
		`performance.getEntriesByType('resource').map((entry) => entry.name).filter((url) => url.includes('/episodes/') && url.endsWith('/after')).at(-1)`,
	);
	const episodeId = episodeUrl?.match(/\/episodes\/([0-9a-f-]+)\/after$/)?.[1];
	if (!episodeId) throw new Error("Plant Explorer episode id unavailable");
	const reconstruction = await fetch(
		`http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`,
		{
			headers: {
				"X-Dev-Principal": "NOT_FOR_PRODUCTION",
				"X-Dev-Role": "researcher",
			},
		},
	);
	const evidence = await reconstruction.json();
	if (!reconstruction.ok || evidence.state?.status !== "completed")
		throw new Error("Plant Explorer backend episode did not complete");
	if (evidence.state?.condition !== condition)
		throw new Error("Plant Explorer condition was not preserved");
	if (!evidence.state?.model1 || !evidence.state?.model2)
		throw new Error("Plant Explorer model records are missing");
	if (!evidence.state?.withdrawal?.input_handlers_cleared)
		throw new Error("Plant Explorer support was not withdrawn");
	await clickText(cdp, "ආපසු");
}

async function completePlantMapping(cdp, correct) {
	await evaluate(
		cdp,
		`(async () => {
		const destinations = { Roots: 'Plant Roots', Flowers: 'Plant Flowers', Fruits: 'Plant Fruits', Leaves: 'Plant Leaves', Buds: 'Plant Buds', Petals: 'Plant Petals' };
		const pause = () => new Promise((resolve) => setTimeout(resolve, 25));
		const sources = [...document.querySelectorAll('.plant-word-rail button')];
		const targets = [...document.querySelectorAll('.plant-target')];
		for (let index = 0; index < sources.length; index += 1) {
			const source = sources[index];
			const wanted = ${correct ? "destinations[source.textContent.trim()]" : "destinations[sources[(index + 1) % sources.length].textContent.trim()]"};
			const target = targets.find((node) => node.textContent.includes(wanted));
			if (!target) throw new Error(JSON.stringify({ wanted, source: source.textContent, targets: targets.map((node) => node.textContent) }));
			source.click(); await pause(); target.click(); await pause();
		}
		return true;
	})()`,
	);
}

async function runWildlifeRangerCoverage(cdp, condition) {
	await waitForText(cdp, "Animal Spotter");
	await clickText(cdp, "Animal Spotter");
	await waitForSelector(cdp, ".wildlife-ranger .wildlife-board");
	await completeWildlifeMapping(cdp, false);
	await clickText(cdp, "Check my trail");
	await waitForSelector(cdp, ".wildlife-ranger .caq-support");
	for (let step = 0; step < 8; step += 1) {
		const label = await evaluate(
			cdp,
			"document.querySelector('.wildlife-ranger .caq-support button')?.textContent?.trim()",
		);
		await clickText(cdp, label);
		if (label === "Now I will try alone") break;
	}
	await waitForSelector(cdp, ".wildlife-ranger .wildlife-board");
	await completeWildlifeMapping(cdp, true);
	await clickText(cdp, "Check my trail");
	await waitForText(cdp, "Excellent spotting!");
	const episodeUrl = await evaluate(
		cdp,
		`performance.getEntriesByType('resource').map((entry) => entry.name).filter((url) => url.includes('/episodes/') && url.endsWith('/after')).at(-1)`,
	);
	const episodeId = episodeUrl?.match(/\/episodes\/([0-9a-f-]+)\/after$/)?.[1];
	if (!episodeId) throw new Error("Wildlife Ranger episode id unavailable");
	const reconstruction = await fetch(
		`http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`,
		{
			headers: {
				"X-Dev-Principal": "NOT_FOR_PRODUCTION",
				"X-Dev-Role": "researcher",
			},
		},
	);
	const evidence = await reconstruction.json();
	if (!reconstruction.ok || evidence.state?.status !== "completed")
		throw new Error("Wildlife Ranger backend episode did not complete");
	if (evidence.state?.condition !== condition)
		throw new Error("Wildlife Ranger condition was not preserved");
	if (!evidence.state?.model1 || !evidence.state?.model2)
		throw new Error("Wildlife Ranger model records are missing");
	if (!evidence.state?.withdrawal?.input_handlers_cleared)
		throw new Error("Wildlife Ranger support was not withdrawn");
	await clickText(cdp, "ආපසු");
}

async function completeWildlifeMapping(cdp, correct) {
	await evaluate(
		cdp,
		`(async () => {
		const sprites = { Dog: 0, Elephant: 1, Rabbit: 2, Peacock: 3, Butterfly: 4, Cow: 5, Monkey: 6, Owl: 7 };
		const pause = () => new Promise((resolve) => setTimeout(resolve, 25));
		const sources = [...document.querySelectorAll('.wildlife-word-rail button')];
		const targets = [...document.querySelectorAll('.wildlife-target')];
		for (let index = 0; index < sources.length; index += 1) {
			const source = sources[index];
			const name = ${correct ? "source.textContent.trim()" : "sources[(index + 1) % sources.length].textContent.trim()"};
			const target = targets.find((node) => node.querySelector('.sprite-' + sprites[name]));
			if (!target) throw new Error('Wildlife target unavailable for ' + name);
			source.click(); await pause(); target.click(); await pause();
		}
		return true;
	})()`,
	);
}

async function runEverydayObjectCoverage(cdp, condition) {
	await waitForText(cdp, "Object Pop");
	await clickText(cdp, "Object Pop");
	await waitForSelector(cdp, ".everyday-object-quest .object-board");
	await completeObjectMapping(cdp, false);
	await clickText(cdp, "Check my objects");
	await waitForSelector(cdp, ".everyday-object-quest .caq-support");
	for (let step = 0; step < 8; step += 1) {
		const label = await evaluate(
			cdp,
			"document.querySelector('.everyday-object-quest .caq-support button')?.textContent?.trim()",
		);
		await clickText(cdp, label);
		if (label === "Now I will try alone") break;
	}
	await waitForSelector(cdp, ".everyday-object-quest .object-board");
	await completeObjectMapping(cdp, true);
	await clickText(cdp, "Check my objects");
	await waitForText(cdp, "Brilliant tidying!");
	const episodeUrl = await evaluate(
		cdp,
		`performance.getEntriesByType('resource').map((entry) => entry.name).filter((url) => url.includes('/episodes/') && url.endsWith('/after')).at(-1)`,
	);
	const episodeId = episodeUrl?.match(/\/episodes\/([0-9a-f-]+)\/after$/)?.[1];
	if (!episodeId) throw new Error("Everyday Object episode id unavailable");
	const reconstruction = await fetch(
		`http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`,
		{
			headers: {
				"X-Dev-Principal": "NOT_FOR_PRODUCTION",
				"X-Dev-Role": "researcher",
			},
		},
	);
	const evidence = await reconstruction.json();
	if (!reconstruction.ok || evidence.state?.status !== "completed")
		throw new Error("Everyday Object backend episode did not complete");
	if (evidence.state?.condition !== condition)
		throw new Error("Everyday Object condition was not preserved");
	if (!evidence.state?.model1 || !evidence.state?.model2)
		throw new Error("Everyday Object model records are missing");
	if (!evidence.state?.withdrawal?.input_handlers_cleared)
		throw new Error("Everyday Object support was not withdrawn");
	await clickText(cdp, "ආපසු");
}

async function runFamilyConstellationCoverage(cdp, condition) {
	await waitForText(cdp, "Word-Star Bridge");
	await clickText(cdp, "Word-Star Bridge");
	await waitForSelector(cdp, ".family-word-constellation .link-board");
	await completeFamilyLinks(cdp, false);
	await clickText(cdp, "Check my word links");
	await waitForSelector(cdp, ".family-word-constellation .caq-support");
	for (let step = 0; step < 8; step += 1) {
		const label = await evaluate(
			cdp,
			"document.querySelector('.family-word-constellation .caq-support button')?.textContent?.trim()",
		);
		await clickText(cdp, label);
		if (label === "Now I will try alone") break;
	}
	await waitForSelector(cdp, ".family-word-constellation .link-board");
	await completeFamilyLinks(cdp, true);
	await clickText(cdp, "Check my word links");
	await waitForText(cdp, "Constellation badge earned!");
	const episodeUrl = await evaluate(
		cdp,
		`performance.getEntriesByType('resource').map((entry) => entry.name).filter((url) => url.includes('/episodes/') && url.endsWith('/after')).at(-1)`,
	);
	const episodeId = episodeUrl?.match(/\/episodes\/([0-9a-f-]+)\/after$/)?.[1];
	if (!episodeId)
		throw new Error("Family constellation episode id unavailable");
	const reconstruction = await fetch(
		`http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`,
		{
			headers: {
				"X-Dev-Principal": "NOT_FOR_PRODUCTION",
				"X-Dev-Role": "researcher",
			},
		},
	);
	const evidence = await reconstruction.json();
	if (!reconstruction.ok || evidence.state?.status !== "completed")
		throw new Error("Family constellation backend episode did not complete");
	if (evidence.state?.condition !== condition)
		throw new Error("Family constellation condition was not preserved");
	if (!evidence.state?.model1 || !evidence.state?.model2)
		throw new Error("Family constellation model records are missing");
	if (!evidence.state?.withdrawal?.input_handlers_cleared)
		throw new Error("Family constellation support was not withdrawn");
	await clickText(cdp, "ආපසු");
}

async function completeFamilyLinks(cdp, correct) {
	await evaluate(
		cdp,
		`(async () => {
		const pairs = { Father: 'පියා', Mother: 'මව', Sister: 'සහෝදරිය', Brother: 'සහෝදරයා', Grandfather: 'මුත්තා', Grandmother: 'ආච්චි', Aunt: 'නැන්දා', Uncle: 'මාමා' };
		const pause = () => new Promise((resolve) => setTimeout(resolve, 25));
		const sources = [...document.querySelectorAll('.star-rail button')];
		const targets = [...document.querySelectorAll('.sinhala-sheet button')];
		const names = sources.map((node) => node.textContent.trim());
		for (let index = 0; index < sources.length; index += 1) {
			const name = ${correct ? "names[index]" : "names[(index + 1) % names.length]"};
			const target = targets.find((node) => node.textContent.includes(pairs[name]));
			if (!target) throw new Error('Family word unavailable for ' + name);
			sources[index].click(); await pause(); target.click(); await pause();
		}
		return true;
	})()`,
	);
}

async function runTransitTerminalCoverage(cdp, condition) {
	await waitForText(cdp, "Transit Terminal Quest");
	await clickText(cdp, "Transit Terminal Quest");
	await waitForSelector(cdp, ".transit-terminal-quest .ticket-board");
	await completeTransportMapping(cdp, false);
	await clickText(cdp, "Check my tickets");
	await waitForSelector(cdp, ".transit-terminal-quest .caq-support");
	for (let step = 0; step < 8; step += 1) {
		const label = await evaluate(
			cdp,
			"document.querySelector('.transit-terminal-quest .caq-support button')?.textContent?.trim()",
		);
		await clickText(cdp, label);
		if (label === "Now I will try alone") break;
	}
	await waitForSelector(cdp, ".transit-terminal-quest .ticket-board");
	await completeTransportMapping(cdp, true);
	await clickText(cdp, "Check my tickets");
	await waitForText(cdp, "Terminal stamp earned!");
	const episodeUrl = await evaluate(
		cdp,
		`performance.getEntriesByType('resource').map((entry) => entry.name).filter((url) => url.includes('/episodes/') && url.endsWith('/after')).at(-1)`,
	);
	const episodeId = episodeUrl?.match(/\/episodes\/([0-9a-f-]+)\/after$/)?.[1];
	if (!episodeId) throw new Error("Transit Terminal episode id unavailable");
	const reconstruction = await fetch(
		`http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`,
		{
			headers: {
				"X-Dev-Principal": "NOT_FOR_PRODUCTION",
				"X-Dev-Role": "researcher",
			},
		},
	);
	const evidence = await reconstruction.json();
	if (!reconstruction.ok || evidence.state?.status !== "completed")
		throw new Error("Transit Terminal backend episode did not complete");
	if (evidence.state?.condition !== condition)
		throw new Error("Transit Terminal condition was not preserved");
	if (!evidence.state?.model1 || !evidence.state?.model2)
		throw new Error("Transit Terminal model records are missing");
	if (!evidence.state?.withdrawal?.input_handlers_cleared)
		throw new Error("Transit Terminal support was not withdrawn");
	await clickText(cdp, "ආපසු");
}

async function completeTransportMapping(cdp, correct) {
	await evaluate(
		cdp,
		`(async () => {
		const marks = { Train: '🚆', Bicycle: '🚲', Helicopter: '🚁', Aeroplane: '✈️', Bus: '🚌', Car: '🚗' };
		const pause = () => new Promise((resolve) => setTimeout(resolve, 25));
		const sources = [...document.querySelectorAll('.ticket-rail button')];
		const targets = [...document.querySelectorAll('.vehicle-card')];
		for (let index = 0; index < sources.length; index += 1) {
			const source = sources[index];
			const name = ${correct ? "source.textContent.trim()" : "sources[(index + 1) % sources.length].textContent.trim()"};
			const target = targets.find((node) => node.textContent.includes(marks[name]));
			if (!target) throw new Error('Vehicle unavailable for ' + name);
			source.click(); await pause(); target.click(); await pause();
		}
		return true;
	})()`,
	);
}

async function runWaterWorksCoverage(cdp, condition) {
	await waitForText(cdp, "Water Works Adventure");
	await clickText(cdp, "Water Works Adventure");
	await waitForSelector(cdp, ".water-works-adventure .water-board");
	await completeWaterMapping(cdp, false);
	await clickText(cdp, "Check my water actions");
	await waitForSelector(cdp, ".water-works-adventure .caq-support");
	for (let step = 0; step < 8; step += 1) {
		const label = await evaluate(
			cdp,
			"document.querySelector('.water-works-adventure .caq-support button')?.textContent?.trim()",
		);
		await clickText(cdp, label);
		if (label === "Now I will try alone") break;
	}
	await waitForSelector(cdp, ".water-works-adventure .water-board");
	await completeWaterMapping(cdp, true);
	await clickText(cdp, "Check my water actions");
	await waitForText(cdp, "Water badge earned!");
	const episodeUrl = await evaluate(
		cdp,
		`performance.getEntriesByType('resource').map((entry) => entry.name).filter((url) => url.includes('/episodes/') && url.endsWith('/after')).at(-1)`,
	);
	const episodeId = episodeUrl?.match(/\/episodes\/([0-9a-f-]+)\/after$/)?.[1];
	if (!episodeId) throw new Error("Water Works episode id unavailable");
	const reconstruction = await fetch(
		`http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`,
		{
			headers: {
				"X-Dev-Principal": "NOT_FOR_PRODUCTION",
				"X-Dev-Role": "researcher",
			},
		},
	);
	const evidence = await reconstruction.json();
	if (!reconstruction.ok || evidence.state?.status !== "completed")
		throw new Error("Water Works backend episode did not complete");
	if (evidence.state?.condition !== condition)
		throw new Error("Water Works condition was not preserved");
	if (!evidence.state?.model1 || !evidence.state?.model2)
		throw new Error("Water Works model records are missing");
	if (!evidence.state?.withdrawal?.input_handlers_cleared)
		throw new Error("Water Works support was not withdrawn");
	await clickText(cdp, "ආපසු");
}

async function runRainbowWardrobeCoverage(cdp, condition) {
	await waitForText(cdp, "Rainbow Wardrobe Quest");
	await clickText(cdp, "Rainbow Wardrobe Quest");
	await waitForSelector(cdp, ".rainbow-wardrobe .wardrobe-rail");
	await completeWardrobeMapping(cdp, null);
	await clickText(cdp, "Check my wardrobe");
	await waitForSelector(cdp, ".rainbow-wardrobe .caq-support");
	for (let step = 0; step < 8; step += 1) {
		const label = await evaluate(
			cdp,
			"document.querySelector('.rainbow-wardrobe .caq-support button')?.textContent?.trim()",
		);
		await clickText(cdp, label);
		if (label === "I’m ready alone") break;
	}
	await waitForSelector(cdp, ".rainbow-wardrobe .wardrobe-rail");
	const episodeUrl = await evaluate(
		cdp,
		`performance.getEntriesByType('resource').map((entry) => entry.name).filter((url) => url.includes('/episodes/')).at(-1)`,
	);
	const episodeId = episodeUrl?.match(/\/episodes\/([0-9a-f-]+)/)?.[1];
	if (!episodeId) throw new Error("Rainbow Wardrobe episode id unavailable");
	const reconstructionUrl = `http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`;
	const headers = {
		"X-Dev-Principal": "NOT_FOR_PRODUCTION",
		"X-Dev-Role": "researcher",
	};
	const beforeResponse = await fetch(reconstructionUrl, { headers });
	const beforeEvidence = await beforeResponse.json();
	const afterItem = beforeEvidence.state?.presentations?.find(
		(row) => row.role === "unsupported_after",
	);
	if (!afterItem?.game_data?.target_mapping)
		throw new Error("Rainbow Wardrobe reserved mapping unavailable");
	await completeWardrobeMapping(cdp, afterItem.game_data.target_mapping);
	await clickText(cdp, "Check my wardrobe");
	await waitForText(cdp, "Wardrobe wonder!");
	await clickText(cdp, "See my badge");
	await waitForText(cdp, "Rainbow Wardrobe Quest complete!");
	const reconstruction = await fetch(reconstructionUrl, { headers });
	const evidence = await reconstruction.json();
	if (!reconstruction.ok || evidence.state?.status !== "completed")
		throw new Error("Rainbow Wardrobe backend episode did not complete");
	if (evidence.state?.condition !== condition)
		throw new Error("Rainbow Wardrobe condition was not preserved");
	if (!evidence.state?.model1 || !evidence.state?.model2)
		throw new Error("Rainbow Wardrobe model records are missing");
	if (!evidence.state?.withdrawal?.input_handlers_cleared)
		throw new Error("Rainbow Wardrobe support was not withdrawn");
	await clickText(cdp, "ආපසු");
}

async function runBloomBuilderCoverage(cdp, condition) {
	await waitForText(cdp, "Bloom Builder Garden");
	await clickText(cdp, "Bloom Builder Garden");
	await waitForSelector(cdp, ".bloom-builder-garden .garden-bed");
	await completeBloomMapping(cdp, null);
	await clickText(cdp, "Check my garden");
	await waitForSelector(cdp, ".bloom-builder-garden .caq-support");
	for (let step = 0; step < 8; step += 1) {
		const label = await evaluate(
			cdp,
			"document.querySelector('.bloom-builder-garden .caq-support button')?.textContent?.trim()",
		);
		await clickText(cdp, label);
		if (label === "I’m ready to grow alone") break;
	}
	await waitForSelector(cdp, ".bloom-builder-garden .garden-bed");
	const episodeUrl = await evaluate(
		cdp,
		`performance.getEntriesByType('resource').map((entry) => entry.name).filter((url) => url.includes('/episodes/')).at(-1)`,
	);
	const episodeId = episodeUrl?.match(/\/episodes\/([0-9a-f-]+)/)?.[1];
	if (!episodeId) throw new Error("Bloom Builder episode id unavailable");
	const reconstructionUrl = `http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`;
	const headers = {
		"X-Dev-Principal": "NOT_FOR_PRODUCTION",
		"X-Dev-Role": "researcher",
	};
	const reservedResponse = await fetch(reconstructionUrl, { headers });
	const reservedEvidence = await reservedResponse.json();
	const afterItem = reservedEvidence.state?.presentations?.find(
		(row) => row.role === "unsupported_after",
	);
	if (!afterItem?.game_data?.target_mapping)
		throw new Error("Bloom Builder reserved mapping unavailable");
	await completeBloomMapping(cdp, afterItem.game_data.target_mapping);
	await clickText(cdp, "Check my garden");
	await waitForText(cdp, "Beautiful bloom building!");
	await clickText(cdp, "Collect garden badge");
	await waitForText(cdp, "Bloom Builder Garden complete!");
	const reconstruction = await fetch(reconstructionUrl, { headers });
	const evidence = await reconstruction.json();
	if (!reconstruction.ok || evidence.state?.status !== "completed")
		throw new Error("Bloom Builder backend episode did not complete");
	if (evidence.state?.condition !== condition)
		throw new Error("Bloom Builder condition was not preserved");
	if (!evidence.state?.model1 || !evidence.state?.model2)
		throw new Error("Bloom Builder model records are missing");
	if (!evidence.state?.withdrawal?.input_handlers_cleared)
		throw new Error("Bloom Builder support was not withdrawn");
	if (!("raw_independence_gain" in (evidence.state ?? {})))
		throw new Error("Bloom Builder independence measurement is missing");
	await clickText(cdp, "ආපසු");
}

async function runWorkplaceLinkCoverage(cdp, condition) {
	await waitForText(cdp, "Work Route Connector");
	await clickText(cdp, "Work Route Connector");
	await waitForSelector(cdp, ".workplace-link-city .route-hubs");
	await completeWorkplaceLinks(cdp, null);
	await clickText(cdp, "Check my city links");
	await waitForSelector(cdp, ".workplace-link-city .caq-support");
	for (let step = 0; step < 8; step += 1) {
		const label = await evaluate(
			cdp,
			"document.querySelector('.workplace-link-city .caq-support button')?.textContent?.trim()",
		);
		await clickText(cdp, label);
		if (label === "I’m ready to link alone") break;
	}
	await waitForSelector(cdp, ".workplace-link-city .route-hubs");
	const episodeUrl = await evaluate(
		cdp,
		`performance.getEntriesByType('resource').map((entry) => entry.name).filter((url) => url.includes('/episodes/')).at(-1)`,
	);
	const episodeId = episodeUrl?.match(/\/episodes\/([0-9a-f-]+)/)?.[1];
	if (!episodeId) throw new Error("Workplace Link episode id unavailable");
	const reconstructionUrl = `http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`;
	const headers = {
		"X-Dev-Principal": "NOT_FOR_PRODUCTION",
		"X-Dev-Role": "researcher",
	};
	const reservedResponse = await fetch(reconstructionUrl, { headers });
	const reservedEvidence = await reservedResponse.json();
	const afterItem = reservedEvidence.state?.presentations?.find(
		(row) => row.role === "unsupported_after",
	);
	if (!afterItem?.game_data?.target_links)
		throw new Error("Workplace Link reserved graph unavailable");
	await completeWorkplaceLinks(cdp, afterItem.game_data.target_links);
	await clickText(cdp, "Check my city links");
	await waitForText(cdp, "City link complete!");
	const reconstruction = await fetch(reconstructionUrl, { headers });
	const evidence = await reconstruction.json();
	if (!reconstruction.ok || evidence.state?.status !== "completed")
		throw new Error("Workplace Link backend episode did not complete");
	if (evidence.state?.condition !== condition)
		throw new Error("Workplace Link condition was not preserved");
	if (!evidence.state?.model1 || !evidence.state?.model2)
		throw new Error("Workplace Link model records are missing");
	if (!evidence.state?.withdrawal?.input_handlers_cleared)
		throw new Error("Workplace Link support was not withdrawn");
	if (!("raw_independence_gain" in (evidence.state ?? {})))
		throw new Error("Workplace Link independence measurement is missing");
	await clickText(cdp, "ආපසු");
}

async function runEarthSkyCoverage(cdp, condition) {
	await waitForText(cdp, "Panorama Label Quest");
	await clickText(cdp, "Panorama Label Quest");
	await waitForSelector(cdp, ".earth-sky-explorer .es-panorama");
	await completeEarthSkyMapping(cdp, null);
	await clickText(cdp, "Check my explorer links");
	await waitForSelector(cdp, ".earth-sky-explorer .caq-support");
	for (let step = 0; step < 8; step += 1) {
		const label = await evaluate(
			cdp,
			"document.querySelector('.earth-sky-explorer .caq-support button')?.textContent?.trim()",
		);
		await clickText(cdp, label);
		if (label === "I’m ready to explore alone") break;
	}
	await waitForSelector(cdp, ".earth-sky-explorer .es-panorama");
	const episodeUrl = await evaluate(
		cdp,
		`performance.getEntriesByType('resource').map((entry) => entry.name).filter((url) => url.includes('/episodes/')).at(-1)`,
	);
	const episodeId = episodeUrl?.match(/\/episodes\/([0-9a-f-]+)/)?.[1];
	if (!episodeId) throw new Error("Earth & Sky episode id unavailable");
	const reconstructionUrl = `http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`;
	const headers = {
		"X-Dev-Principal": "NOT_FOR_PRODUCTION",
		"X-Dev-Role": "researcher",
	};
	const reservedResponse = await fetch(reconstructionUrl, { headers });
	const reservedEvidence = await reservedResponse.json();
	const afterItem = reservedEvidence.state?.presentations?.find(
		(row) => row.role === "unsupported_after",
	);
	if (!afterItem?.game_data?.target_mapping)
		throw new Error("Earth & Sky reserved mapping unavailable");
	await completeEarthSkyMapping(cdp, afterItem.game_data.target_mapping);
	await clickText(cdp, "Check my explorer links");
	await waitForText(cdp, "Explorer badge earned!");
	const reconstruction = await fetch(reconstructionUrl, { headers });
	const evidence = await reconstruction.json();
	if (!reconstruction.ok || evidence.state?.status !== "completed")
		throw new Error("Earth & Sky backend episode did not complete");
	if (evidence.state?.condition !== condition)
		throw new Error("Earth & Sky condition was not preserved");
	if (!evidence.state?.model1 || !evidence.state?.model2)
		throw new Error("Earth & Sky model records are missing");
	if (!evidence.state?.withdrawal?.input_handlers_cleared)
		throw new Error("Earth & Sky support was not withdrawn");
	if (!("raw_independence_gain" in (evidence.state ?? {})))
		throw new Error("Earth & Sky independence measurement is missing");
}

async function runBlueprintCoverage(cdp, condition) {
	await waitForText(cdp, "Place Card Explorer");
	await clickText(cdp, "Place Card Explorer");
	await waitForSelector(cdp, ".blueprint-quest .bp-zones");
	await completeBlueprintMapping(cdp, null);
	await clickText(cdp, "Check my blueprint");
	await waitForSelector(cdp, ".blueprint-quest .caq-support");
	for (let step = 0; step < 8; step += 1) {
		const label = await evaluate(
			cdp,
			"document.querySelector('.blueprint-quest .caq-support button')?.textContent?.trim()",
		);
		await clickText(cdp, label);
		if (label === "I’m ready to build alone") break;
	}
	await waitForSelector(cdp, ".blueprint-quest .bp-zones");
	const episodeUrl = await evaluate(
			cdp,
			`performance.getEntriesByType('resource').map(e=>e.name).filter(u=>u.includes('/episodes/')).at(-1)`,
		),
		episodeId = episodeUrl?.match(/\/episodes\/([0-9a-f-]+)/)?.[1];
	if (!episodeId) throw new Error("Blueprint episode unavailable");
	const url = `http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`,
		headers = {
			"X-Dev-Principal": "NOT_FOR_PRODUCTION",
			"X-Dev-Role": "researcher",
		},
		reserved = await (await fetch(url, { headers })).json(),
		after = reserved.state?.presentations?.find(
			(x) => x.role === "unsupported_after",
		);
	if (!after?.game_data?.target_mapping)
		throw new Error("Blueprint mapping unavailable");
	await completeBlueprintMapping(cdp, after.game_data.target_mapping);
	await clickText(cdp, "Check my blueprint");
	await waitForText(cdp, "Blueprint approved!");
	const response = await fetch(url, { headers }),
		evidence = await response.json();
	if (
		!response.ok ||
		evidence.state?.status !== "completed" ||
		evidence.state?.condition !== condition ||
		!evidence.state?.model1 ||
		!evidence.state?.model2 ||
		!evidence.state?.withdrawal?.input_handlers_cleared ||
		!("raw_independence_gain" in evidence.state)
	)
		throw new Error("Blueprint reconstruction incomplete");
}

async function runClassroomLanguageCoverage(cdp, condition) {
	await waitForText(cdp, "Phrase Portal Sort");
	await clickText(cdp, "Phrase Portal Sort");
	await waitForSelector(cdp, ".classroom-language-live .cll-portals");
	await completeClassroomLanguageMapping(cdp, null);
	await clickText(cdp, "Check my classroom response");
	await waitForSelector(cdp, ".classroom-language-live .caq-support");
	for (let step = 0; step < 8; step += 1) {
		const label = await evaluate(
			cdp,
			"document.querySelector('.classroom-language-live .caq-support button')?.textContent?.trim()",
		);
		await clickText(cdp, label);
		if (label === "I’m ready to respond alone") break;
	}
	await waitForSelector(cdp, ".classroom-language-live .cll-portals");
	const episodeUrl = await evaluate(
		cdp,
		`performance.getEntriesByType('resource').map((entry) => entry.name).filter((url) => url.includes('/episodes/')).at(-1)`,
	);
	const episodeId = episodeUrl?.match(/\/episodes\/([0-9a-f-]+)/)?.[1];
	if (!episodeId) throw new Error("Classroom Language episode unavailable");
	const reconstructionUrl = `http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`;
	const headers = {
		"X-Dev-Principal": "NOT_FOR_PRODUCTION",
		"X-Dev-Role": "researcher",
	};
	const reserved = await (await fetch(reconstructionUrl, { headers })).json();
	const after = reserved.state?.presentations?.find(
		(row) => row.role === "unsupported_after",
	);
	if (!after?.game_data?.target_mapping)
		throw new Error("Classroom Language mapping unavailable");
	await completeClassroomLanguageMapping(cdp, after.game_data.target_mapping);
	await clickText(cdp, "Check my classroom response");
	await waitForText(cdp, "Classroom response complete!");
	const response = await fetch(reconstructionUrl, { headers });
	const evidence = await response.json();
	if (
		!response.ok ||
		evidence.state?.status !== "completed" ||
		evidence.state?.condition !== condition ||
		!evidence.state?.model1 ||
		!evidence.state?.model2 ||
		!evidence.state?.withdrawal?.input_handlers_cleared ||
		!("raw_independence_gain" in evidence.state)
	)
		throw new Error("Classroom Language reconstruction incomplete");
}

async function completeClassroomLanguageMapping(cdp, mapping) {
	await evaluate(
		cdp,
		`(async () => {
		const mapping = ${JSON.stringify(mapping)};
		const pause = () => new Promise((resolve) => setTimeout(resolve, 25));
		const sources = [...document.querySelectorAll('.classroom-language-live .cll-tray button')];
		const targets = [...document.querySelectorAll('.classroom-language-live .cll-portals button')];
		for (let index = 0; index < sources.length; index += 1) {
			const source = sources[index];
			const targetToken = mapping ? mapping[source.dataset.opaqueToken] : targets[index].dataset.opaqueToken;
			const target = targets.find((node) => node.dataset.opaqueToken === targetToken);
			if (!target) throw new Error('Classroom Language target unavailable');
			source.click(); await pause(); target.click(); await pause();
		}
		return true;
	})()`,
	);
}

async function runConversationStreetCoverage(cdp, condition) {
	await waitForText(cdp, "Conversation Matchmaker");
	await clickText(cdp, "Conversation Matchmaker");
	await waitForSelector(cdp, ".conversation-street .cs-response-sheet");
	await completeConversationLinks(cdp, null);
	await clickText(cdp, "Send this fictional turn");
	await waitForSelector(cdp, ".conversation-street .caq-support");
	for (let step = 0; step < 8; step += 1) {
		const label = await evaluate(
			cdp,
			"document.querySelector('.conversation-street .caq-support button')?.textContent?.trim()",
		);
		await clickText(cdp, label);
		if (label === "I’m ready to talk as the character alone") break;
	}
	await waitForSelector(cdp, ".conversation-street .cs-response-sheet");
	const episodeUrl = await evaluate(
		cdp,
		`performance.getEntriesByType('resource').map((entry) => entry.name).filter((url) => url.includes('/episodes/')).at(-1)`,
	);
	const episodeId = episodeUrl?.match(/\/episodes\/([0-9a-f-]+)/)?.[1];
	if (!episodeId) throw new Error("Conversation Street episode unavailable");
	const reconstructionUrl = `http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`;
	const headers = {
		"X-Dev-Principal": "NOT_FOR_PRODUCTION",
		"X-Dev-Role": "researcher",
	};
	const reserved = await (await fetch(reconstructionUrl, { headers })).json();
	const after = reserved.state?.presentations?.find(
		(row) => row.role === "unsupported_after",
	);
	if (!after?.game_data?.target_mapping)
		throw new Error("Conversation Street adjacency map unavailable");
	await completeConversationLinks(cdp, after.game_data.target_mapping);
	await clickText(cdp, "Send this fictional turn");
	await waitForText(cdp, "Conversation turn complete!");
	const response = await fetch(reconstructionUrl, { headers });
	const evidence = await response.json();
	if (
		!response.ok ||
		evidence.state?.status !== "completed" ||
		evidence.state?.condition !== condition ||
		!evidence.state?.model1 ||
		!evidence.state?.model2 ||
		!evidence.state?.withdrawal?.input_handlers_cleared ||
		!("raw_independence_gain" in evidence.state)
	)
		throw new Error("Conversation Street reconstruction incomplete");
}

async function completeConversationLinks(cdp, mapping) {
	await evaluate(
		cdp,
		`(async () => {
		const mapping = ${JSON.stringify(mapping)};
		const pause = () => new Promise((resolve) => setTimeout(resolve, 25));
		const questions = [...document.querySelectorAll('.conversation-street .cs-timeline button')];
		const responses = [...document.querySelectorAll('.conversation-street .cs-response-sheet button')];
		for (let index = 0; index < questions.length; index += 1) {
			const question = questions[index];
			const responseToken = mapping ? mapping[question.dataset.opaqueToken] : responses[index].dataset.opaqueToken;
			const response = responses.find((node) => node.dataset.opaqueToken === responseToken);
			if (!response) throw new Error('Conversation response unavailable');
			question.click(); await pause(); response.click(); await pause();
		}
		return true;
	})()`,
	);
}
async function completeBlueprintMapping(cdp, mapping) {
	await evaluate(
		cdp,
		`(async()=>{const mapping=${JSON.stringify(mapping)},pause=()=>new Promise(r=>setTimeout(r,25)),sources=[...document.querySelectorAll('.blueprint-quest .bp-tray button')],targets=[...document.querySelectorAll('.blueprint-quest .bp-zones button')];for(let i=0;i<sources.length;i++){const source=sources[i],token=mapping?mapping[source.dataset.opaqueToken]:targets[(i+1)%targets.length].dataset.opaqueToken,target=targets.find(n=>n.dataset.opaqueToken===token);if(!target)throw new Error('Blueprint target unavailable');source.click();await pause();target.click();await pause()}return true})()`,
	);
}

async function runInformationStationCoverage(cdp, condition) {
	await waitForText(cdp, "Word Signal Bridge");
	await clickText(cdp, "Word Signal Bridge");
	await waitForSelector(cdp, ".info-station .is-targets");
	await completeInformationMapping(cdp, null);
	await clickText(cdp, "Check my signals");
	await waitForSelector(cdp, ".info-station .caq-support");
	for (let step = 0; step < 8; step += 1) {
		const label = await evaluate(
			cdp,
			"document.querySelector('.info-station .caq-support button')?.textContent?.trim()",
		);
		await clickText(cdp, label);
		if (label === "I’m ready to connect alone") break;
	}
	await waitForSelector(cdp, ".info-station .is-targets");
	const episodeUrl = await evaluate(
		cdp,
		`performance.getEntriesByType('resource').map((entry) => entry.name).filter((url) => url.includes('/episodes/')).at(-1)`,
	);
	const episodeId = episodeUrl?.match(/\/episodes\/([0-9a-f-]+)/)?.[1];
	if (!episodeId) throw new Error("Information Station episode unavailable");
	const reconstructionUrl = `http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`;
	const headers = {
		"X-Dev-Principal": "NOT_FOR_PRODUCTION",
		"X-Dev-Role": "researcher",
	};
	const reserved = await (await fetch(reconstructionUrl, { headers })).json();
	const after = reserved.state?.presentations?.find(
		(row) => row.role === "unsupported_after",
	);
	if (!after?.game_data?.target_mapping)
		throw new Error("Information Station mapping unavailable");
	await completeInformationMapping(cdp, after.game_data.target_mapping);
	await clickText(cdp, "Check my signals");
	await waitForText(cdp, "Signal station complete!");
	const response = await fetch(reconstructionUrl, { headers });
	const evidence = await response.json();
	if (
		!response.ok ||
		evidence.state?.status !== "completed" ||
		evidence.state?.condition !== condition ||
		!evidence.state?.model1 ||
		!evidence.state?.model2 ||
		!evidence.state?.withdrawal?.input_handlers_cleared ||
		!("raw_independence_gain" in evidence.state)
	)
		throw new Error("Information Station reconstruction incomplete");
}

async function runHeritageMuseumCoverage(cdp, condition) {
	await waitForText(cdp, "Museum Word Bridge");
	await clickText(cdp, "Museum Word Bridge");
	await waitForSelector(cdp, ".heritage-museum .hm-cases");
	await completeHeritageMapping(cdp, null);
	await clickText(cdp, "Check my labels");
	await waitForSelector(cdp, ".heritage-museum .caq-support");
	for (let step = 0; step < 8; step += 1) {
		const label = await evaluate(
			cdp,
			"document.querySelector('.heritage-museum .caq-support button')?.textContent?.trim()",
		);
		await clickText(cdp, label);
		if (label === "I’m ready to curate alone") break;
	}
	await waitForSelector(cdp, ".heritage-museum .hm-cases");
	const episodeUrl = await evaluate(
		cdp,
		`performance.getEntriesByType('resource').map((entry) => entry.name).filter((url) => url.includes('/episodes/')).at(-1)`,
	);
	const episodeId = episodeUrl?.match(/\/episodes\/([0-9a-f-]+)/)?.[1];
	if (!episodeId) throw new Error("Heritage Museum episode unavailable");
	const reconstructionUrl = `http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`;
	const headers = {
		"X-Dev-Principal": "NOT_FOR_PRODUCTION",
		"X-Dev-Role": "researcher",
	};
	const reserved = await (await fetch(reconstructionUrl, { headers })).json();
	const after = reserved.state?.presentations?.find(
		(row) => row.role === "unsupported_after",
	);
	if (!after?.game_data?.target_mapping)
		throw new Error("Heritage Museum mapping unavailable");
	await completeHeritageMapping(cdp, after.game_data.target_mapping);
	await clickText(cdp, "Check my labels");
	await waitForText(cdp, "Museum label approved!");
	const response = await fetch(reconstructionUrl, { headers });
	const evidence = await response.json();
	if (
		!response.ok ||
		evidence.state?.status !== "completed" ||
		evidence.state?.condition !== condition ||
		!evidence.state?.model1 ||
		!evidence.state?.model2 ||
		!evidence.state?.withdrawal?.input_handlers_cleared ||
		!("raw_independence_gain" in evidence.state)
	)
		throw new Error("Heritage Museum reconstruction incomplete");
}

async function completeHeritageMapping(cdp, mapping) {
	await evaluate(
		cdp,
		`(async () => {
		const mapping = ${JSON.stringify(mapping)};
		const pause = () => new Promise((resolve) => setTimeout(resolve, 25));
		const sources = [...document.querySelectorAll('.heritage-museum .hm-tray button')];
		const targets = [...document.querySelectorAll('.heritage-museum .hm-target')];
		for (let index = 0; index < sources.length; index += 1) {
			const source = sources[index];
			const token = mapping ? mapping[source.dataset.opaqueToken] : targets[index].dataset.opaqueToken;
			const target = targets.find((node) => node.dataset.opaqueToken === token);
			if (!target) throw new Error('Heritage Museum target unavailable');
			source.click(); await pause(); target.click(); await pause();
		}
		return true;
	})()`,
	);
}

async function completeInformationMapping(cdp, mapping) {
	await evaluate(
		cdp,
		`(async () => {
		const mapping = ${JSON.stringify(mapping)};
		const pause = () => new Promise((resolve) => setTimeout(resolve, 25));
		const sources = [...document.querySelectorAll('.info-station .is-tray button')];
		const targets = [...document.querySelectorAll('.info-station .is-targets button')];
		for (let index = 0; index < sources.length; index += 1) {
			const source = sources[index];
			const token = mapping ? mapping[source.dataset.opaqueToken] : targets[index].dataset.opaqueToken;
			const target = targets.find((node) => node.dataset.opaqueToken === token);
			if (!target) throw new Error('Information Station target unavailable');
			source.click(); await pause(); target.click(); await pause();
		}
		return true;
	})()`,
	);
}

async function completeEarthSkyMapping(cdp, mapping) {
	await evaluate(
		cdp,
		`(async () => {
		const mapping = ${JSON.stringify(mapping)};
		const pause = () => new Promise((resolve) => setTimeout(resolve, 25));
		const sources = [...document.querySelectorAll('.earth-sky-explorer .es-token-grid .es-word')];
		const targets = [...document.querySelectorAll('.earth-sky-explorer .es-card-target')];
		for (let index = 0; index < sources.length; index += 1) {
			const source = sources[index];
			const targetToken = mapping ? mapping[source.dataset.opaqueToken] : targets[(index + 1) % targets.length].dataset.opaqueToken;
			const target = targets.find((node) => node.dataset.opaqueToken === targetToken);
			if (!target) throw new Error('Earth & Sky target unavailable');
			source.click(); await pause(); target.click(); await pause();
		}
		return true;
	})()`,
	);
}

async function completeWorkplaceLinks(cdp, mapping) {
	await evaluate(
		cdp,
		`(async () => {
		const mapping = ${JSON.stringify(mapping)};
		const pause = () => new Promise((resolve) => setTimeout(resolve, 25));
		const sources = [...document.querySelectorAll('.workplace-link-city .occupation-tray .work-label')];
		const targets = [...document.querySelectorAll('.workplace-link-city .place-hub')];
		for (let index = 0; index < sources.length; index += 1) {
			const source = sources[index];
			const targetToken = mapping ? mapping[source.dataset.opaqueToken] : targets[(index + 1) % targets.length].dataset.opaqueToken;
			const target = targets.find((node) => node.dataset.opaqueToken === targetToken);
			if (!target) throw new Error('Workplace destination unavailable');
			source.click(); await pause(); target.click(); await pause();
		}
		return true;
	})()`,
	);
}

async function completeBloomMapping(cdp, mapping) {
	await evaluate(
		cdp,
		`(async () => {
		const mapping = ${JSON.stringify(mapping)};
		const pause = () => new Promise((resolve) => setTimeout(resolve, 25));
		const sources = [...document.querySelectorAll('.bloom-builder-garden .seed-packet')];
		const targets = [...document.querySelectorAll('.bloom-builder-garden .flower-target-hit')];
		for (let index = 0; index < sources.length; index += 1) {
			const source = sources[index];
			const targetToken = mapping ? mapping[source.dataset.opaqueToken] : targets[(index + 1) % targets.length].dataset.opaqueToken;
			const target = targets.find((node) => node.dataset.opaqueToken === targetToken);
			if (!target) throw new Error('Flower target unavailable');
			source.click(); await pause(); target.click(); await pause();
		}
		return true;
	})()`,
	);
}

async function completeWardrobeMapping(cdp, mapping) {
	await evaluate(
		cdp,
		`(async () => {
		const mapping = ${JSON.stringify(mapping)};
		const pause = () => new Promise((resolve) => setTimeout(resolve, 25));
		const sources = [...document.querySelectorAll('.rainbow-wardrobe .wardrobe-word')];
		const targets = [...document.querySelectorAll('.rainbow-wardrobe .wardrobe-target')];
		for (let index = 0; index < sources.length; index += 1) {
			const source = sources[index];
			const targetToken = mapping ? mapping[source.dataset.opaqueToken] : targets[(index + 1) % targets.length].dataset.opaqueToken;
			const target = targets.find((node) => node.dataset.opaqueToken === targetToken);
			if (!target) throw new Error('Wardrobe target unavailable');
			source.click(); await pause(); target.click(); await pause();
		}
		return true;
	})()`,
	);
}

async function completeWaterMapping(cdp, correct) {
	await evaluate(
		cdp,
		`(async () => {
		const marks = { Bathe: '🛁', Cook: '🍲', Wash: '🧼', Drink: '🥤', 'Water (the plants)': '🌱' };
		const pause = () => new Promise((resolve) => setTimeout(resolve, 25));
		const sources = [...document.querySelectorAll('.droplet-rail button')];
		const targets = [...document.querySelectorAll('.scene-card')];
		for (let index = 0; index < sources.length; index += 1) {
			const source = sources[index];
			const name = ${correct ? "source.textContent.trim()" : "sources[(index + 1) % sources.length].textContent.trim()"};
			const target = targets.find((node) => node.textContent.includes(marks[name]));
			if (!target) throw new Error('Water scene unavailable for ' + name);
			source.click(); await pause(); target.click(); await pause();
		}
		return true;
	})()`,
	);
}

async function runIslandFoodCoverage(cdp, condition) {
	await waitForText(cdp, "Market Match Dash");
	await clickText(cdp, "Market Match Dash");
	await waitForSelector(cdp, ".island-food-festival .food-board");
	await completeFoodMapping(cdp, false);
	await clickText(cdp, "Check my foods");
	await waitForSelector(cdp, ".island-food-festival .caq-support");
	for (let step = 0; step < 8; step += 1) {
		const label = await evaluate(
			cdp,
			"document.querySelector('.island-food-festival .caq-support button')?.textContent?.trim()",
		);
		await clickText(cdp, label);
		if (label === "Now I will try alone") break;
	}
	await waitForSelector(cdp, ".island-food-festival .food-board");
	await completeFoodMapping(cdp, true);
	await clickText(cdp, "Check my foods");
	await waitForText(cdp, "Festival stamp earned!");
	const episodeUrl = await evaluate(
		cdp,
		`performance.getEntriesByType('resource').map((entry) => entry.name).filter((url) => url.includes('/episodes/') && url.endsWith('/after')).at(-1)`,
	);
	const episodeId = episodeUrl?.match(/\/episodes\/([0-9a-f-]+)\/after$/)?.[1];
	if (!episodeId) throw new Error("Island Food episode id unavailable");
	const reconstruction = await fetch(
		`http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`,
		{
			headers: {
				"X-Dev-Principal": "NOT_FOR_PRODUCTION",
				"X-Dev-Role": "researcher",
			},
		},
	);
	const evidence = await reconstruction.json();
	if (!reconstruction.ok || evidence.state?.status !== "completed")
		throw new Error("Island Food backend episode did not complete");
	if (evidence.state?.condition !== condition)
		throw new Error("Island Food condition was not preserved");
	if (!evidence.state?.model1 || !evidence.state?.model2)
		throw new Error("Island Food model records are missing");
	if (!evidence.state?.withdrawal?.input_handlers_cleared)
		throw new Error("Island Food support was not withdrawn");
	await clickText(cdp, "ආපසු");
}

async function completeFoodMapping(cdp, correct) {
	await evaluate(
		cdp,
		`(async () => {
		const glyphs = { Egg: '🥚', Bread: '🍞', Fish: '🐟', Coconut: '🥥', Buns: '🥯', 'Sweet Potatoes': '🍠', Tea: '🍵', Milk: '🥛', Water: '💧', 'Fruit Juice': '🧃', Banana: '🍌', Pineapple: '🍍', Mango: '🥭', Watermelon: '🍉', Olive: '🫒', Potato: '🥔', Cabbage: '🥬', Tomato: '🍅', Carrot: '🥕', Cucumber: '🥒' };
		const pause = () => new Promise((resolve) => setTimeout(resolve, 25));
		const sources = [...document.querySelectorAll('.island-food-festival .chunk-rail button')];
		const targets = [...document.querySelectorAll('.island-food-festival .food-target')];
		for (let index = 0; index < sources.length; index += 1) {
			const source = sources[index];
			const name = ${correct ? "source.textContent.trim()" : "sources[(index + 1) % sources.length].textContent.trim()"};
			const target = targets.find((node) => node.textContent.includes(glyphs[name]));
			if (!target) throw new Error('Food target unavailable for ' + name);
			source.click(); await pause(); target.click(); await pause();
		}
		return true;
	})()`,
	);
}

async function completeObjectMapping(cdp, correct) {
	await evaluate(
		cdp,
		`(async () => {
		const glyphs = { Chair: '🪑', Pencil: '✏️', Ruler: '📏', Bed: '🛏️', Spoon: '🥄', Toothbrush: '🪥', Broom: '🧹', Plate: '🍽️' };
		const pause = () => new Promise((resolve) => setTimeout(resolve, 25));
		const sources = [...document.querySelectorAll('.object-word-rail button')];
		const targets = [...document.querySelectorAll('.object-target')];
		for (let index = 0; index < sources.length; index += 1) {
			const source = sources[index];
			const name = ${correct ? "source.textContent.trim()" : "sources[(index + 1) % sources.length].textContent.trim()"};
			const target = targets.find((node) => node.textContent.includes(glyphs[name]));
			if (!target) throw new Error('Object target unavailable for ' + name);
			source.click(); await pause(); target.click(); await pause();
		}
		return true;
	})()`,
	);
}

async function runNumberPatternCoverage(cdp, condition) {
	await waitForText(cdp, "සංඛ්‍යා පියවර මාවත");
	await clickText(cdp, "සංඛ්‍යා පියවර මාවත");
	const episodeIds = new Set();
	const supportTypes = new Set();
	for (let challenge = 0; challenge < 6; challenge += 1) {
		await waitForSelector(cdp, ".number-pattern-adventure .pattern-board");
		await completeNumberPatternManipulation(cdp, false);
		await clickText(cdp, "තහවුරු කරන්න");
		await waitFor(
			cdp,
			`document.querySelector('[data-pattern-step]')?.dataset.patternStep === 'feedback'`,
		);
		await clickText(cdp, "උදව්ව බලන්න");
		await waitForSelector(cdp, ".number-pattern-adventure [data-support-type]");
		await completeAdaptiveSupport(cdp);
		await clickText(cdp, "උදව්ව අවසන් කරන්න");
		await waitFor(
			cdp,
			`document.querySelector('[data-pattern-step]')?.dataset.patternStep === 'question'`,
		);
		if (
			await evaluate(
				cdp,
				`Boolean(document.querySelector('[data-support-visible="true"]'))`,
			)
		)
			throw new Error(
				`Number Pattern challenge ${challenge + 1}: support remained visible`,
			);
		await completeNumberPatternManipulation(cdp, true);
		await clickText(cdp, "තහවුරු කරන්න");
		await waitFor(
			cdp,
			`document.querySelector('[data-pattern-step]')?.dataset.patternStep === 'result'`,
		);
		const episodeId = await evaluate(
			cdp,
			"document.querySelector('.number-pattern-adventure')?.dataset.episodeId",
		);
		if (!episodeId || episodeIds.has(episodeId))
			throw new Error(
				`Number Pattern challenge ${challenge + 1}: episode was not unique`,
			);
		episodeIds.add(episodeId);
		const reconstruction = await fetch(
			`http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`,
			{
				headers: {
					"X-Dev-Principal": "NOT_FOR_PRODUCTION",
					"X-Dev-Role": "researcher",
				},
			},
		);
		const evidence = await reconstruction.json();
		if (!reconstruction.ok || evidence.state?.status !== "completed")
			throw new Error(
				`Number Pattern challenge ${challenge + 1}: backend episode did not complete`,
			);
		if (!evidence.state?.attempts?.at(-1)?.correct)
			throw new Error(
				`Number Pattern challenge ${challenge + 1}: fresh unsupported retry was not correct`,
			);
		if (evidence.state?.universal_skill_id !== "APT-PAT")
			throw new Error(
				`Number Pattern challenge ${challenge + 1}: evidence crossed constructs`,
			);
		if (!evidence.state?.withdrawal?.input_handlers_cleared)
			throw new Error(
				`Number Pattern challenge ${challenge + 1}: withdrawal was incomplete`,
			);
		supportTypes.add(evidence.state?.scaffold_exposure?.scaffold_type);
		const updates = evidence.state?.policy_updates?.length ?? 0;
		if (updates !== (condition === "proposed" ? 1 : 0))
			throw new Error(
				`Number Pattern challenge ${challenge + 1}: unexpected policy update count ${updates}`,
			);
		await clickText(
			cdp,
			challenge % 2 === 0
				? "ඊළඟ අභියෝගය"
				: challenge === 5
					? "ක්‍රීඩා තේරීමට"
					: "ඊළඟ ක්‍රීඩාව",
		);
	}
	if (episodeIds.size !== 6)
		throw new Error(
			"Number Pattern Adventure did not execute all six atomic skills",
		);
	const expectedSupportTypes =
		condition === "proposed"
			? ["visual_guidance", "worked_parallel_example"]
			: ["visual_guidance"];
	for (const type of expectedSupportTypes)
		if (!supportTypes.has(type))
			throw new Error(`Number Pattern Adventure did not exercise ${type}`);
}

async function runMultiplicationCoverage(cdp) {
	await waitForText(cdp, "ගුණන වගු ගවේෂණය");
	await waitForText(cdp, "අභියෝග 1ක්");
	await waitForText(cdp, "අභියෝග 3ක්");
	await clickText(cdp, "ගුණන වගු ගවේෂණය");
	await waitForSelector(cdp, "[data-kind='fact']");
	const overflow = await evaluate(
		cdp,
		"document.documentElement.scrollWidth > document.documentElement.clientWidth + 1",
	);
	if (overflow) throw new Error("multiplication table overflowed the page");
	await clickText(cdp, "ආපසු");
}

async function runTimeAdventureCoverage(cdp) {
	await waitForText(cdp, "කාල මෙවලම්");
	await waitForText(cdp, "අභියෝග 2ක්");
	await waitForText(cdp, "අභියෝග 1ක්");
	await clickText(cdp, "කාල මෙවලම්");
	await waitForSelector(cdp, ".time-adventure .unit-match select");
	const overflow = await evaluate(
		cdp,
		"document.documentElement.scrollWidth > document.documentElement.clientWidth + 1",
	);
	if (overflow) throw new Error("time adventure overflowed the page at 320px");
	await evaluate(
		cdp,
		`(() => {
			const equivalents = { '60 තත්පර': '1 මිනිත්තු', '60 මිනිත්තු': '1 පැය', '24 පැය': '1 දින', '7 දින': '1 සති', '4 සති': '1 මාස', '12 මාස': '1 අවුරුදු', '365 දින': '1 සාමාන්‍ය අවුරුද්ද', '366 දින': '1 අධික අවුරුද්ද' };
			const rows = [...document.querySelectorAll('.time-adventure .unit-match')];
			rows.forEach((row) => {
				const select = row.querySelector('select');
				const wanted = equivalents[row.querySelector('span')?.textContent?.trim()];
				const option = [...select.options].find((candidate) => candidate.textContent.trim() === wanted);
				select.value = option.value;
				select.dispatchEvent(new Event('change', { bubbles: true }));
			});
			return rows.length;
		})()`,
	);
	await clickText(cdp, "තහවුරු කරන්න");
	await waitForText(cdp, "නිවැරදියි!");
	await clickText(cdp, "ආපසු");
}

async function runMoneyAdventureCoverage(cdp) {
	await waitForText(cdp, "මුදල් හඳුනා ගනිමු");
	await waitForText(cdp, "මුදල් ගණනය කරමු");
	await waitForText(cdp, "පුංචි වෙළඳසැල");
	const labels = await evaluate(
		cdp,
		"document.querySelector('.money-adventure')?.innerText",
	);
	if (!labels.includes("අභියෝග 2ක්") || !labels.includes("අභියෝග 1ක්"))
		throw new Error("money adventure challenge counts are incorrect");
	await clickText(cdp, "මුදල් හඳුනා ගනිමු");
	await waitForSelector(cdp, ".money-adventure .currency-token");
	for (const width of [320, 390]) {
		await cdp.call("Emulation.setDeviceMetricsOverride", {
			width,
			height: width === 320 ? 568 : 844,
			deviceScaleFactor: 2,
			mobile: true,
		});
		const result = await evaluate(
			cdp,
			`(() => ({
				overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
				undersized: [...document.querySelectorAll('.money-adventure .currency-token, .money-adventure .money-trays button')].filter((node) => { const box = node.getBoundingClientRect(); return box.width < 48 || box.height < 48; }).length,
				unlabelled: [...document.querySelectorAll('.money-adventure .currency-token')].filter((node) => !node.getAttribute('aria-label')).length,
			}))()`,
		);
		if (result.overflow)
			throw new Error(`money adventure overflowed at ${width}px`);
		if (result.undersized)
			throw new Error(
				`money adventure has ${result.undersized} undersized controls at ${width}px`,
			);
		if (result.unlabelled)
			throw new Error(
				"money denomination token lacks a Sinhala accessible name",
			);
	}
	await cdp.call("Emulation.setDeviceMetricsOverride", {
		width: 320,
		height: 568,
		deviceScaleFactor: 2,
		mobile: true,
	});
	await clickText(cdp, "ආපසු");
}

async function runCapacityAdventureCoverage(cdp) {
	await waitForText(cdp, "ජල පරීක්ෂණාගාරය");
	await waitForText(cdp, "ලීටර් යන්ත්‍රය");
	await waitForText(cdp, "ජල බෙදාහැරීම");
	const labels = await evaluate(
		cdp,
		"document.querySelector('.capacity-adventure')?.innerText",
	);
	if (!labels.includes("අභියෝග 2ක්") || !labels.includes("අභියෝග 1ක්"))
		throw new Error("capacity adventure challenge counts are incorrect");
	await clickText(cdp, "ජල පරීක්ෂණාගාරය");
	await waitForSelector(cdp, ".capacity-adventure .graduated-vessel");
	for (const width of [320, 390]) {
		await cdp.call("Emulation.setDeviceMetricsOverride", {
			width,
			height: width === 320 ? 568 : 844,
			deviceScaleFactor: 2,
			mobile: true,
		});
		const result = await evaluate(
			cdp,
			`(() => ({
			overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
			marks: document.querySelectorAll('.capacity-adventure .vessel-body > button').length,
			undersized: [...document.querySelectorAll('.capacity-adventure .vessel-body > button, .capacity-adventure .pour-controls button')].filter((node) => { const box = node.getBoundingClientRect(); return box.width < 48 || box.height < 48; }).length,
			unlabelled: [...document.querySelectorAll('.capacity-adventure .vessel-body > button')].filter((node) => !node.getAttribute('aria-label')).length,
		}))()`,
		);
		if (result.overflow)
			throw new Error(`capacity adventure overflowed at ${width}px`);
		if (result.marks !== 10)
			throw new Error("capacity vessel must have ten 100 ml graduations");
		if (result.undersized)
			throw new Error(
				`capacity adventure has ${result.undersized} undersized controls at ${width}px`,
			);
		if (result.unlabelled)
			throw new Error("capacity graduation lacks a Sinhala accessible name");
	}
	await cdp.call("Emulation.setDeviceMetricsOverride", {
		width: 320,
		height: 568,
		deviceScaleFactor: 2,
		mobile: true,
	});
	await clickText(cdp, "ආපසු");
}

async function runMassAdventureCoverage(cdp) {
	await waitForText(cdp, "බර මිනුම් මධ්‍යස්ථානය");
	await waitForText(cdp, "කිලෝග්‍රෑම් යන්ත්‍රය");
	await waitForText(cdp, "වෙළඳපොළ බෙදාහැරීම");
	const labels = await evaluate(
		cdp,
		"document.querySelector('.mass-adventure')?.innerText",
	);
	if (!labels.includes("අභියෝග 2ක්") || !labels.includes("අභියෝග 1ක්"))
		throw new Error("mass adventure challenge counts are incorrect");
	await clickText(cdp, "බර මිනුම් මධ්‍යස්ථානය");
	await waitForSelector(cdp, ".mass-adventure .instrument-grid");
	for (const width of [320, 390]) {
		await cdp.call("Emulation.setDeviceMetricsOverride", {
			width,
			height: width === 320 ? 568 : 844,
			deviceScaleFactor: 2,
			mobile: true,
		});
		const result = await evaluate(
			cdp,
			`(() => ({
			overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
			instruments: document.querySelectorAll('.mass-adventure .instrument-grid > button').length,
			undersized: [...document.querySelectorAll('.mass-adventure .instrument-grid > button, .mass-adventure .weigh-object')].filter((node) => { const box = node.getBoundingClientRect(); return box.width < 48 || box.height < 48; }).length,
			unlabelled: [...document.querySelectorAll('.mass-adventure .instrument-grid > button, .mass-adventure .weigh-object')].filter((node) => !(node.getAttribute('aria-label') || node.textContent.trim())).length,
		}))()`,
		);
		if (result.overflow)
			throw new Error(`mass adventure overflowed at ${width}px`);
		if (result.instruments !== 5)
			throw new Error("mass adventure must show five weighing instruments");
		if (result.undersized)
			throw new Error(
				`mass adventure has ${result.undersized} undersized controls at ${width}px`,
			);
		if (result.unlabelled)
			throw new Error(
				"mass instrument control lacks a Sinhala accessible name",
			);
	}
	await cdp.call("Emulation.setDeviceMetricsOverride", {
		width: 320,
		height: 568,
		deviceScaleFactor: 2,
		mobile: true,
	});
	await clickText(cdp, "ආපසු");
}

async function runSubtractionCoverage(cdp, condition) {
	await waitForText(cdp, "ස්ථාන අගය වෙනස පුවරුව");
	await cdp.call("Emulation.setDeviceMetricsOverride", {
		width: 390,
		height: 844,
		deviceScaleFactor: 2,
		mobile: true,
	});
	await verifyViewportAndAccessibility(cdp, "subtraction normal phone");
	await cdp.call("Emulation.setDeviceMetricsOverride", {
		width: 568,
		height: 320,
		deviceScaleFactor: 2,
		mobile: true,
	});
	await verifyViewportAndAccessibility(cdp, "subtraction landscape");
	await cdp.call("Emulation.setDeviceMetricsOverride", {
		width: 320,
		height: 568,
		deviceScaleFactor: 2,
		mobile: true,
	});
	await verifyViewportAndAccessibility(cdp, "subtraction 320 portrait");
	await clickText(cdp, "ස්ථාන අගය වෙනස පුවරුව");
	const episodeIds = new Set();
	const supportTypes = new Set();
	for (let challenge = 0; challenge < 6; challenge += 1) {
		await waitForSelector(cdp, ".subtraction-adventure .subtraction-board");
		await completeSubtractionManipulation(cdp, false);
		await clickText(cdp, "තහවුරු කරන්න");
		await waitFor(
			cdp,
			`document.querySelector('[data-subtraction-step]')?.dataset.subtractionStep === 'feedback'`,
		);
		await clickText(cdp, "උදව්ව බලන්න");
		await waitForSelector(cdp, ".subtraction-adventure [data-support-type]");
		const supportType = await evaluate(
			cdp,
			"document.querySelector('[data-support-type]')?.dataset.supportType",
		);
		supportTypes.add(supportType);
		await completeAdaptiveSupport(cdp);
		await clickText(cdp, "උදව්ව අවසන් කරන්න");
		await waitFor(
			cdp,
			`document.querySelector('[data-subtraction-step]')?.dataset.subtractionStep === 'question'`,
		);
		if (
			await evaluate(
				cdp,
				`Boolean(document.querySelector('[data-support-visible="true"]'))`,
			)
		)
			throw new Error(
				`Subtraction challenge ${challenge + 1}: support remained visible`,
			);
		await completeSubtractionManipulation(cdp, true);
		await clickText(cdp, "තහවුරු කරන්න");
		await waitFor(
			cdp,
			`document.querySelector('[data-subtraction-step]')?.dataset.subtractionStep === 'result'`,
		);
		const episodeId = await evaluate(
			cdp,
			"document.querySelector('.subtraction-adventure')?.dataset.episodeId",
		);
		if (!episodeId || episodeIds.has(episodeId))
			throw new Error(
				`Subtraction challenge ${challenge + 1}: episode was not unique`,
			);
		episodeIds.add(episodeId);
		const reconstruction = await fetch(
			`http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`,
			{
				headers: {
					"X-Dev-Principal": "NOT_FOR_PRODUCTION",
					"X-Dev-Role": "researcher",
				},
			},
		);
		const evidence = await reconstruction.json();
		if (!reconstruction.ok || evidence.state?.status !== "completed")
			throw new Error(
				`Subtraction challenge ${challenge + 1}: backend episode did not complete`,
			);
		if (!evidence.state?.attempts?.at(-1)?.correct)
			throw new Error(
				`Subtraction challenge ${challenge + 1}: fresh unsupported retry was not correct`,
			);
		if (evidence.state?.universal_skill_id !== "MAT-OPS")
			throw new Error(
				`Subtraction challenge ${challenge + 1}: evidence crossed constructs`,
			);
		if (!evidence.state?.withdrawal?.input_handlers_cleared)
			throw new Error(
				`Subtraction challenge ${challenge + 1}: withdrawal was incomplete`,
			);
		const updates = evidence.state?.policy_updates?.length ?? 0;
		if (updates !== (condition === "proposed" ? 1 : 0))
			throw new Error(
				`Subtraction challenge ${challenge + 1}: unexpected policy update count ${updates}`,
			);
		const body = await evaluate(cdp, "document.body.innerText");
		if (/හොඳයි!|misconception|raw_independence_gain/.test(body))
			throw new Error(
				`Subtraction challenge ${challenge + 1}: research or premature success text`,
			);
		await clickText(
			cdp,
			challenge % 2 === 0
				? "ඊළඟ අභියෝගය"
				: challenge === 5
					? "ක්‍රීඩා තේරීමට"
					: "ඊළඟ ක්‍රීඩාව",
		);
	}
	if (episodeIds.size !== 6)
		throw new Error(
			"Subtraction Adventure did not execute all six atomic skills",
		);
	for (const type of ["visual_guidance", "worked_parallel_example"])
		if (!supportTypes.has(type))
			throw new Error(`Subtraction Adventure did not exercise ${type}`);
}

async function runAdditionAdventureCoverage(cdp, condition) {
	const skills = [
		["ඉක්මන් එකතු උයන", "පළතුරු එකතු කර මුළු ගණන හදමු"],
		["එකතු කිරීමේ මාර්ගය", "ටුක්-ටුක් සමුච්චිත එකතුව"],
		["ගෙනයාමේ දොඹකරය", "ගෙනයාම් දෙකක් සහිත භාණ්ඩ හුවමාරුව"],
		["ගෙනයාමේ දොඹකරය", "ගෙනයාම් දෙකකට වැඩි භාණ්ඩ හුවමාරුව"],
		["ගෙනයාමේ දොඹකරය", "භාණ්ඩ කාණ්ඩ තුනක් එකතු කරමු"],
		["වෙළඳපොළ බෙදාහැරීම් සැලසුම", "වෙළඳපොළ ඇණවුම් කරත්තයට පටවමු"],
		["ජීවමාන වගු රහස් පරීක්ෂක", "උත්සව වගුවේ අදාළ කොටු එකතු කරමු"],
		["ජීවමාන වගු රහස් පරීක්ෂක", "උත්සව එකතු දෙකක වෙනස සොයමු"],
		["ජීවමාන වගු රහස් පරීක්ෂක", "වැඩිම පේළි එකතුව සොයමු"],
	];
	const episodeIds = new Set();
	const supportTypes = new Set();
	for (const [skillIndex, [chapter, skill]] of skills.entries()) {
		if (skillIndex === 0) await clickText(cdp, chapter);
		await waitFor(
			cdp,
			`Boolean(document.querySelector('.addition-adventure .manipulation-board, [data-failure-code]'))`,
		);
		const failureCode = await evaluate(
			cdp,
			"document.querySelector('[data-failure-code]')?.dataset.failureCode",
		);
		if (failureCode) throw new Error(`${skill}: ${failureCode}`);
		await completeManipulation(cdp, ".addition-adventure");
		await clickText(cdp, "තහවුරු කරන්න");
		await waitFor(
			cdp,
			`document.querySelector('[data-addition-step]')?.dataset.additionStep === 'feedback'`,
		);
		await clickText(cdp, "උදව්ව බලන්න");
		await waitFor(
			cdp,
			`document.querySelector('.addition-adventure [data-support-type]')?.textContent.includes('උදව් වර්ගය:')`,
		);
		await completeAdaptiveSupport(cdp);
		await clickText(cdp, "උදව්ව අවසන් කරන්න");
		await waitFor(
			cdp,
			`document.querySelector('[data-addition-step]')?.dataset.additionStep === 'question'`,
		);
		if (
			await evaluate(
				cdp,
				`Boolean(document.querySelector('[data-support-visible="true"]'))`,
			)
		)
			throw new Error(`${skill}: addition support remained visible`);
		await completeManipulation(cdp, ".addition-adventure", true);
		await clickText(cdp, "තහවුරු කරන්න");
		await waitFor(
			cdp,
			`document.querySelector('[data-addition-step]')?.dataset.additionStep === 'result'`,
		);
		const visibleAnswerResult = await evaluate(
			cdp,
			"document.querySelector('.addition-adventure [data-answer-result]')?.dataset.answerResult",
		);
		const episodeId = await evaluate(
			cdp,
			"document.querySelector('.addition-adventure[data-episode-id]')?.dataset.episodeId",
		);
		if (!episodeId || episodeIds.has(episodeId))
			throw new Error(`${skill}: addition episode was not unique`);
		episodeIds.add(episodeId);
		const reconstruction = await fetch(
			`http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`,
			{
				headers: {
					"X-Dev-Principal": "NOT_FOR_PRODUCTION",
					"X-Dev-Role": "researcher",
				},
			},
		);
		const evidence = await reconstruction.json();
		if (!reconstruction.ok || evidence.state?.status !== "completed")
			throw new Error(`${skill}: addition backend episode did not complete`);
		const expectedAnswerResult = evidence.state?.attempts?.at(-1)?.correct
			? "correct"
			: "incorrect";
		if (visibleAnswerResult !== expectedAnswerResult)
			throw new Error(
				`${skill}: addition result did not match server correctness`,
			);
		if (evidence.state?.universal_skill_id !== "MAT-OPS")
			throw new Error(`${skill}: addition evidence crossed constructs`);
		supportTypes.add(evidence.state?.scaffold_exposure?.scaffold_type);
		const updates = evidence.state?.policy_updates?.length ?? 0;
		if (updates !== (condition === "proposed" ? 1 : 0))
			throw new Error(
				`${skill}: unexpected addition policy update count ${updates}`,
			);
		const nextChapter = skills[skillIndex + 1]?.[0];
		await clickText(
			cdp,
			skillIndex === skills.length - 1
				? "ක්‍රීඩා තේරීමට"
				: nextChapter === chapter
					? "ඊළඟ අභියෝගය"
					: "ඊළඟ ක්‍රීඩාව",
		);
	}
	if (episodeIds.size !== skills.length)
		throw new Error("Addition Adventure did not execute every atomic skill");
	const expectedSupportTypes =
		condition === "proposed"
			? ["visual_guidance", "worked_parallel_example"]
			: ["visual_guidance"];
	for (const type of expectedSupportTypes) {
		if (!supportTypes.has(type))
			throw new Error(`Addition Adventure did not visibly exercise ${type}`);
	}
}

async function _runLegacyNumberWorldCoverage(cdp, condition) {
	const skills = [
		["ස්ථානීය අගය වරාය", "ඉලක්කම නිවැරදි තොටුපළට ගෙන යමු"],
		["ස්ථානීය අගය වරාය", "නිරූපිත අගය සහිත බඩු ටැගය"],
		["ස්ථානීය අගය වරාය", "100 000 තෙක් සංඛ්‍යා ගොඩනඟමු"],
		["කණාමැදිරි ගණක රාමුව", "කණාමැදිරි ගණක රාමුව"],
		["කණාමැදිරි ගණක රාමුව", "සංඛ්‍යාව හා විහිදුණු ආකාරය"],
		["සංඛ්‍යා කයිට් වැඩමුළුව", "විශාලතම හෝ කුඩාතම කයිට් කේතය"],
		["සංඛ්‍යා කයිට් වැඩමුළුව", "මුල් ශූන්‍යය නොමැති කයිට් කේතය"],
		["ගඟ මාර්ග තරගය", "ගඟ හරහා සංඛ්‍යා පිළිවෙළ"],
	];
	const episodeIds = new Set();
	let supportedEpisodes = 0;
	for (const [chapter, skill] of skills) {
		await clickText(cdp, chapter);
		await clickText(cdp, skill);
		await waitForSelector(cdp, ".number-world .manipulation-board");
		await waitFor(
			cdp,
			`document.querySelector('.number-world [data-progress-stage]')?.dataset.progressStage === '1'`,
		);
		await completeManipulation(cdp, ".number-world");
		await clickText(cdp, "තහවුරු කරන්න");
		await waitFor(
			cdp,
			`document.querySelector('[data-number-world-step]')?.dataset.numberWorldStep === 'feedback'`,
		);
		const hasSupport = await evaluate(
			cdp,
			`[...document.querySelectorAll('button')].some((button) => button.textContent.includes("උදව්ව බලන්න"))`,
		);
		if (hasSupport) {
			supportedEpisodes += 1;
			await clickText(cdp, "උදව්ව බලන්න");
			await waitFor(
				cdp,
				`document.querySelector('.number-world [data-support-type]')?.textContent.includes('උදව් වර්ගය:')`,
			);
			await waitFor(
				cdp,
				`document.querySelector('.number-world [data-progress-stage]')?.dataset.progressStage === '2'`,
			);
			await completeAdaptiveSupport(cdp);
			await clickText(cdp, "උදව්ව අවසන් කරන්න");
			await waitFor(
				cdp,
				`document.querySelector('[data-number-world-step]')?.dataset.numberWorldStep === 'question'`,
			);
			await waitFor(
				cdp,
				`document.querySelector('.number-world [data-progress-stage]')?.dataset.progressStage === '3'`,
			);
			const supportStillVisible = await evaluate(
				cdp,
				`Boolean(document.querySelector('[data-support-visible="true"]'))`,
			);
			if (supportStillVisible)
				throw new Error(
					`${skill}: support remained visible after acknowledgement`,
				);
			await completeManipulation(cdp, ".number-world");
			await clickText(cdp, "තහවුරු කරන්න");
			await waitFor(
				cdp,
				`document.querySelector('[data-number-world-step]')?.dataset.numberWorldStep === 'feedback'`,
			);
			await clickText(cdp, "ඊළඟට");
		} else {
			await clickText(cdp, "ඊළඟට");
		}
		await waitFor(
			cdp,
			`document.querySelector('[data-number-world-step]')?.dataset.numberWorldStep === 'result'`,
		);
		const visibleAnswerResult = await evaluate(
			cdp,
			"document.querySelector('.number-world [data-answer-result]')?.dataset.answerResult",
		);
		await waitFor(
			cdp,
			`document.querySelector('.number-world [data-progress-stage]')?.dataset.progressStage === '4'`,
		);
		const episodeId = await evaluate(
			cdp,
			"document.querySelector('[data-episode-id]')?.dataset.episodeId",
		);
		if (!episodeId || episodeIds.has(episodeId))
			throw new Error(`${skill}: could not recover a unique episode id`);
		episodeIds.add(episodeId);
		const reconstruction = await fetch(
			`http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`,
			{
				headers: {
					"X-Dev-Principal": "NOT_FOR_PRODUCTION",
					"X-Dev-Role": "researcher",
				},
			},
		);
		const evidence = await reconstruction.json();
		if (!reconstruction.ok || evidence.state?.status !== "completed")
			throw new Error(`${skill}: backend did not complete the episode`);
		const expectedAnswerResult = evidence.state?.attempts?.at(-1)?.correct
			? "correct"
			: "incorrect";
		if (visibleAnswerResult !== expectedAnswerResult)
			throw new Error(`${skill}: result did not match server correctness`);
		if (evidence.state?.validity !== "valid")
			throw new Error(
				`${skill}: unsupported probe pair was invalid (${(evidence.state?.exclusion_reasons ?? []).join(", ")})`,
			);
		const updates = evidence.state?.policy_updates?.length ?? 0;
		if (updates !== (condition === "proposed" ? 1 : 0))
			throw new Error(
				`${skill}: unexpected ${condition} policy update count ${updates}`,
			);
		await clickText(cdp, "ආපසු");
	}
	if (episodeIds.size !== skills.length)
		throw new Error("Number World did not execute every atomic skill");
	if (supportedEpisodes === 0)
		throw new Error(
			"Number World E2E did not exercise the support-withdrawal path",
		);
	await clickText(cdp, "ස්ථානීය අගය වරාය");
	await clickText(cdp, "ඉලක්කම නිවැරදි තොටුපළට ගෙන යමු");
	await waitForSelector(cdp, ".number-world .harbour-board");
	const successEpisode = await completeCorrectNumberPosition(cdp);
	await clickText(cdp, "තහවුරු කරන්න");
	await waitForText(cdp, "හොඳයි!");
	await clickText(cdp, "ඊළඟට");
	await waitFor(
		cdp,
		`document.querySelector('[data-answer-result="correct"]') !== null`,
	);
	await waitForSelector(
		cdp,
		'.number-world .success-celebration-image[src="/curriculum/game/shared/child-celebrating-stars.png"]',
	);
	await clickText(cdp, "ඊළඟ ක්‍රීඩාව");
	await waitFor(
		cdp,
		`document.querySelector('[data-number-world-step]')?.dataset.numberWorldStep === 'question' && document.querySelector('[data-episode-id]')?.dataset.episodeId !== ${JSON.stringify(successEpisode)}`,
	);
	await clickText(cdp, "ආපසු");
}

async function runNumberWorldCoverage(cdp, condition) {
	const games = [
		"ස්ථාන අගය සොයා ගණක රාමුව හදමු",
		"විහිදුණු සංඛ්‍යාවෙන් ලක්ෂය තෙක් යමු",
		"විශාලම හා කුඩාම සංඛ්‍යා හදමු",
	];
	const challengeCounts = [3, 2, 3];
	const episodeIds = new Set();
	const supportTypes = new Set();
	for (let gameIndex = 0; gameIndex < games.length; gameIndex += 1) {
		await clickText(cdp, games[gameIndex]);
		for (
			let challengeIndex = 0;
			challengeIndex < challengeCounts[gameIndex];
			challengeIndex += 1
		) {
			await waitFor(
				cdp,
				`document.querySelector('[data-number-world-step]')?.dataset.numberWorldStep === 'question' && document.body.innerText.includes(${JSON.stringify(`අභියෝගය ${challengeIndex + 1}/${challengeCounts[gameIndex]}`)})`,
			);
			await waitFor(
				cdp,
				`document.querySelector('.number-world [data-progress-stage]')?.dataset.progressStage === ${JSON.stringify(String(gameIndex + 1))}`,
			);
			if (gameIndex === 0 && challengeIndex === 2) {
				const abacusLayout = await evaluate(
					cdp,
					`(() => {
						const board = document.querySelector('.abacus-board');
						const buttons = [...document.querySelectorAll('.abacus-step-button')];
						return {
							rods: document.querySelectorAll('.abacus-frame-rod').length,
							pageOverflows: document.documentElement.scrollWidth > window.innerWidth,
							boardOverflows: board ? board.scrollWidth > board.clientWidth : true,
							undersized: buttons.filter((button) => {
								const rect = button.getBoundingClientRect();
								return rect.width < 48 || rect.height < 48;
							}).length,
							unnamed: buttons.filter((button) => !button.getAttribute('aria-label')).length,
						};
					})()`,
				);
				if (
					abacusLayout.rods !== 6 ||
					abacusLayout.pageOverflows ||
					abacusLayout.boardOverflows ||
					abacusLayout.undersized ||
					abacusLayout.unnamed
				)
					throw new Error(
						`Abacus mobile layout invalid: ${JSON.stringify(abacusLayout)}`,
					);
			}
			if (
				await evaluate(
					cdp,
					`Boolean(document.querySelector('.place-value-table'))`,
				)
			) {
				const tableLayout = await evaluate(
					cdp,
					`(() => {
						const board = document.querySelector('.place-value-board');
						const buttons = [...document.querySelectorAll('.place-value-cell-button')];
						return {
							columns: document.querySelectorAll('.place-value-table th').length,
							pageOverflows: document.documentElement.scrollWidth > window.innerWidth,
							boardOverflows: board ? board.scrollWidth > board.clientWidth : true,
							undersized: buttons.filter((button) => {
								const rect = button.getBoundingClientRect();
								return rect.width < 48 || rect.height < 48;
							}).length,
							unnamed: buttons.filter((button) => !button.getAttribute('aria-label')).length,
						};
					})()`,
				);
				if (
					tableLayout.columns !== 6 ||
					tableLayout.pageOverflows ||
					tableLayout.boardOverflows ||
					tableLayout.undersized ||
					tableLayout.unnamed
				)
					throw new Error(
						`Place-value mobile layout invalid: ${JSON.stringify(tableLayout)}`,
					);
			}
			const episodeId = await evaluate(
				cdp,
				"document.querySelector('.number-world[data-episode-id]')?.dataset.episodeId",
			);
			if (!episodeId || episodeIds.has(episodeId))
				throw new Error("Number World challenge did not open a unique episode");
			episodeIds.add(episodeId);

			{
				await completeIncorrectNumberManipulation(cdp);
				await clickText(cdp, "තහවුරු කරන්න");
				await waitFor(
					cdp,
					`document.querySelector('[data-number-world-step]')?.dataset.numberWorldStep === 'feedback'`,
				);
				await clickText(cdp, "උදව්ව බලන්න");
				await waitForSelector(cdp, ".number-world [data-support-type]");
				const supportType = await evaluate(
					cdp,
					"document.querySelector('.number-world [data-support-type]')?.dataset.supportType",
				);
				supportTypes.add(supportType);
				await completeAdaptiveSupport(cdp);
				await clickText(cdp, "උදව්ව අවසන් කරන්න");
				await waitFor(
					cdp,
					`document.querySelector('[data-number-world-step]')?.dataset.numberWorldStep === 'question'`,
				);
			}

			await completeCorrectNumberManipulation(cdp);
			await clickText(cdp, "තහවුරු කරන්න");
			if (challengeIndex < challengeCounts[gameIndex] - 1) {
				await waitFor(
					cdp,
					`document.querySelector('[data-number-world-step]')?.dataset.numberWorldStep === 'question' && document.querySelector('[data-episode-id]')?.dataset.episodeId !== ${JSON.stringify(episodeId)}`,
				);
				const prematurePraise = await evaluate(
					cdp,
					`document.body.innerText.includes("හොඳයි!")`,
				);
				if (prematurePraise)
					throw new Error(
						"Number World showed premature praise between challenges",
					);
			} else {
				await waitForSelector(
					cdp,
					'.number-world [data-answer-result="correct"]',
				);
				await waitFor(
					cdp,
					`document.querySelector('.number-world [data-progress-stage]')?.dataset.progressStage === ${JSON.stringify(String(gameIndex + 2))}`,
				);
			}

			const reconstruction = await fetch(
				`http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`,
				{
					headers: {
						"X-Dev-Principal": "NOT_FOR_PRODUCTION",
						"X-Dev-Role": "researcher",
					},
				},
			);
			const evidence = await reconstruction.json();
			if (!reconstruction.ok || evidence.state?.status !== "completed")
				throw new Error("Number World backend challenge did not complete");
			if (
				!evidence.state?.model1 ||
				!evidence.state?.model2 ||
				evidence.state?.raw_independence_gain === null ||
				evidence.state?.scaffold_exposure?.fully_withdrawn !== true
			)
				throw new Error(
					"Number World challenge did not complete the three-model pathway",
				);
			const policyUpdates = evidence.state?.policy_updates?.length ?? 0;
			if (policyUpdates !== (condition === "proposed" ? 1 : 0))
				throw new Error(
					`Number World ${condition} challenge had ${policyUpdates} policy updates`,
				);
		}
		await clickText(cdp, gameIndex === games.length - 1 ? "ක්‍රීඩා තේරීමට" : "ආපසු");
	}
	if (episodeIds.size !== 8)
		throw new Error(
			"Number World did not execute all eight textbook challenges",
		);
	if (supportTypes.size === 0)
		throw new Error(
			`${condition}: Number World did not expose adaptive support`,
		);
}

async function completeIncorrectNumberManipulation(cdp) {
	await manipulateCurrentNumberItem(cdp, false);
}

async function completeCorrectNumberManipulation(cdp) {
	await manipulateCurrentNumberItem(cdp, true);
}

async function manipulateCurrentNumberItem(cdp, correct) {
	const episodeId = await evaluate(
		cdp,
		"document.querySelector('.number-world[data-episode-id]')?.dataset.episodeId",
	);
	const reconstruction = await fetch(
		`http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`,
		{
			headers: {
				"X-Dev-Principal": "NOT_FOR_PRODUCTION",
				"X-Dev-Role": "researcher",
			},
		},
	);
	const evidence = await reconstruction.json();
	const game = evidence.state?.presentations?.at(-1)?.game_data ?? {};
	await evaluate(
		cdp,
		`(async () => {
			const root = document.querySelector('.number-world');
			const game = ${JSON.stringify(game)};
			const correct = ${JSON.stringify(correct)};
			const pause = () => new Promise((resolve) => setTimeout(resolve, 20));
			if (root.querySelector('.milestone-options')) {
				const wanted = correct ? '100 000' : '10 000';
				[...root.querySelectorAll('.milestone-options button')].find((button) => button.textContent.trim() === wanted).click();
			} else if (root.querySelector('.expanded-form-board')) {
				const digits = String(game.number).padStart(6, '0').split('').map(Number);
				const wanted = correct ? digits : digits.map((digit, index) => index === 5 ? (digit + 1) % 10 : digit);
				const controls = root.querySelectorAll('.expanded-column');
				for (let index = 0; index < wanted.length; index += 1) {
					for (let count = 0; count < wanted[index]; count += 1) {
						controls[index].querySelector('.expanded-step-button--increment').click();
						await pause();
					}
				}
			} else if (root.querySelector('.place-value-table')) {
				const target = 6 - Number(game.place);
				const index = correct ? target : (target === 6 ? 5 : target + 1);
				root.querySelector('.place-value-table td:nth-child(' + index + ') button').click();
			} else if (root.querySelector('.abacus-board')) {
				const rods = correct ? game.rods : [1, 0, 0, 0, 0, 0];
				const controls = root.querySelectorAll('.abacus-rod-control');
				for (let index = 0; index < rods.length; index += 1) {
					for (let count = 0; count < Number(rods[index]); count += 1) {
						controls[index].querySelector('.abacus-step-button--increment').click(); await pause();
					}
				}
			} else if (root.querySelector('.kite-board')) {
				let digits = [...game.digits].sort((a, b) => game.greatest ? b - a : a - b);
				if (!correct) digits.reverse();
				if (digits[0] === 0) { const at = digits.findIndex(Boolean); [digits[0], digits[at]] = [digits[at], digits[0]]; }
				for (const value of digits) {
					[...root.querySelectorAll('.extreme-digit-circle button')].find((button) => Number(button.textContent) === value).click(); await pause();
				}
			} else if (root.querySelector('.river-board')) {
				let values = [...game.values].sort((a, b) => game.ascending ? a - b : b - a);
				if (!correct) values.reverse();
				for (const value of values) {
					[...root.querySelectorAll('.river-bank button')].find((button) => Number(button.textContent.replaceAll(',', '')) === value).click(); await pause();
				}
			}
			await pause(); return true;
		})()`,
	);
}

async function completeCorrectNumberPosition(cdp) {
	const episodeId = await evaluate(
		cdp,
		"document.querySelector('.number-world[data-episode-id]')?.dataset.episodeId",
	);
	const reconstruction = await fetch(
		`http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`,
		{
			headers: {
				"X-Dev-Principal": "NOT_FOR_PRODUCTION",
				"X-Dev-Role": "researcher",
			},
		},
	);
	const evidence = await reconstruction.json();
	const place = evidence.state?.presentations?.at(-1)?.game_data?.place;
	if (!Number.isInteger(place))
		throw new Error("Correct place-value target unavailable");
	await clickSelector(
		cdp,
		`.number-world .place-value-table td:nth-child(${6 - Number(place)}) button`,
	);
	return episodeId;
}

async function verifyViewportAndAccessibility(cdp, label) {
	const result = await evaluate(
		cdp,
		`(() => {
		const buttons = [...document.querySelectorAll('button')];
		return {
			lang: document.querySelector('main')?.getAttribute('lang'),
			overflows: document.documentElement.scrollWidth > window.innerWidth,
			reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches,
			unnamedButtons: buttons.filter((button) =>
				!(button.getAttribute('aria-label') || button.textContent.trim())
			).length,
			undersizedButtons: buttons.filter((button) => {
				const rect = button.getBoundingClientRect();
				return rect.width < 48 || rect.height < 48;
			}).length,
		};
	})()`,
	);
	if (result.lang !== "si")
		throw new Error(`${label}: app language was not Sinhala`);
	if (result.overflows)
		throw new Error(`${label}: horizontal viewport overflow detected`);
	if (!result.reducedMotion)
		throw new Error(`${label}: reduced-motion preference was not active`);
	if (result.unnamedButtons) throw new Error(`${label}: found unnamed buttons`);
	if (result.undersizedButtons)
		throw new Error(`${label}: found undersized touch targets`);
}

async function assertBrowserHealth(cdp, label) {
	const health = await evaluate(
		cdp,
		`(async () => { const urls = [...new Set(performance.getEntriesByType('resource').map((entry) => entry.name).filter((url) => url.includes('/curriculum/game/')))]; const failedAssets = []; for (const url of urls) { try { const response = await fetch(url); if (!response.ok) failedAssets.push(url + ':' + response.status); } catch (error) { failedAssets.push(url + ':' + String(error)); } } const brokenImages = [...document.images].filter((image) => image.complete && image.naturalWidth === 0).map((image) => image.src); return { errors: window.__mindbridgeE2eErrors ?? [], failedAssets, brokenImages }; })()`,
	);
	if (health.errors.length)
		throw new Error(
			`${label}: browser runtime errors: ${health.errors.join(" | ")}`,
		);
	if (health.failedAssets.length)
		throw new Error(
			`${label}: failed asset requests: ${health.failedAssets.join(" | ")}`,
		);
	if (health.brokenImages.length)
		throw new Error(
			`${label}: broken images: ${health.brokenImages.join(" | ")}`,
		);
}

async function completeSubtractionManipulation(cdp, correct) {
	const episodeId = await evaluate(
		cdp,
		"document.querySelector('.subtraction-adventure')?.dataset.episodeId",
	);
	const reconstruction = await fetch(
		`http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`,
		{
			headers: {
				"X-Dev-Principal": "NOT_FOR_PRODUCTION",
				"X-Dev-Role": "researcher",
			},
		},
	);
	const evidence = await reconstruction.json();
	const game = evidence.state?.presentations?.at(-1)?.game_data ?? {};
	await evaluate(
		cdp,
		`(async () => {
			const root = document.querySelector('.subtraction-adventure');
			const game = ${JSON.stringify(game)};
			const correct = ${JSON.stringify(correct)};
			if (!root) throw new Error('subtraction root unavailable');
			const pause = () => new Promise((resolve) => setTimeout(resolve, 40));
			const input = (element, value) => {
				const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
				setter.call(element, String(value));
				element.dispatchEvent(new Event('input', { bubbles: true }));
			};
			if (game.response_kind === 'difference_story') {
				const minuend = correct ? game.minuend_source : game.subtrahend_source;
				const subtrahend = correct ? game.subtrahend_source : game.minuend_source;
				root.querySelector('[data-source="' + minuend + '"] .story-minuend').click();
				await pause();
				root.querySelector('[data-source="' + subtrahend + '"] .story-subtrahend').click();
				await pause();
			}
			if (game.response_kind === 'expanded_subtraction') {
				const rows = ['minuend', 'subtrahend', 'adjusted', 'result'];
				const values = {
					minuend: game.minuend_terms,
					subtrahend: game.subtrahend_terms,
					adjusted: game.adjusted_terms,
					result: game.result_terms,
				};
				for (const row of rows) {
					const fields = root.querySelectorAll('[data-row="' + row + '"] input');
					values[row].forEach((value, index) => input(fields[index], correct ? value : value + 1));
					await pause();
				}
				input(root.querySelector('.expanded-result'), correct ? game.result : game.result + 1);
				await pause();
				return true;
			}
			if (correct) {
				for (const exchange of game.exchanges ?? []) {
					root.querySelector('.exchange-source[data-place="' + exchange.from_place + '"]').click();
					await pause();
					root.querySelector('.exchange-destination[data-place="' + exchange.to_place + '"]').click();
					await pause();
					root.querySelector('.exchange-apply').click();
					await pause();
				}
			}
			const digits = correct ? game.result_digits : game.result_digits.map((digit) => (digit + 1) % 10);
			const fields = root.querySelectorAll('.result-digit');
			if (!fields.length) throw new Error('result digits were not rendered');
			fields[0].focus();
			if (document.activeElement !== fields[0]) throw new Error('result digit did not receive keyboard focus');
			fields[0].dispatchEvent(new KeyboardEvent('keydown', { key: '1', bubbles: true }));
			digits.forEach((digit, index) => input(fields[index], digit));
			await pause();
			return true;
		})()`,
	);
}

async function completeNumberPatternManipulation(cdp, correct) {
	const episodeId = await evaluate(
		cdp,
		"document.querySelector('.number-pattern-adventure')?.dataset.episodeId",
	);
	const reconstruction = await fetch(
		`http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`,
		{
			headers: {
				"X-Dev-Principal": "NOT_FOR_PRODUCTION",
				"X-Dev-Role": "researcher",
			},
		},
	);
	const evidence = await reconstruction.json();
	const game = evidence.state?.presentations?.at(-1)?.game_data ?? {};
	await evaluate(
		cdp,
		`(async () => {
			const root = document.querySelector('.number-pattern-adventure');
			const game = ${JSON.stringify(game)};
			const correct = ${JSON.stringify(correct)};
			if (!root) throw new Error('number pattern root unavailable');
			const pause = () => new Promise((resolve) => setTimeout(resolve, 30));
			const input = (element, value) => {
				const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
				setter.call(element, String(value));
				element.dispatchEvent(new Event('input', { bubbles: true }));
			};
			if (game.operation !== 'multiply') {
				const label = game.operation === 'add' ? 'එකතු කිරීම තෝරන්න' : 'අඩු කිරීම තෝරන්න';
				root.querySelector('[aria-label="' + label + '"]').click();
				await pause();
			}
			const fields = root.querySelectorAll('.pattern-rule-builder input, .pattern-node input');
			input(fields[0], correct ? game.rule : game.rule + 1);
			await pause();
			const missing = game.missing_indices ?? [];
			for (let index = 0; index < missing.length; index += 1) {
				input(fields[index + 1], correct ? game.sequence[missing[index]] : 1);
				await pause();
			}
			return true;
		})()`,
	);
}

async function completeManipulation(cdp, rootSelector, correct = false) {
	const episodeId = await evaluate(
		cdp,
		`${JSON.stringify(rootSelector)} && document.querySelector(${JSON.stringify(rootSelector)})?.dataset.episodeId`,
	);
	const reconstruction = await fetch(
		`http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`,
		{
			headers: {
				"X-Dev-Principal": "NOT_FOR_PRODUCTION",
				"X-Dev-Role": "researcher",
			},
		},
	);
	const evidence = await reconstruction.json();
	const game = evidence.state?.presentations?.at(-1)?.game_data ?? {};
	await evaluate(
		cdp,
		`(async () => {
			const root = document.querySelector(${JSON.stringify(rootSelector)});
			const game = ${JSON.stringify(game)};
			const correct = ${JSON.stringify(correct)};
			if (!root) throw new Error('manipulation root unavailable');
			const pause = () => new Promise((resolve) => setTimeout(resolve, 20));
			const input = (element, value = '1') => {
				const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
				setter.call(element, value); element.dispatchEvent(new Event('input', { bubbles: true }));
			};
			if (root.querySelector('.harbour-board')) {
				const field = root.querySelector('.numeric-builder input');
				if (field) input(field);
				else if (root.querySelector('.place-value-table')) root.querySelectorAll('.place-value-table tbody button')[(6 - Number(game.place)) % 6].click();
				else root.querySelector('.milestone-options button').click();
			}
			else if (root.querySelector('.abacus-board')) root.querySelector('.abacus-step-button--increment').click();
			else if (root.querySelector('.kite-board')) {
				const wrong = [...game.digits].sort((a, b) => game.greatest ? a - b : b - a);
				if (wrong[0] === 0) { const at = wrong.findIndex(Boolean); [wrong[0], wrong[at]] = [wrong[at], wrong[0]]; }
				for (const value of wrong) { [...root.querySelectorAll('.digit-patches button')].find((button) => Number(button.textContent) === value).click(); await pause(); }
			} else if (root.querySelector('.river-board')) {
				const wrong = [...game.values].sort((a, b) => game.ascending ? b - a : a - b);
				for (const value of wrong) { [...root.querySelectorAll('.river-bank button')].find((button) => Number(button.textContent) === value).click(); await pause(); }
			} else if (root.querySelector('.fruit-catch')) {
				for (const button of root.querySelectorAll('.quantity-groups button')) { button.click(); await pause(); }
				input(root.querySelector('.numeric-builder input'), correct ? String(game.addends.reduce((sum, value) => sum + value, 0)) : '1');
			}
			else if (root.querySelector('.tuk-route')) {
				let running = Number(game.start ?? 0);
				for (const [index, field] of [...root.querySelectorAll('.addition-route input')].entries()) {
					running += Number(game.stops[index]); input(field, correct ? String(running) : '1'); await pause();
				}
			}
			else if (root.querySelector('.carry-crane')) {
				const buttons = [...root.querySelectorAll('.carry-row button')];
				const carryCount = correct ? Number(game.carrying_count) : 1;
				for (const button of buttons.slice(0, carryCount)) { button.click(); await pause(); }
				const total = correct ? String(game.addends.reduce((sum, value) => sum + value, 0)).padStart(5, '0') : '11111';
				for (const [index, field] of [...root.querySelectorAll('.answer-row input')].entries()) { input(field, total[index]); await pause(); }
			}
			else if (root.querySelector('.market-delivery')) {
				for (const button of root.querySelectorAll('.parcel-shelf button')) { button.click(); await pause(); }
				input(root.querySelector('.numeric-builder input'), correct ? String(game.addends.reduce((sum, value) => sum + value, 0)) : '1');
			}
			else if (root.querySelector('.festival-data')) {
				const buttons = [...root.querySelectorAll('.festival-data td button')];
				const cells = correct ? game.selected_cells : buttons.slice(0, game.selected_cells?.length ?? 3).map((_, index) => [0, index]);
				for (const [row, column] of cells) { buttons[row * game.table[0].length + column]?.click(); await pause(); }
				const rowTotal = (row) => row.reduce((sum, value) => sum + value, 0);
				const expected = game.target_type === 'difference'
					? Math.abs(rowTotal(game.table[game.comparison_rows[0]]) - rowTotal(game.table[game.comparison_rows[1]]))
					: game.target_type === 'maximum_row'
						? Math.max(...game.table.map(rowTotal))
						: game.selected_cells.reduce((sum, [row, column]) => sum + game.table[row][column], 0);
				input(root.querySelector('.numeric-builder input'), correct ? String(expected) : '1');
			}
			await pause(); return true;
		})()`,
	);
}

async function connectCdp(url) {
	const socket = new WebSocket(url);
	await new Promise((resolveOpen, reject) => {
		socket.onopen = resolveOpen;
		socket.onerror = reject;
	});
	let id = 0;
	const pending = new Map();
	socket.onmessage = (event) => {
		const message = JSON.parse(event.data);
		if (!message.id || !pending.has(message.id)) return;
		const { resolve: resolveCall, reject } = pending.get(message.id);
		pending.delete(message.id);
		if (message.error) reject(new Error(message.error.message));
		else resolveCall(message.result);
	};
	return {
		call(method, params = {}) {
			id += 1;
			return new Promise((resolveCall, reject) => {
				pending.set(id, { resolve: resolveCall, reject });
				socket.send(JSON.stringify({ id, method, params }));
			});
		},
		close() {
			socket.close();
		},
	};
}

async function evaluate(cdp, expression) {
	const result = await cdp.call("Runtime.evaluate", {
		expression,
		returnByValue: true,
		awaitPromise: true,
	});
	if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
	return result.result.value;
}

async function clickText(cdp, text) {
	await waitFor(
		cdp,
		`(() => {
    const button = [...document.querySelectorAll('button')].find((item) => item.textContent.includes(${JSON.stringify(text)}) || item.getAttribute('aria-label')?.includes(${JSON.stringify(text)}));
    if (!button || button.disabled) return false;
    button.click(); return true;
  })()`,
	);
}

async function clickSelector(cdp, selector) {
	await waitFor(
		cdp,
		`(() => {
		const element = document.querySelector(${JSON.stringify(selector)});
		if (!element || element.disabled) return false;
		element.click(); return true;
	})()`,
	);
}

async function completeAdaptiveSupport(cdp) {
	await waitForSelector(cdp, ".scaffold-practice button");
	for (let step = 0; step < 6; step += 1) {
		const clicked = await evaluate(
			cdp,
			`(() => { const button = document.querySelector('.scaffold-practice button'); if (!button || button.disabled) return false; button.click(); return true; })()`,
		);
		if (!clicked) break;
		await delay(50);
	}
}

async function waitForText(cdp, text) {
	await waitFor(
		cdp,
		`document.body.innerText.includes(${JSON.stringify(text)})`,
	);
}

async function waitForSelector(cdp, selector) {
	await waitFor(
		cdp,
		`Boolean(document.querySelector(${JSON.stringify(selector)}))`,
	);
}

async function waitFor(cdp, expression, timeoutMs = 10000) {
	const deadline = Date.now() + timeoutMs;
	while (Date.now() < deadline) {
		if (await evaluate(cdp, expression)) return;
		await delay(50);
	}
	const body = await evaluate(cdp, "document.body.innerText").catch(
		() => "<unavailable>",
	);
	const browserErrors = await evaluate(
		cdp,
		"window.__mindbridgeE2eErrors ?? []",
	).catch(() => []);
	const failureCode = await evaluate(
		cdp,
		"document.querySelector('[data-failure-code]')?.getAttribute('data-failure-code') ?? null",
	).catch(() => null);
	throw new Error(
		`Timed out waiting for browser expression: ${expression}\nBody: ${body}\nFailure code: ${failureCode}\nBrowser errors: ${JSON.stringify(browserErrors)}`,
	);
}

async function waitForUrl(url) {
	const deadline = Date.now() + 15000;
	while (Date.now() < deadline) {
		try {
			if ((await fetch(url)).ok) return;
		} catch {}
		await delay(100);
	}
	throw new Error(`Timed out waiting for ${url}`);
}

async function waitForJson(url) {
	const deadline = Date.now() + 10000;
	while (Date.now() < deadline) {
		try {
			const response = await fetch(url);
			if (response.ok) return response.json();
		} catch {}
		await delay(100);
	}
	throw new Error(`Timed out waiting for ${url}`);
}

function existsFile(path) {
	try {
		return statSync(path).isFile();
	} catch {
		return false;
	}
}

function delay(milliseconds) {
	return new Promise((resolveDelay) => setTimeout(resolveDelay, milliseconds));
}
