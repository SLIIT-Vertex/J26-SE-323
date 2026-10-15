"""Learner delivery, authoring, jobs, and privacy-safe observation for the pilot API.

The HTTP session store remains process-local. Durable rows live behind
``SqlAlchemyDeliveryStore``. Child-facing item text stays blocked unless a
separate approved catalog is injected into ``SessionPlay``.
"""

import hashlib
import json
import logging
import threading
import time
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.gamification.application.errors import PlayError
from app.gamification.application.ports import (
    AuditOutput,
    Clock,
    ConsentEligibilityGateway,
    CurriculumReferenceGateway,
    VerifiedTutorGateway,
)
from app.gamification.application.records import AuditEvent

logger = logging.getLogger("app.gamification.delivery")

JOB_KINDS = (
    "ingestion",
    "feature_construction",
    "retention_check",
    "evaluation",
    "export",
)
JOB_STATUSES = ("queued", "claimed", "succeeded", "failed")
_FORBIDDEN_LOG_KEYS = frozenset(
    {
        "answer",
        "answers",
        "correct_option_id",
        "question_text",
        "prompt",
        "payload",
        "body",
        "guardian",
        "guardian_name",
        "selected_option_id",
        "raw_text",
        "content",
    }
)
_MAX_PAGE = 50


def request_fingerprint(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def utc_now() -> datetime:
    return datetime.now(UTC)


def privacy_fields(fields: Mapping[str, object]) -> dict[str, object]:
    """Drop answer text, prompts, and free-form payloads before anything is logged."""

    return {key: value for key, value in fields.items() if key not in _FORBIDDEN_LOG_KEYS}


def privacy_log(event: str, **fields: object) -> None:
    logger.info("%s %s", event, privacy_fields(fields))


def call_within_budget[Result](operation: Callable[[], Result], *, budget_ms: int) -> Result:
    """Refuse the call when the budget is already exhausted.

    A non-positive budget is the testable timeout stand-in. The operation is not
    invoked, so a slow tutor or retriever cannot leak into the episode.
    """

    if budget_ms <= 0:
        raise PlayError("STALE_EXTERNAL_EVIDENCE", 409)
    started = time.perf_counter()
    try:
        result = operation()
    except TimeoutError as error:
        raise PlayError("STALE_EXTERNAL_EVIDENCE", 409) from error
    elapsed_ms = (time.perf_counter() - started) * 1000
    if elapsed_ms > budget_ms:
        raise PlayError("STALE_EXTERNAL_EVIDENCE", 409)
    return result


def page_slice[Item](
    items: tuple[Item, ...] | list[Item], *, cursor: str | None, limit: int
) -> tuple[list[Item], str | None]:
    if limit < 1 or limit > _MAX_PAGE:
        raise PlayError("PAYLOAD_OUT_OF_BOUNDS", 422)
    offset = 0 if cursor is None else _decode_cursor(cursor)
    if offset > len(items):
        raise PlayError("PAYLOAD_OUT_OF_BOUNDS", 422)
    window = list(items[offset : offset + limit])
    next_offset = offset + len(window)
    next_cursor = None if next_offset >= len(items) else str(next_offset)
    return window, next_cursor


def _decode_cursor(cursor: str) -> int:
    if not cursor.isdigit():
        raise PlayError("PAYLOAD_OUT_OF_BOUNDS", 422)
    return int(cursor)


@dataclass
class DeliveryMetrics:
    requests: int = 0
    errors: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    event_duplicates: int = 0
    event_quarantined: int = 0
    event_accepted: int = 0
    fallbacks: int = 0
    abstentions: int = 0
    support_failures: int = 0
    verification_unavailable: int = 0
    job_failures: int = 0
    spans: list[str] = field(default_factory=list)

    def observe(self, *, status_code: int, latency_ms: float, span: str) -> None:
        self.requests += 1
        if status_code >= 400:
            self.errors += 1
        self.latencies_ms.append(latency_ms)
        if span:
            self.spans.append(span)

    def snapshot(self) -> dict[str, object]:
        ordered = sorted(self.latencies_ms)
        p95 = ordered[min(len(ordered) - 1, int(0.95 * (len(ordered) - 1)))] if ordered else 0.0
        return {
            "requests": self.requests,
            "errors": self.errors,
            "latency_p95_ms": round(p95, 3),
            "event_accepted": self.event_accepted,
            "event_duplicates": self.event_duplicates,
            "event_quarantined": self.event_quarantined,
            "fallbacks": self.fallbacks,
            "abstentions": self.abstentions,
            "support_failures": self.support_failures,
            "verification_unavailable": self.verification_unavailable,
            "job_failures": self.job_failures,
            "spans": tuple(self.spans),
        }


METRICS = DeliveryMetrics()


class RateLimiter:
    def __init__(self, *, limit: int = 60, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window = timedelta(seconds=window_seconds)
        self._hits: dict[str, deque[datetime]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, now: datetime) -> None:
        with self._lock:
            bucket = self._hits.setdefault(key, deque())
            cutoff = now - self.window
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                raise PlayError("RATE_LIMITED", 429)
            bucket.append(now)


LIMITER = RateLimiter()


def get_rate_limiter() -> RateLimiter:
    return LIMITER


@dataclass
class DeliveryJob:
    job_id: UUID
    kind: str
    status: str
    idempotency_key: str
    payload: dict[str, str | int | bool | None]
    attempts: int = 0
    claim_token: str | None = None
    error_code: str | None = None


class JobQueue:
    """In-process queue with claim tokens. The SQL store is the durable twin."""

    def __init__(self) -> None:
        self._jobs: dict[UUID, DeliveryJob] = {}
        self._by_key: dict[str, UUID] = {}
        self._lock = threading.Lock()

    def enqueue(
        self,
        *,
        kind: str,
        idempotency_key: str,
        payload: Mapping[str, str | int | bool | None],
    ) -> DeliveryJob:
        if kind not in JOB_KINDS:
            raise PlayError("PAYLOAD_OUT_OF_BOUNDS", 422)
        safe_payload = {
            key: value for key, value in payload.items() if key not in _FORBIDDEN_LOG_KEYS
        }
        with self._lock:
            existing = self._by_key.get(idempotency_key)
            if existing is not None:
                found = self._jobs[existing]
                if found.kind != kind or found.payload != safe_payload:
                    raise PlayError("DUPLICATE_IDEMPOTENCY_KEY", 409)
                return found
            job = DeliveryJob(
                job_id=uuid4(),
                kind=kind,
                status="queued",
                idempotency_key=idempotency_key,
                payload=dict(safe_payload),
            )
            self._jobs[job.job_id] = job
            self._by_key[idempotency_key] = job.job_id
            return job

    def claim(self, worker_id: str) -> DeliveryJob | None:
        with self._lock:
            for job in self._jobs.values():
                if job.status == "queued":
                    return self._mark_claimed(job, worker_id)
        return None

    def claim_id(self, job_id: UUID, worker_id: str) -> DeliveryJob:
        with self._lock:
            job = self._jobs[job_id]
            if job.status == "succeeded":
                return job
            if job.status != "queued":
                raise PlayError("EPISODE_STATE_CONFLICT", 409)
            return self._mark_claimed(job, worker_id)

    def _mark_claimed(self, job: DeliveryJob, worker_id: str) -> DeliveryJob:
        job.status = "claimed"
        job.claim_token = worker_id
        job.attempts += 1
        return job

    def complete(self, job_id: UUID, worker_id: str) -> None:
        job = self._owned(job_id, worker_id)
        job.status = "succeeded"

    def fail(self, job_id: UUID, worker_id: str, code: str) -> None:
        job = self._owned(job_id, worker_id)
        job.status = "failed"
        job.error_code = code
        METRICS.job_failures += 1

    def get(self, job_id: UUID) -> DeliveryJob:
        try:
            return self._jobs[job_id]
        except KeyError as error:
            raise PlayError("EXPORT_NOT_FOUND", 404) from error

    def _owned(self, job_id: UUID, worker_id: str) -> DeliveryJob:
        job = self.get(job_id)
        if job.status != "claimed" or job.claim_token != worker_id:
            raise PlayError("EPISODE_STATE_CONFLICT", 409)
        return job


@dataclass
class _ContentRecord:
    content_id: str
    kind: str
    language: str
    skill_code: str
    body: dict[str, str | int | bool | None]
    status: str = "draft"
    version: int = 1
    reviewer_id: str | None = None


class LocalCurriculumGateway:
    def __init__(self) -> None:
        self._versions: dict[str, str] = {}
        self.stale: set[str] = set()

    def remember(self, source_id: str, version: str) -> None:
        self._versions[source_id] = version

    def source_version(self, source_id: str) -> str | None:
        if source_id in self.stale:
            return None
        return self._versions.get(source_id)


class LocalConsentGateway:
    def __init__(self) -> None:
        self._references: dict[tuple[UUID, str], str] = {}

    def remember(self, *, learner_id: UUID, purpose: str, reference: str) -> None:
        self._references[(learner_id, purpose)] = reference

    def reference_for(self, *, learner_id: UUID, purpose: str) -> str | None:
        return self._references.get((learner_id, purpose))


class LocalTutorGateway:
    def __init__(self) -> None:
        self._outcomes: dict[tuple[UUID, str], str] = {}
        self.timed_out = False

    def remember(self, *, learner_id: UUID, skill_id: str, token: str) -> None:
        self._outcomes[(learner_id, skill_id)] = token

    def latest_outcome(self, *, learner_id: UUID, skill_id: str, as_of: datetime) -> str | None:
        del as_of
        if self.timed_out:
            raise TimeoutError
        return self._outcomes.get((learner_id, skill_id))


class AuthoringDesk:
    """Admin and research operations. Learner item text is not returned from here."""

    def __init__(
        self,
        *,
        audit: AuditOutput,
        jobs: JobQueue | None = None,
        curriculum: CurriculumReferenceGateway | None = None,
        consent: ConsentEligibilityGateway | None = None,
        tutor: VerifiedTutorGateway | None = None,
        clock: Clock | None = None,
        budget_ms: int = 500,
    ) -> None:
        self.audit = audit
        self.jobs = jobs or JobQueue()
        self.curriculum = curriculum or LocalCurriculumGateway()
        self.consent = consent or LocalConsentGateway()
        self.tutor = tutor or LocalTutorGateway()
        self._clock = clock
        self.budget_ms = budget_ms
        self._sources: dict[str, dict[str, str]] = {}
        self._content: dict[str, _ContentRecord] = {}
        self._models: dict[str, dict[str, str | bool]] = {}
        self._exports: dict[UUID, dict[str, object]] = {}
        self._idempotency: dict[str, tuple[str, dict[str, object]]] = {}
        self._lock = threading.Lock()

    def now(self) -> datetime:
        if self._clock is None:
            return utc_now()
        return self._clock.now()

    def once(
        self, key: str, fingerprint: str, produce: Callable[[], dict[str, object]]
    ) -> dict[str, object]:
        if not key or len(key) > 128:
            raise PlayError("IDEMPOTENCY_KEY_REQUIRED", 400)
        with self._lock:
            found = self._idempotency.get(key)
            if found is not None:
                if found[0] != fingerprint:
                    raise PlayError("DUPLICATE_IDEMPOTENCY_KEY", 409)
                return found[1]
            body = produce()
            self._idempotency[key] = (fingerprint, body)
            return body

    def register_source(
        self, *, source_id: str, title: str, grade: int, language: str, version: str
    ) -> dict[str, object]:
        if grade != 5 or language != "si":
            raise PlayError("LANGUAGE_NOT_AVAILABLE", 409)
        if any(token in title.lower() for token in ("ignore previous", "system prompt")):
            title = "untrusted-source-title"
        self._sources[source_id] = {
            "source_id": source_id,
            "title": title,
            "version": version,
            "language": language,
        }
        if isinstance(self.curriculum, LocalCurriculumGateway):
            self.curriculum.remember(source_id, version)
        self._audit("curriculum_source_registered", source_id, ("SOURCE_REFERENCE",))
        return {"source_id": source_id, "status": "registered", "version": version}

    def ingest(self, source_id: str, *, text: str, idempotency_key: str) -> dict[str, object]:
        if source_id not in self._sources:
            raise PlayError("STALE_EXTERNAL_EVIDENCE", 409)
        if len(text) > 4_000:
            raise PlayError("PAYLOAD_OUT_OF_BOUNDS", 422)
        version = call_within_budget(
            lambda: self.curriculum.source_version(source_id), budget_ms=self.budget_ms
        )
        if version is None:
            raise PlayError("STALE_EXTERNAL_EVIDENCE", 409)
        # Embedded instructions stay data. They do not approve content or change the job kind.
        stored = "retained-as-data"
        job = self.jobs.enqueue(
            kind="ingestion",
            idempotency_key=idempotency_key,
            payload={"source_id": source_id, "version": version, "disposition": stored},
        )
        self._finish(job)
        self._audit("curriculum_ingested", source_id, ("UNTRUSTED_TEXT_STORED",))
        return {"source_id": source_id, "job_id": str(job.job_id), "status": job.status}

    def map_skill(
        self, *, skill_code: str, universal_skill_id: str, source_id: str, mapping_version: str
    ) -> dict[str, object]:
        if source_id not in self._sources:
            raise PlayError("STALE_EXTERNAL_EVIDENCE", 409)
        record = _ContentRecord(
            content_id=f"map:{skill_code}",
            kind="skill_mapping",
            language="si",
            skill_code=skill_code,
            body={
                "universal_skill_id": universal_skill_id,
                "source_id": source_id,
                "mapping_version": mapping_version,
            },
        )
        self._content[record.content_id] = record
        self._audit("skill_mapping_recorded", record.content_id, ("MAPPING_DRAFT",))
        return {"content_id": record.content_id, "status": "draft"}

    def create_instance(
        self,
        *,
        instance_id: str,
        skill_code: str,
        language: str,
        prompt_label: str,
        option_labels: tuple[str, ...],
    ) -> dict[str, object]:
        if language != "si":
            raise PlayError("LANGUAGE_NOT_AVAILABLE", 409)
        record = _ContentRecord(
            content_id=instance_id,
            kind="game_instance",
            language=language,
            skill_code=skill_code,
            body={
                "prompt_label": prompt_label,
                "option_count": len(option_labels),
                "labels": "|".join(option_labels),
            },
        )
        self._content[instance_id] = record
        self._audit("game_instance_drafted", instance_id, ("CONTENT_DRAFT",))
        return {"instance_id": instance_id, "status": "draft"}

    def create_support_asset(
        self, *, asset_id: str, scaffold_type: str, step_count: int
    ) -> dict[str, object]:
        record = _ContentRecord(
            content_id=asset_id,
            kind="support_asset",
            language="si",
            skill_code="",
            body={"scaffold_type": scaffold_type, "step_count": step_count},
        )
        self._content[asset_id] = record
        self._audit("support_asset_drafted", asset_id, ("CONTENT_DRAFT",))
        return {"asset_id": asset_id, "status": "draft"}

    def create_verification_pair(
        self, *, pair_id: str, baseline_instance_id: str, verification_instance_id: str
    ) -> dict[str, object]:
        if baseline_instance_id == verification_instance_id:
            raise PlayError("VERIFICATION_PAIR_UNAVAILABLE", 409)
        for instance_id in (baseline_instance_id, verification_instance_id):
            if instance_id not in self._content:
                raise PlayError("CONTENT_NOT_APPROVED", 409)
        record = _ContentRecord(
            content_id=pair_id,
            kind="verification_pair",
            language="si",
            skill_code="",
            body={
                "baseline_instance_id": baseline_instance_id,
                "verification_instance_id": verification_instance_id,
            },
        )
        self._content[pair_id] = record
        self._audit("verification_pair_drafted", pair_id, ("PAIR_DRAFT",))
        return {"pair_id": pair_id, "status": "draft"}

    def approve_content(
        self, content_id: str, *, reviewer_id: str, decision: str
    ) -> dict[str, object]:
        record = self._require(content_id)
        if decision not in {"approve", "revoke"}:
            raise PlayError("PAYLOAD_OUT_OF_BOUNDS", 422)
        if decision == "approve":
            record.status = "approved"
            record.reviewer_id = reviewer_id
            record.version += 1
            reason = "CONTENT_APPROVED"
        else:
            record.status = "revoked"
            record.version += 1
            reason = "CONTENT_REVOKED"
        self._audit("content_decision", content_id, (reason,))
        return {"content_id": content_id, "status": record.status, "version": record.version}

    def approve_model(
        self, model_id: str, *, model_version: str, artifact_digest: str, decision: str
    ) -> dict[str, object]:
        if decision not in {"approve", "revoke"}:
            raise PlayError("PAYLOAD_OUT_OF_BOUNDS", 422)
        previous = self._models.get(model_id)
        self._models[model_id] = {
            "model_id": model_id,
            "model_version": model_version,
            "artifact_digest": artifact_digest,
            "approved": decision == "approve",
            "replaces": "" if previous is None else str(previous["model_version"]),
        }
        self._audit("model_decision", model_id, (f"MODEL_{decision.upper()}",))
        return {
            "model_id": model_id,
            "approved": decision == "approve",
            "model_version": model_version,
        }

    def manifest(self, instance_id: str) -> dict[str, object]:
        record = self._content.get(instance_id)
        if record is None or record.kind != "game_instance" or record.status != "approved":
            raise PlayError("CONTENT_NOT_APPROVED", 409)
        labels = str(record.body.get("labels", "")).split("|") if record.body.get("labels") else []
        return {
            "instance_id": instance_id,
            "language": record.language,
            "skill_code": record.skill_code,
            "prompt_label": record.body.get("prompt_label"),
            "options": [
                {"option_id": str(index), "text": label} for index, label in enumerate(labels)
            ],
            "content_version": record.version,
        }

    def note_consent_reference(
        self, *, learner_id: UUID, purpose: str, reference: str, consent_version: str
    ) -> dict[str, object]:
        if isinstance(self.consent, LocalConsentGateway):
            self.consent.remember(learner_id=learner_id, purpose=purpose, reference=reference)
        self._audit("consent_reference_recorded", str(learner_id), ("CONSENT_REFERENCE",))
        return {
            "learner_id": str(learner_id),
            "purpose": purpose,
            "consent_reference": reference,
            "consent_version": consent_version,
        }

    def create_export(self, *, learner_id: UUID, purpose: str) -> dict[str, object]:
        if purpose != "research_export":
            raise PlayError("CONSENT_SCOPE_MISSING", 409)
        reference = call_within_budget(
            lambda: self.consent.reference_for(learner_id=learner_id, purpose=purpose),
            budget_ms=self.budget_ms,
        )
        if reference is None:
            raise PlayError("CONSENT_SCOPE_MISSING", 409)
        export_id = uuid4()
        self._exports[export_id] = {
            "export_id": str(export_id),
            "learner_id": str(learner_id),
            "purpose": purpose,
            "consent_reference": reference,
            "status": "succeeded",
            "records": {
                "contract_version": "gamification-research-export-v1",
                "contains_item_text": False,
                "contains_answers": False,
            },
        }
        job = self.jobs.enqueue(
            kind="export",
            idempotency_key=str(export_id),
            payload={"learner_id": str(learner_id), "purpose": purpose},
        )
        self._finish(job)
        self._audit("research_export_created", str(export_id), ("EXPORT_APPROVED",))
        return self._exports[export_id]

    def get_export(self, export_id: UUID) -> dict[str, object]:
        try:
            return self._exports[export_id]
        except KeyError as error:
            raise PlayError("EXPORT_NOT_FOUND", 404) from error

    def build_feature_snapshot(self, *, learner_id: UUID, skill_code: str) -> dict[str, object]:
        """Pre-decision features only. Verification and Independence Gain are absent."""

        tutor_token = None
        try:
            tutor_token = call_within_budget(
                lambda: self.tutor.latest_outcome(
                    learner_id=learner_id, skill_id=skill_code, as_of=self.now()
                ),
                budget_ms=self.budget_ms,
            )
        except PlayError as error:
            if error.code != "STALE_EXTERNAL_EVIDENCE":
                raise
            tutor_token = None
        snapshot = {
            "feature_definition_version": "gamification-features-v2",
            "values": {
                "skill_code": skill_code,
                "tutor_outcome_present": tutor_token is not None,
            },
            "excluded": ("independence_gain", "verification_score", "support_outcome"),
        }
        job = self.jobs.enqueue(
            kind="feature_construction",
            idempotency_key=f"features:{learner_id}:{skill_code}",
            payload={"skill_code": skill_code, "tutor_outcome_present": tutor_token is not None},
        )
        self._finish(job)
        return snapshot

    def run_retention(
        self, *, learner_id: UUID, session_events: dict[UUID, set[str]]
    ) -> dict[str, object]:
        removed = 0
        for events in session_events.values():
            removed += len(events)
            events.clear()
        job = self.jobs.enqueue(
            kind="retention_check",
            idempotency_key=f"retention:{learner_id}:{self.now().date().isoformat()}",
            payload={"learner_id": str(learner_id), "removed_event_ids": removed},
        )
        self._finish(job)
        self._audit("retention_applied", str(learner_id), ("EVENTS_CLEARED",))
        return {
            "learner_id": str(learner_id),
            "removed_event_ids": removed,
            "job_status": job.status,
        }

    def _finish(self, job: DeliveryJob) -> None:
        if job.status == "succeeded":
            return
        worker = "pilot-request"
        claimed = self.jobs.claim_id(job.job_id, worker)
        if claimed.status == "claimed" and claimed.claim_token == worker:
            self.jobs.complete(claimed.job_id, worker)

    def _require(self, content_id: str) -> _ContentRecord:
        try:
            return self._content[content_id]
        except KeyError as error:
            raise PlayError("CONTENT_NOT_APPROVED", 409) from error

    def _audit(self, event_type: str, subject_id: str, reasons: tuple[str, ...]) -> None:
        self.audit.write(
            AuditEvent(
                event_type=event_type,
                subject_id=subject_id,
                occurred_at=self.now(),
                reason_codes=reasons,
                metadata={"component": "gamification"},
            )
        )


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return ordered[index]
