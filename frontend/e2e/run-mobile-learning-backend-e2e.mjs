import { mkdtempSync, readFileSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { dirname, extname, join, resolve } from "node:path";
import { spawn, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const root = resolve(frontend, "..");
const temporary = mkdtempSync(join(tmpdir(), "mindbridge-mobile-learning-e2e-"));
const python = resolve(root, "backend/.venv/bin/python");
const chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const processes = [];

try {
  const backend = spawn(python, ["backend/tools/mobile_learning_e2e_server.py"], {
    cwd: root,
    env: {
      ...process.env,
      PYTHONPATH: resolve(root, "backend"),
      DATABASE_URL: `sqlite:///${join(temporary, "mobile-learning.sqlite")}`,
      FRONTEND_ORIGIN: "http://127.0.0.1:4174",
    },
    stdio: ["ignore", "inherit", "inherit"],
  });
  processes.push(backend);
  await waitForUrl("http://127.0.0.1:8765/api/v1/health");

  for (const condition of ["baseline", "proposed"]) {
    const learnerId = condition === "baseline"
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
  process.stdout.write("mobile-learning real-backend E2E passed in baseline and proposed modes.\n");
} finally {
  for (const processHandle of processes) processHandle.kill("SIGTERM");
}

function build(condition, learnerId) {
  const result = spawnSync("npm", ["run", "build:web"], {
    cwd: frontend,
    env: {
      ...process.env,
      VITE_ENABLE_MOBILE_LEARNING_DRAFT: "true",
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
    const requested = request.url === "/" ? "/index.html" : request.url.split("?")[0];
    let path = resolve(dist, `.${requested}`);
    if (!path.startsWith(dist) || !existsFile(path)) path = resolve(dist, "index.html");
    response.setHeader("Content-Type", contentTypes.get(extname(path)) ?? "application/octet-stream");
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
    if (!page?.webSocketDebuggerUrl) throw new Error("Chrome page target unavailable");
    const cdp = await connectCdp(page.webSocketDebuggerUrl);
    await cdp.call("Runtime.enable");
		await cdp.call("Emulation.setDeviceMetricsOverride", {
			width: 320,
			height: 568,
			deviceScaleFactor: 2,
			mobile: true,
		});
		await cdp.call("Emulation.setEmulatedMedia", {
			features: [{ name: "prefers-reduced-motion", value: "reduce" }],
		});
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
    await clickText(cdp, "ක්‍රීඩා කර");
    await clickText(cdp, "මෙහෙයුම බලන්න");
    await clickText(cdp, "ආරම්භ කරන්න");
    await waitForText(cdp, "ඔබම උත්සාහ කරන්න");
    await clickText(cdp, "14");
    await clickText(cdp, "පිළිතුර යවන්න");
    await clickText(cdp, "ඉදිරියට");
    await waitForSelector(cdp, ".semantic-object");
    await evaluate(cdp, `(() => {
      const objects = [...document.querySelectorAll('.semantic-object')];
      if (objects.length !== 6) throw new Error('expected six semantic objects');
      objects.forEach((object, index) => object.querySelectorAll('button')[index < 3 ? 0 : 1].click());
      [...document.querySelectorAll('button')].find((button) => button.textContent.includes('සමූහ කිරීම අවසන්')).click();
    })()`);
    await clickText(cdp, "උදව් අවසන් කරන්න");
    await waitForText(cdp, "දැන් අලුත් එකක් ඔබම උත්සාහ කරන්න");
    const supportStillVisible = await evaluate(
      cdp,
      `Boolean(document.querySelector('[data-support-visible="true"], .semantic-object, canvas'))`,
    );
    if (supportStillVisible) throw new Error("support remained visible after acknowledgement");
    await clickText(cdp, "ඉදිරියට");
    await waitForText(cdp, "අලුත් එක ඔබම උත්සාහ කරන්න");
    await clickText(cdp, "18");
    await clickText(cdp, "පිළිතුර යවන්න");
    await waitForText(cdp, "හොඳ උත්සාහයක්!");
    const body = await evaluate(cdp, "document.body.innerText");
    if (/inspector|Grade 4|raw_independence_gain|misconception|policy reward/i.test(body))
      throw new Error("legacy or research-only child content was exposed");
    const resources = await evaluate(
      cdp,
      "performance.getEntriesByType('resource').map((entry) => entry.name)",
    );
    const episodeUrl = resources.find((url) => /\/episodes\/[0-9a-f-]+\/before$/.test(url));
    const episodeId = episodeUrl?.match(/\/episodes\/([0-9a-f-]+)\/before$/)?.[1];
    if (!episodeId) throw new Error("Could not recover episode id from real HTTP flow");
    const reconstruction = await fetch(
      `http://127.0.0.1:8765/api/v1/development/learning-flow/episodes/${episodeId}/reconstruction`,
      { headers: { "X-Dev-Principal": "NOT_FOR_PRODUCTION", "X-Dev-Role": "researcher" } },
    );
    const evidence = await reconstruction.json();
    if (!reconstruction.ok || evidence.state?.status !== "completed")
      throw new Error(`Backend did not complete ${condition} episode`);
    if (evidence.state.condition !== condition)
      throw new Error(`Expected ${condition}, received ${evidence.state.condition}`);
    if (!evidence.state.withdrawal?.input_handlers_cleared)
      throw new Error("Backend lacks revision-bound withdrawal evidence");
    cdp.close();
  } finally {
    browser.kill("SIGTERM");
  }
}

async function verifyViewportAndAccessibility(cdp, label) {
	const result = await evaluate(cdp, `(() => {
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
	})()`);
	if (result.lang !== "si") throw new Error(`${label}: app language was not Sinhala`);
	if (result.overflows) throw new Error(`${label}: horizontal viewport overflow detected`);
	if (!result.reducedMotion) throw new Error(`${label}: reduced-motion preference was not active`);
	if (result.unnamedButtons) throw new Error(`${label}: found unnamed buttons`);
	if (result.undersizedButtons) throw new Error(`${label}: found undersized touch targets`);
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
    close() { socket.close(); },
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
  await waitFor(cdp, `(() => {
    const button = [...document.querySelectorAll('button')].find((item) => item.textContent.includes(${JSON.stringify(text)}));
    if (!button || button.disabled) return false;
    button.click(); return true;
  })()`);
}

async function waitForText(cdp, text) {
  await waitFor(cdp, `document.body.innerText.includes(${JSON.stringify(text)})`);
}

async function waitForSelector(cdp, selector) {
  await waitFor(cdp, `Boolean(document.querySelector(${JSON.stringify(selector)}))`);
}

async function waitFor(cdp, expression, timeoutMs = 10000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await evaluate(cdp, expression)) return;
    await delay(50);
  }
  const body = await evaluate(cdp, "document.body.innerText").catch(() => "<unavailable>");
  throw new Error(`Timed out waiting for browser expression: ${expression}\nBody: ${body}`);
}

async function waitForUrl(url) {
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) {
    try { if ((await fetch(url)).ok) return; } catch {}
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
  try { return statSync(path).isFile(); } catch { return false; }
}

function delay(milliseconds) {
  return new Promise((resolveDelay) => setTimeout(resolveDelay, milliseconds));
}
