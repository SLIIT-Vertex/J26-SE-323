"""Fixture rounds for each Grade 5 area.

This service scores from the package rubric, never returns the answer key, and
does not invent learner-state behaviour fields.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.gamification.content.playable_area_package import (
    PlayableAreaItem,
    PlayableAreaRow,
    load_playable_area_package,
)

NOTICE_SI = "මෙය තවම සමාලෝචනය නොකළ කෙටුම්පතකි."
NO_GRADE5_SOURCE_NOTICE_SI = "මෙම ක්ෂේත්‍රයට 5 ශ්‍රේණියේ මූලාශ්‍රයක් නොමැත. මෙය සමාලෝචනය නොකළ සංවර්ධක කෙටුම්පතකි."
PROHIBITED_LEARNER_STATE_FIELDS = (
    "overlap_time",
    "first_action",
    "position",
    "original",
    "task_progress",
)
_ROUNDS: dict[str, dict[str, object]] = {}


class FixtureRoundError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def reset_fixture_rounds() -> None:
    _ROUNDS.clear()


class FixtureRoundService:
    def __init__(self, store: dict[str, dict[str, object]] | None = None) -> None:
        self._store = _ROUNDS if store is None else store

    def open_round(
        self,
        *,
        area_id: str,
        learner_id: UUID,
        session_id: UUID,
        grade: int,
        medium: str,
    ) -> dict[str, object]:
        if grade != 5 or medium != "si":
            raise FixtureRoundError("GRADE5_SINHALA_REQUIRED")
        package = load_playable_area_package()
        row = next((area for area in package.areas if area.area_id == area_id), None)
        if row is None:
            raise FixtureRoundError("FIXTURE_NOT_FOUND")
        if row.template_id in {"pillam_journey", "punctuation_journey", "riddle_journey"}:
            # A dedicated durable game never runs through the fixture path.
            raise FixtureRoundError("DEDICATED_GAME_REQUIRED")
        episode_id = uuid4()
        before = _item(row, "unsupported_before")
        options, correct_option_id = _options(before)
        state: dict[str, object] = {
            "episode_id": str(episode_id),
            "area_id": row.area_id,
            "template_id": row.template_id,
            "learner_id": str(learner_id),
            "session_id": str(session_id),
            "environment": "production",
            "phase": "unsupported_before",
            "row": row,
            "correct_option_id": correct_option_id,
            "scores": [],
            "evidence": [],
            "curriculum_passage_status": "NO_RELEVANT_PASSAGES",
            "mastery": None,
            "learner_state": None,
            "public_options": options,
            "public_prompt": before.prompt_si,
            "assistance_state": "none",
        }
        self._reject_fabricated_behaviour(state)
        self._store[str(episode_id)] = state
        return self._public(state)

    def answer(self, episode_id: UUID, *, option_id: str, learner_id: UUID) -> dict[str, object]:
        state = self._owned(episode_id, learner_id)
        phase = str(state["phase"])
        if phase not in {"unsupported_before", "supported_practice", "unsupported_after"}:
            raise FixtureRoundError("FIXTURE_PHASE_INVALID")
        options = state["public_options"]
        if not isinstance(options, list) or option_id not in {
            str(option["option_id"]) for option in options if isinstance(option, dict)
        }:
            raise FixtureRoundError("UNKNOWN_OPTION")
        row = state["row"]
        assert isinstance(row, PlayableAreaRow)
        item = _item(row, phase)
        earned = 1 if option_id == state["correct_option_id"] else 0
        score = {
            "earned_score": str(earned),
            "maximum_score": str(item.rubric.maximum_score),
            "scoring_version": item.rubric.scoring_version,
            "server_authoritative": True,
            "measurement_role": phase,
        }
        scores = state["scores"]
        assert isinstance(scores, list)
        scores.append(score)
        self._record_evidence(state, item, earned, option_id)
        if phase == "unsupported_before":
            state["phase"] = "support"
            state["public_options"] = []
            state["public_prompt"] = None
            state["assistance_state"] = "scaffold_active"
        elif phase == "supported_practice":
            state["phase"] = "withdraw"
            state["public_options"] = []
            state["public_prompt"] = None
            state["assistance_state"] = "none"
        else:
            state["phase"] = "completed"
            state["public_options"] = []
            state["public_prompt"] = None
            state["assistance_state"] = "none"
            state["correct_option_id"] = None
        return self._public(state)

    def continue_round(self, episode_id: UUID, *, learner_id: UUID) -> dict[str, object]:
        state = self._owned(episode_id, learner_id)
        row = state["row"]
        assert isinstance(row, PlayableAreaRow)
        phase = str(state["phase"])
        if phase == "support":
            item = _item(row, "supported_practice")
            options, correct_option_id = _options(item)
            state["phase"] = "supported_practice"
            state["public_options"] = options
            state["public_prompt"] = item.prompt_si
            state["correct_option_id"] = correct_option_id
            state["assistance_state"] = "scaffold_active"
        elif phase == "withdraw":
            item = _item(row, "unsupported_after")
            options, correct_option_id = _options(item)
            state["phase"] = "unsupported_after"
            state["public_options"] = options
            state["public_prompt"] = item.prompt_si
            state["correct_option_id"] = correct_option_id
            state["assistance_state"] = "none"
        else:
            raise FixtureRoundError("FIXTURE_PHASE_INVALID")
        return self._public(state)

    def evidence(self, episode_id: UUID) -> list[dict[str, object]]:
        state = self._get(episode_id)
        recorded = state["evidence"]
        assert isinstance(recorded, list)
        return [dict(row) for row in recorded if isinstance(row, dict)]

    def _get(self, episode_id: UUID) -> dict[str, object]:
        state = self._store.get(str(episode_id))
        if state is None:
            raise FixtureRoundError("EPISODE_NOT_FOUND")
        return state

    def _owned(self, episode_id: UUID, learner_id: UUID) -> dict[str, object]:
        state = self._get(episode_id)
        if state["learner_id"] != str(learner_id):
            raise FixtureRoundError("EPISODE_NOT_FOUND")
        return state

    def _record_evidence(
        self,
        state: dict[str, object],
        item: PlayableAreaItem,
        earned: int,
        option_id: str,
    ) -> None:
        row = state["row"]
        assert isinstance(row, PlayableAreaRow)
        role = item.measurement_role
        supported = role == "supported_practice"
        record = {
            "event_type": "gamification_item_scored",
            "attempt_id": str(uuid4()),
            "correct": earned == item.rubric.maximum_score,
            "difficulty": "easy",
            "response_time_ms": None,
            "supported": supported,
            "hint_count": 1 if supported else 0,
            "environment": state["environment"],
            "model_ingestion_eligible": False,
            "learner_id": state["learner_id"],
            "skill_id": row.area_id,
            "universal_skill_id": row.universal_skill_id,
            "measurement_role": role,
            "assistance_state": item.assistance_state,
            "earned_score": str(earned),
            "maximum_score": str(item.rubric.maximum_score),
            "scoring_version": item.rubric.scoring_version,
            "difficulty_source": "introductory",
            "difficulty_mapping_version": "learning_flow-introductory-v1",
            "session_id": state["session_id"],
            "episode_id": state["episode_id"],
            "presentation_id": str(uuid4()),
            "selected_option_id": option_id,
            "curriculum_passage_status": state["curriculum_passage_status"],
            "mastery": state["mastery"],
            "learner_state": state["learner_state"],
        }
        self._reject_fabricated_behaviour(record)
        evidence = state["evidence"]
        assert isinstance(evidence, list)
        evidence.append(record)

    def _public(self, state: dict[str, object]) -> dict[str, object]:
        row = state["row"]
        assert isinstance(row, PlayableAreaRow)
        phase = str(state["phase"])
        scores = state["scores"]
        assert isinstance(scores, list)
        support = None
        if phase in {"support", "supported_practice"}:
            support = {
                "support_type": row.scaffold.support_type,
                "body_si": row.scaffold.body_si,
                "assistance_state": "scaffold_active",
            }
        view = {
            "episode_id": state["episode_id"],
            "area_id": row.area_id,
            "template_id": row.template_id,
            "phase": phase,
            "notice_si": (
                NO_GRADE5_SOURCE_NOTICE_SI if row.source_status == "no_grade5_source" else NOTICE_SI
            ),
            "prompt_si": state["public_prompt"],
            "assistance_state": state["assistance_state"],
            "options": list(state["public_options"])
            if isinstance(state["public_options"], list)
            else [],
            "support": support,
            "server_score": scores[-1] if scores else None,
            "server_scores": list(scores),
            "reward": (
                {"points": 1, "reason_code": "episode_complete"} if phase == "completed" else None
            ),
        }
        leaked = _answer_key_text(view)
        if leaked:
            raise FixtureRoundError("ANSWER_KEY_EXPOSURE")
        return view

    @staticmethod
    def _reject_fabricated_behaviour(payload: dict[str, object]) -> None:
        present = PROHIBITED_LEARNER_STATE_FIELDS
        if any(name in payload for name in present):
            raise FixtureRoundError("LEARNER_STATE_FIELD_FABRICATED")


def _item(row: PlayableAreaRow, role: str) -> PlayableAreaItem:
    return next(item for item in row.items if item.measurement_role == role)


def _options(item: PlayableAreaItem) -> tuple[list[dict[str, str]], str]:
    parts = [part.strip() for part in item.surface_form.split("|")]
    choices = parts[1:]
    if len(parts) < 3 or item.correct_response not in choices or len(set(choices)) != len(choices):
        raise FixtureRoundError("FIXTURE_SURFACE_INVALID")
    options = [
        {"option_id": f"opt-{index + 1}", "text_si": text} for index, text in enumerate(choices)
    ]
    correct = next(
        option["option_id"] for option in options if option["text_si"] == item.correct_response
    )
    return options, correct


def _answer_key_text(value: object) -> bool:
    if isinstance(value, dict):
        if {
            "correct_response",
            "correct_option_id",
            "answer_key",
            "rubric",
            "server_answer_keys",
        } & set(value):
            return True
        return any(_answer_key_text(child) for child in value.values())
    if isinstance(value, list):
        return any(_answer_key_text(child) for child in value)
    return False
