"""Browser end-to-end check of the research chat through Safari WebDriver (W3C, no extra packages).

Prerequisites (all local):
  1. Safari > Settings > Advanced: "Show features for web developers"; then
     Developer: "Allow remote automation" (or run `sudo safaridriver --enable` once).
  2. Backend with FAKE Gemini (port 8001): .venv/bin/python -m scripts.serve_research_fake_gemini
  3. Frontend on that API:      VITE_API_URL=http://localhost:8001/api/v1 npm --prefix frontend run dev
  4. This script:               .venv/bin/python -m scripts.browser_e2e_research_chat

It asks the PP1 scenario question in the real UI, records six researcher-reviewed attempts through
the chevron panel, and checks levels, labels, diagnostics and the absence of learner delivery.
"""

import argparse
import base64
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from app.adaptive_tutor.infrastructure.local_research import validate_local_research_settings
from app.config import Settings
from scripts.pp1_multiturn_demo import ATTEMPTS, QUESTION, QUESTION_EXPECTED_LEVEL
from scripts.serve_research_fake_gemini import FAKE_MARKER_PATH

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = REPOSITORY_ROOT / "research/adaptive-tutor/pp1-demo/browser-e2e"
ELEMENT = "element-6066-11e4-a52e-4f735466cecf"

READ_STATE = """
const turns = [...document.querySelectorAll('.mindy-turn')];
return {
  status: document.querySelector('.mindy-topbar [role=status]')?.textContent ?? null,
  turns: turns.length,
  busy: !!document.querySelector('.mindy-typing'),
  errors: [...document.querySelectorAll('.mindy-reply-error, .mindy-banner')].map(e => e.textContent),
  levels: [...document.querySelectorAll('.research-summary-meta')].map(e => e.textContent),
  unverified: document.querySelectorAll('.mindy-answer--unverified').length,
  notVerifiedTags: [...document.querySelectorAll('.status-chip--unverified')].map(e => e.textContent.trim()),
  checkedAnswers: document.querySelectorAll('[aria-label="Mindy\\'s checked answer"]').length,
  synthetic: document.querySelectorAll('.research-summary-flag').length,
};
"""
API_ORIGINS_USED = """
return [...new Set(performance.getEntriesByType('resource')
  .map(entry => entry.name)
  .filter(name => name.includes('/adaptive-tutor/research/'))
  .map(name => new URL(name).origin))];
"""
READ_LAST_DIAGNOSTICS = """
const panels = document.querySelectorAll('details.research-details');
const last = panels[panels.length - 1];
if (!last) return null;
return {
  evidence: [...last.querySelectorAll('.evidence-list li')].map(li => [
    li.querySelector('.evidence-name')?.textContent, li.dataset.origin,
  ]),
  glance: [...last.querySelectorAll('.glance-tile')].map(t => t.textContent),
  reasons: [...last.querySelectorAll('.reason-chips li')].map(li => li.title),
  notice: last.querySelector('.draft-source small')?.textContent ?? null,
};
"""


class WebDriver:
    def __init__(self, url: str) -> None:
        self._http = httpx.Client(base_url=url, timeout=60)
        created = self._call(
            "POST", "/session", {"capabilities": {"alwaysMatch": {"browserName": "safari"}}}
        )
        self._session = created["sessionId"]

    def _call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        response = self._http.request(method, path, json=body)
        value = response.json().get("value")
        if response.status_code >= 400:
            raise RuntimeError(f"WebDriver {path}: {value}")
        return value

    def cmd(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        return self._call(method, f"/session/{self._session}{path}", body)

    def go(self, url: str) -> None:
        self.cmd("POST", "/url", {"url": url})

    def find(self, css: str) -> str:
        return self.cmd("POST", "/element", {"using": "css selector", "value": css})[ELEMENT]

    def find_all(self, css: str) -> list[str]:
        return [
            item[ELEMENT]
            for item in self.cmd("POST", "/elements", {"using": "css selector", "value": css})
        ]

    def click(self, element: str) -> None:
        self.cmd("POST", f"/element/{element}/click", {})

    def type(self, element: str, text: str) -> None:
        self.cmd("POST", f"/element/{element}/value", {"text": text})

    def clear(self, element: str) -> None:
        self.cmd("POST", f"/element/{element}/clear", {})

    def js(self, script: str, *args: Any) -> Any:
        return self.cmd("POST", "/execute/sync", {"script": script, "args": list(args)})

    def screenshot(self, path: Path) -> None:
        path.write_bytes(base64.b64decode(self.cmd("GET", "/screenshot")))

    def quit(self) -> None:
        try:
            self._call("DELETE", f"/session/{self._session}")
        finally:
            self._http.close()


def wait_for(driver: WebDriver, predicate: Any, timeout: float, what: str) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    state: dict[str, Any] = {}
    while time.monotonic() < deadline:
        state = driver.js(READ_STATE)
        if state["errors"]:
            raise RuntimeError(f"UI error while waiting for {what}: {state['errors']}")
        if predicate(state):
            return state
        time.sleep(0.5)
    raise TimeoutError(f"timed out waiting for {what}: {state}")


# Safari's WebDriver click focuses a <summary> without toggling its <details>, so disclosure
# panels are opened by script; every input that sends data is still typed and clicked.
OPEN_PANELS = """
const outer = [...document.querySelectorAll('details.research-details')].at(-1);
if (!outer) return false;
outer.open = true;
const inner = arguments[0] ? outer.querySelector('details.research-subsection:has(form.attempt-form)') : null;
if (inner) inner.open = true;
return outer.open && (!arguments[0] || (inner !== null && inner.open));
"""


def open_researcher_panel(driver: WebDriver, *, attempt_form: bool = True) -> None:
    if driver.js(OPEN_PANELS, attempt_form) is not True:
        raise RuntimeError("researcher panel could not be opened")


def record_attempt(driver: WebDriver, policy: str, correct: bool, severity: float) -> None:
    open_researcher_panel(driver)
    driver.type(driver.find("form.attempt-form input:not([type])"), policy)
    checks = driver.find_all("form.attempt-form input[type=checkbox]")
    if correct:
        driver.click(checks[0])
    else:
        field = driver.find("form.attempt-form input[type=number]")
        driver.clear(field)
        driver.type(field, str(severity))
        typed = driver.js(
            "return document.querySelector('form.attempt-form input[type=number]').value"
        )
        if typed != str(severity):
            raise RuntimeError(f"severity field shows {typed!r}, expected {severity}")
    driver.click(checks[1])
    driver.click(driver.find("form.attempt-form .attempt-submit"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--app-url", default="http://localhost:5173/#/tutor")
    parser.add_argument("--api-origin", default="http://localhost:8001")
    parser.add_argument("--webdriver-port", type=int, default=4444)
    args = parser.parse_args()
    marker = httpx.get(f"{args.api_origin}{FAKE_MARKER_PATH}", timeout=10)
    if marker.status_code != 200 or marker.json().get("provider") != "FAKE_GEMINI":
        raise SystemExit(f"{args.api_origin} is not the fake-Gemini server; refusing to run")
    policy = min(validate_local_research_settings(Settings()))
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%S")
    out = OUTPUT_DIR / stamp
    out.mkdir(parents=True, exist_ok=True)

    server = subprocess.Popen(["safaridriver", "-p", str(args.webdriver_port)])
    time.sleep(1.5)
    driver: WebDriver | None = None
    report: dict[str, Any] = {"run_at": stamp, "app_url": args.app_url, "provider": "FAKE GEMINI"}
    try:
        driver = WebDriver(f"http://127.0.0.1:{args.webdriver_port}")
        driver.go(args.app_url)
        wait_for(driver, lambda s: s["status"] == "Maths helper", 60, "research session start")
        origins = driver.js(API_ORIGINS_USED)
        if origins != [args.api_origin.rstrip("/")]:
            raise RuntimeError(
                f"frontend is calling {origins}, not the fake server; nothing was asked"
            )
        report["api_origins_used"] = origins
        report["harness_note"] = (
            "Disclosure panels opened by script (Safari WebDriver does not toggle <details> on "
            "click); question, form fields, checkboxes and submit were typed and clicked."
        )

        driver.type(driver.find("#mindy-question"), QUESTION)
        driver.click(driver.find('button[aria-label="Send"]'))
        wait_for(
            driver, lambda s: s["turns"] == 1 and not s["busy"] and s["levels"], 180, "first reply"
        )
        driver.screenshot(out / "01-question.png")

        for index, (label, correct, severity, _) in enumerate(ATTEMPTS, start=2):
            record_attempt(driver, policy, correct, severity)
            wait_for(
                driver,
                lambda s, n=index: s["turns"] == n and not s["busy"] and len(s["levels"]) == n,
                120,
                f"reply after {label}",
            )
            if label == "a4":
                driver.screenshot(out / "02-after-a4.png")

        state = driver.js(READ_STATE)
        open_researcher_panel(driver, attempt_form=False)
        diagnostics = driver.js(READ_LAST_DIAGNOSTICS)
        driver.screenshot(out / "03-final-diagnostics.png")

        levels = [text.split(" · ")[0] for text in state["levels"]]
        expected = [QUESTION_EXPECTED_LEVEL, *(attempt[3] for attempt in ATTEMPTS)]
        origins = dict(diagnostics["evidence"]) if diagnostics else {}
        checks = {
            "levels_in_ui_match_plan": levels == expected,
            "every_reply_shows_unverified_bubble": state["unverified"] == len(expected),
            "every_unverified_bubble_tagged": state["notVerifiedTags"]
            == ["Not verified"] * len(expected),
            "no_checked_answer_shown": state["checkedAnswers"] == 0,
            "synthetic_flag_visible": state["synthetic"] >= 1,
            "history_labelled_synthetic": origins.get("Help history") == "SYNTHETIC",
            "mastery_labelled_synthetic": origins.get("Mastery (knowledge tracing)") == "SYNTHETIC",
            "skill_mapping_labelled_real": origins.get("Skill mapping") == "REAL",
        }
        report.update(
            levels=levels,
            expected=expected,
            ui_state=state,
            last_diagnostics=diagnostics,
            checks=checks,
            passed=all(checks.values()),
        )
    except Exception as error:  # noqa: BLE001 - always save what was observed
        report.update(passed=False, error=f"{type(error).__name__}: {error}")
        if driver is not None:
            try:
                driver.screenshot(out / "99-failure.png")
            except Exception as screenshot_error:  # noqa: BLE001
                report["screenshot_error"] = type(screenshot_error).__name__
    finally:
        if driver is not None:
            driver.quit()
        server.terminate()
    (out / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {key: report.get(key) for key in ("passed", "levels", "checks", "error")}, indent=2
        )
    )
    return 0 if report.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
