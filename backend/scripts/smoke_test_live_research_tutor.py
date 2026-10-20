"""Opt-in browser-equivalent smoke call through the local research HTTP boundary."""

from __future__ import annotations

import json
import os

import httpx


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def checked(response: httpx.Response) -> dict[str, object]:
    if response.is_success:
        return {} if response.status_code == 204 else response.json()
    try:
        detail = response.json().get("detail", "request failed safely")
    except (ValueError, AttributeError):
        detail = "request failed safely"
    raise RuntimeError(f"HTTP {response.status_code}: {detail}")


def main() -> int:
    if os.environ.get("AT24_LIVE_SMOKE_ENABLED", "").casefold() != "true":
        raise PermissionError("set AT24_LIVE_SMOKE_ENABLED=true to permit the live smoke test")

    base = os.environ.get(
        "AT24_API_URL", "http://127.0.0.1:8000/api/v1/adaptive-tutor/research"
    ).rstrip("/")
    headers = {"X-Tutor-Research-Key": required("TUTOR_RESEARCH_ACCESS_KEY")}
    experimental = os.environ.get("TUTOR_PP1_EXPERIMENTAL_DEMO_ENABLED", "").casefold() == "true"
    with httpx.Client(timeout=120) as client:
        checked(client.get(f"{base}/status", headers=headers))
        started = client.post(
            f"{base}/sessions",
            headers=headers,
            json={"learner_id": required("AT24_LEARNER_ID")},
        )
        research = checked(started)
        session_headers = {
            **headers,
            "X-Tutor-Research-Session": research["session_token"],
        }
        try:
            print(f"TRUSTED_RESEARCH_SESSION_ID={research['session_id']}")
            if os.environ.get("AT24_PAUSE_FOR_LEARNER_STATE", "").casefold() != "true":
                raise PermissionError(
                    "set AT24_PAUSE_FOR_LEARNER_STATE=true; record genuine same-session Learner "
                    "State evidence, run readiness with this session ID, then continue"
                )
            input("Record and verify genuine Learner State evidence, then press Enter: ")
            response = client.post(
                f"{base}/sessions/{research['session_id']}/questions",
                headers=session_headers,
                json={
                    "student_message": required("AT24_QUESTION"),
                    "response_language": os.environ.get("AT24_LANGUAGE", "en"),
                },
            )
            turn = checked(response)
            if experimental:
                if not (
                    turn.get("delivery_authorized") is False
                    and not turn.get("response_text")
                    and turn.get("experimental_response_text")
                    and turn.get("experimental_generation_status") == "GENERATED"
                    and turn.get("experimental_provenance") == "UNREVIEWED_EXPERIMENTAL"
                    and turn.get("experimental_provider_name") == "google-gemini"
                ):
                    raise RuntimeError(
                        "experimental response was blocked safely; "
                        f"status={turn.get('status')}, issues={turn.get('context_issue_codes')}"
                    )
            elif not (
                turn.get("delivery_authorized") is True
                and turn.get("response_text")
                and turn.get("curriculum_status") == "FOUND"
                and turn.get("verification_outcome") == "PASS"
                and turn.get("verification_evidence_provenance")
            ):
                raise RuntimeError(
                    "first turn was not an authorized, RAG-grounded, independently verified response; "
                    f"status={turn.get('status')}, issues={turn.get('context_issue_codes')}"
                )
            print(json.dumps(turn, indent=2, ensure_ascii=False))

            annotation = json.loads(required("AT24_ATTEMPT_JSON"))
            if annotation.get("reviewer_confirmed") is not True:
                raise ValueError("AT24_ATTEMPT_JSON requires reviewer_confirmed=true")
            attempt = checked(
                client.post(
                    f"{base}/sessions/{research['session_id']}/interactions/"
                    f"{turn['interaction_id']}/attempts",
                    headers=session_headers,
                    json=annotation,
                )
            )
            if not attempt.get("assistance_level"):
                raise RuntimeError(
                    "controlled attempt was stored but the next Controller decision was blocked; "
                    f"status={attempt.get('status')}, issues={attempt.get('context_issue_codes')}"
                )
            if experimental and not (
                attempt.get("experimental_response_text")
                and attempt.get("experimental_generation_status") == "GENERATED"
                and attempt.get("experimental_provenance") == "UNREVIEWED_EXPERIMENTAL"
                and attempt.get("delivery_authorized") is False
            ):
                raise RuntimeError("next-turn experimental response was blocked safely")
            print(json.dumps(attempt, indent=2, ensure_ascii=False))
        finally:
            checked(
                client.delete(
                    f"{base}/sessions/{research['session_id']}", headers=session_headers
                )
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
