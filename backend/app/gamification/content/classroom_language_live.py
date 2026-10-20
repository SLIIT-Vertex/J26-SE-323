"""Development-only Theme 17 Classroom Language Live content."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

AREA_ID = "G5-AREA-ENG-17"
PACKAGE_VERSION = "g5-eng-classroom-language-live-draft-v1"
CATALOGUE_VERSION = "g5-eng-classroom-language-misconceptions-v1"
FEATURE_VERSION = "g5-eng-classroom-language-features-v1"
MAPPING_VERSION = "g5-eng-classroom-language-source-mapping-v1"
MODEL_VERSION = "g5-eng-classroom-language-authored-probabilistic-v1"
POLICY_VERSION = "g5-eng-classroom-language-raw-ig-shadow-v1"
SCORING_VERSION = "g5-eng-classroom-language-constructed-scoring-v1"
EQUIVALENCE_VERSION = "g5-eng-classroom-language-parallel-v1"

Chapter = Literal[
    "phrase_portal_sort", "command_stage_director", "situation_bubble_match", "question_tile_studio"
]
Role = Literal["unsupported_before", "unsupported_after"]

SOURCE_GROUPS = {
    "Greetings and Wishes": (
        "Good Morning",
        "Good Afternoon",
        "Good Evening",
        "Good Bye",
        "Good Luck",
        "All the Best",
        "Happy Birthday",
        "Happy New Year",
        "Merry Christmas",
        "Happy Christmas",
    ),
    "Simple Commands": (
        "Hands up",
        "Hands down",
        "Run",
        "Jump",
        "Start",
        "Clap your hands",
        "Look at me",
        "Form a Line",
        "Form a Circle",
        "Don't go out",
        "Get ready",
    ),
    "Request": (
        "May I come in?",
        "May I go out?",
        "Silence Please",
        "Listen to me please",
        "Hurry up please",
        "Be quiet",
        "Be Careful",
    ),
    "Praising": ("Good", "Very good", "That's right", "Well done", "I like it"),
    "Polite Forms": ("Thank You", "Please excuse me", "I'm sorry"),
    "Simple Question Forms": (
        "Who is shouting ?",
        "What's this?",
        "What's that?",
        "What is it?",
        "Is it a ................. ?",
        "Is that a ................. ?",
        "Are you ready?",
    ),
}
COMMANDS = {
    "Hands up": "state-0",
    "Hands down": "state-1",
    "Run": "state-2",
    "Jump": "state-3",
    "Start": "state-4",
    "Clap your hands": "state-5",
    "Look at me": "state-6",
    "Form a Line": "state-7",
    "Form a Circle": "state-8",
    "Don't go out": "state-9",
    "Get ready": "state-10",
}
CONTEXTS = (
    ("scene-0", "Good Morning", 0),
    ("scene-1", "Happy Birthday", 1),
    ("scene-2", "Well done", 2),
    ("scene-3", "I'm sorry", 3),
    ("scene-4", "May I come in?", 4),
    ("scene-5", "Thank You", 5),
)
QUESTIONS = (
    ("What's this?", ("What's", "this", "?"), None),
    ("What's that?", ("What's", "that", "?"), None),
    ("Are you ready?", ("Are", "you", "ready", "?"), None),
    ("Who is shouting ?", ("Who", "is", "shouting", "?"), None),
    ("What is it?", ("What", "is", "it", "?"), None),
    ("Is it a ................. ?", ("Is", "it", "a", "?"), "blank"),
    ("Is that a ................. ?", ("Is", "that", "a", "?"), "blank"),
)
MISCONCEPTIONS = (
    "source_heading_expression_confusion",
    "written_command_action_confusion",
    "situation_expression_confusion",
    "question_word_order_confusion",
    "request_group_function_confusion",
    "greeting_wish_confusion",
    "praise_polite_form_confusion",
    "command_negation_confusion",
    "line_circle_formation_confusion",
    "contraction_or_apostrophe_confusion",
    "question_placeholder_confusion",
    "source_punctuation_confusion",
    "code_scene_ambiguity",
    "incomplete_mapping_or_omission",
    "unknown_or_other",
)
SCAFFOLDS = ("visual_guidance", "worked_parallel_example", "step_by_step_guidance")


@dataclass(frozen=True, slots=True)
class AtomicSkill:
    skill_id: str
    chapter: Chapter
    name_si: str
    difficulty: str
    response_kind: str


ATOMIC_SKILLS = (
    AtomicSkill(
        "G5-ENG-CLASS-FUNCTION-01",
        "phrase_portal_sort",
        "පාඩමේ ශීර්ෂ යටතේ වාක්‍ය ඛණ්ඩ වර්ග කිරීම",
        "easy-to-hard",
        "classroom_function_sort",
    ),
    AtomicSkill(
        "G5-ENG-CLASS-COMMAND-02",
        "command_stage_director",
        "ලිඛිත පන්ති විධාන කේත දර්ශනයක ක්‍රියාත්මක කිරීම",
        "easy-to-hard",
        "classroom_command_action",
    ),
    AtomicSkill(
        "G5-ENG-CLASS-CONTEXT-03",
        "situation_bubble_match",
        "සමාලෝචිත කල්පිත අවස්ථාවකට වාක්‍ය ඛණ්ඩයක් තේරීම",
        "easy-to-hard",
        "classroom_context_expression_links",
    ),
    AtomicSkill(
        "G5-ENG-CLASS-QUESTION-04",
        "question_tile_studio",
        "මුද්‍රිත සරල ප්‍රශ්න රටා නැවත සැකසීම",
        "easy-to-hard",
        "classroom_question_sequence",
    ),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}


@dataclass(frozen=True, slots=True)
class ClassroomLanguageItem:
    item_id: str
    revision_id: str
    parallel_family_id: str
    skill_id: str
    chapter: Chapter
    measurement_role: Role
    prompt_si: str
    options: tuple[tuple[str, str], ...]
    correct_option_id: str
    error_codes: dict[str, str]
    game_data: dict[str, object]


def _token(prefix: str, value: str, salt: str) -> str:
    return f"{prefix}-{hashlib.sha256(f'{salt}:{value}'.encode()).hexdigest()[:12]}"


def generate_item(skill_id: str, *, role: str, seed: int) -> ClassroomLanguageItem:
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("CLASSROOM_LANGUAGE_ITEM_REQUEST_INVALID")
    rng = random.Random(
        int.from_bytes(hashlib.sha256(f"{skill_id}:{role}:{seed}".encode()).digest()[:8], "big")
    )
    salt = f"{skill_id}:{role}:{seed}"
    skill = SKILLS[skill_id]
    if skill.response_kind == "classroom_function_sort":
        headings = list(SOURCE_GROUPS)
        rng.shuffle(headings)
        headings = headings[: (2 if seed % 2 == 0 else 4)]
        rows = [(heading, rng.choice(SOURCE_GROUPS[heading])) for heading in headings]
        expressions = [
            {"expression_token": _token("e", phrase, salt), "text_en": phrase} for _, phrase in rows
        ]
        zones = [
            {"heading_token": _token("h", heading, salt), "text_en": heading}
            for heading in reversed(headings)
        ]
        mapping = {
            _token("e", phrase, salt): _token("h", heading, salt) for heading, phrase in rows
        }
        game = {
            "response_kind": skill.response_kind,
            "activity_id": skill.chapter,
            "command_token": _token("cmd", "sort", salt),
            "expressions": expressions,
            "heading_zones": zones,
            "target_mapping": mapping,
        }
        prompt = "මෙම පාඩමේ එක් එක් වාක්‍ය ඛණ්ඩය තිබෙන ශීර්ෂය යටතට දමන්න."
    elif skill.response_kind == "classroom_command_action":
        command, state = rng.choice(list(COMMANDS.items()))
        actor = _token("a", "fictional-actor", salt)
        action = _token("x", state, salt)
        decoy = _token("x", "decoy", salt)
        target_state = _token("s", state, salt)
        decoy_state = _token("s", "decoy", salt)
        game = {
            "response_kind": skill.response_kind,
            "activity_id": skill.chapter,
            "command_token": _token("cmd", command, salt),
            "command_text": command,
            "actor_token": actor,
            "action_controls": [
                {
                    "action_token": action,
                    "state_token": target_state,
                    "renderer_variant": int(state.split("-")[1]),
                },
                {
                    "action_token": decoy,
                    "state_token": decoy_state,
                    "renderer_variant": (int(state.split("-")[1]) + 5) % 11,
                },
            ],
            "target_action": action,
            "target_state": target_state,
        }
        prompt = "ලිඛිත විධානය කල්පිත කේත පන්තියේ පෙන්වන්න."
    elif skill.response_kind == "classroom_context_expression_links":
        rows = list(CONTEXTS)
        rng.shuffle(rows)
        rows = rows[: (2 if seed % 2 == 0 else 4)]
        situations = [
            {"situation_token": _token("u", row[0], salt), "renderer_variant": row[2]}
            for row in rows
        ]
        expressions = [
            {"expression_token": _token("e", row[1], salt), "text_en": row[1]}
            for row in reversed(rows)
        ]
        mapping = {_token("u", row[0], salt): _token("e", row[1], salt) for row in rows}
        game = {
            "response_kind": skill.response_kind,
            "activity_id": skill.chapter,
            "command_token": _token("cmd", "context", salt),
            "situations": situations,
            "expressions": expressions,
            "target_mapping": mapping,
        }
        prompt = "කල්පිත අවස්ථාවට ගැළපෙන පාඩමේ වාක්‍ය ඛණ්ඩය සම්බන්ධ කරන්න."
    else:
        source, chunks, placeholder = rng.choice(QUESTIONS)
        token_rows = [
            {"chunk_token": _token("c", f"{index}:{chunk}", salt), "text_en": chunk}
            for index, chunk in enumerate(chunks)
        ]
        rng.shuffle(token_rows)
        ordered = [_token("c", f"{index}:{chunk}", salt) for index, chunk in enumerate(chunks)]
        game = {
            "response_kind": skill.response_kind,
            "activity_id": skill.chapter,
            "command_token": _token("cmd", source, salt),
            "prompt_token": _token("p", source, salt),
            "source_form": source,
            "chunks": token_rows,
            "required_slot_count": len(chunks),
            "placeholder_token": _token("blank", placeholder, salt) if placeholder else None,
            "target_sequence": ordered,
        }
        prompt = "වචන කොටස් තෝරා පාඩමේ ප්‍රශ්නය නිවැරදි අනුපිළිවෙළට සකසන්න."
    revision = f"{skill_id}:{role}:{seed % 100000}@v1"
    return ClassroomLanguageItem(
        f"{skill_id}:{role}",
        revision,
        f"{skill_id}:{skill.chapter}:parallel-v1",
        skill_id,
        skill.chapter,
        role,
        prompt,
        (),
        "constructed-response",
        {},
        game,
    )


def public_game_data(item: ClassroomLanguageItem) -> dict[str, object]:
    private = {"target_mapping", "target_action", "target_state", "target_sequence"}
    return {
        "chapter": item.chapter,
        **{key: value for key, value in item.game_data.items() if key not in private},
    }


def correct_response(game: Mapping[str, object]) -> dict[str, object]:
    common = {
        "command_token": str(game["command_token"]),
        "interaction_trace": ["server:correct"],
        "revisions": 0,
        "tap_alternative_used": True,
    }
    kind = game["response_kind"]
    if kind in {"classroom_function_sort", "classroom_context_expression_links"}:
        mapping = game["target_mapping"]
        assert isinstance(mapping, Mapping)
        if kind == "classroom_function_sort":
            return {
                "kind": kind,
                **common,
                "placements": [
                    {"sequence": i + 1, "expression_token": s, "heading_token": t}
                    for i, (s, t) in enumerate(mapping.items())
                ],
                "unplaced_expression_tokens": [],
                "invalid_drop_count": 0,
            }
        return {
            "kind": kind,
            **common,
            "links": [
                {"sequence": i + 1, "situation_token": s, "expression_token": t}
                for i, (s, t) in enumerate(mapping.items())
            ],
            "unlinked_situation_tokens": [],
            "invalid_link_count": 0,
        }
    if kind == "classroom_command_action":
        return {
            "kind": kind,
            **common,
            "actions": [
                {
                    "sequence": 1,
                    "actor_token": game["actor_token"],
                    "action_token": game["target_action"],
                    "target_token": None,
                }
            ],
            "final_scene_state": [game["target_state"]],
            "invalid_action_count": 0,
        }
    return {
        "kind": kind,
        **common,
        "prompt_token": game["prompt_token"],
        "ordered_chunk_tokens": list(game["target_sequence"]),
        "placeholder_token": game["placeholder_token"],
        "unused_chunk_tokens": [],
        "invalid_drop_count": 0,
    }


def validate_constructed_response(
    item: Mapping[str, object] | ClassroomLanguageItem, response: Mapping[str, object]
) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, ClassroomLanguageItem) else item["game_data"]
    if not isinstance(game, Mapping):
        raise TypeError("MALFORMED_CLASSROOM_LANGUAGE_ITEM")
    expected = correct_response(game)
    if set(response) != set(expected) or response.get("kind") != expected["kind"]:
        raise ValueError("MALFORMED_CLASSROOM_LANGUAGE_RESPONSE")
    if response.get("command_token") != game["command_token"]:
        raise ValueError("STALE_CLASSROOM_LANGUAGE_COMMAND")
    trace = response.get("interaction_trace")
    if (
        not isinstance(trace, list)
        or not trace
        or not all(isinstance(entry, str) for entry in trace)
    ):
        raise ValueError("INVALID_CLASSROOM_LANGUAGE_TRACE")
    for key in (
        "revisions",
        "invalid_drop_count"
        if "invalid_drop_count" in response
        else "invalid_link_count"
        if "invalid_link_count" in response
        else "invalid_action_count",
    ):
        if not isinstance(response[key], int) or not 0 <= response[key] <= 100:
            raise ValueError("INVALID_CLASSROOM_LANGUAGE_COUNTER")
    if not isinstance(response["tap_alternative_used"], bool):
        raise TypeError("INVALID_CLASSROOM_LANGUAGE_COUNTER")
    kind = str(response["kind"])
    if kind == "classroom_function_sort":
        rows, mapping, sk, tk, empty = (
            response["placements"],
            game["target_mapping"],
            "expression_token",
            "heading_token",
            "unplaced_expression_tokens",
        )
    elif kind == "classroom_context_expression_links":
        rows, mapping, sk, tk, empty = (
            response["links"],
            game["target_mapping"],
            "situation_token",
            "expression_token",
            "unlinked_situation_tokens",
        )
    else:
        rows = mapping = None
        sk = tk = empty = ""
    if rows is not None:
        assert isinstance(mapping, Mapping)
        if not isinstance(rows, list) or response[empty] != [] or len(rows) != len(mapping):
            raise ValueError("INCOMPLETE_CLASSROOM_LANGUAGE_RESPONSE")
        submitted: dict[str, str] = {}
        for i, row in enumerate(rows, 1):
            if (
                not isinstance(row, Mapping)
                or set(row) != {"sequence", sk, tk}
                or row["sequence"] != i
                or row[sk] not in mapping
                or row[tk] not in set(mapping.values())
            ):
                raise ValueError("INVALID_CLASSROOM_LANGUAGE_TOKEN_OR_SEQUENCE")
            submitted[str(row[sk])] = str(row[tk])
        if len(submitted) != len(rows) or len(set(submitted.values())) != len(rows):
            raise ValueError("DUPLICATE_CLASSROOM_LANGUAGE_TOKEN")
        correct = submitted == mapping
    elif kind == "classroom_command_action":
        actions = response["actions"]
        correct = (
            isinstance(actions, list)
            and len(actions) == 1
            and actions[0] == expected["actions"][0]
            and response["final_scene_state"] == expected["final_scene_state"]
        )
    else:
        ordered = response["ordered_chunk_tokens"]
        if (
            not isinstance(ordered, list)
            or len(ordered) != len(game["target_sequence"])
            or len(set(ordered)) != len(ordered)
        ):
            raise ValueError("INVALID_CLASSROOM_QUESTION_SEQUENCE")
        allowed = set(game["target_sequence"])
        if (
            set(ordered) != allowed
            or response["unused_chunk_tokens"] != []
            or response["prompt_token"] != game["prompt_token"]
            or response["placeholder_token"] != game["placeholder_token"]
        ):
            raise ValueError("INVALID_CLASSROOM_QUESTION_TOKENS")
        correct = ordered == game["target_sequence"]
    error = {
        "classroom_function_sort": "source_heading_expression_confusion",
        "classroom_command_action": "written_command_action_confusion",
        "classroom_context_expression_links": "situation_expression_confusion",
        "classroom_question_sequence": "question_word_order_confusion",
    }[kind]
    return correct, "correct" if correct else error, dict(response)


def infer_belief(
    error_code: str, *, sparse: bool = False, evidence_quality: float = 0.8
) -> dict[str, object]:
    primary = error_code if error_code in MISCONCEPTIONS else "unknown_or_other"
    confidence = 1 / len(MISCONCEPTIONS) if sparse else min(0.72, max(0.2, evidence_quality * 0.72))
    remainder = (1 - confidence) / (len(MISCONCEPTIONS) - 1)
    probabilities = {name: confidence if name == primary else remainder for name in MISCONCEPTIONS}
    return {
        "probabilities": probabilities,
        "predicted_label": primary,
        "confidence": probabilities[primary],
        "fallback_used": sparse,
    }


def scaffold_decision(
    skill_id: str, condition: str, belief: Mapping[str, object], *, seed: int
) -> dict[str, object]:
    del skill_id, seed
    return {
        "selected_action": "visual_guidance",
        "condition": condition,
        "propensity": 1.0,
        "policy_version": POLICY_VERSION,
        "eligible_actions": list(SCAFFOLDS),
        "belief_label": belief.get("predicted_label"),
    }


def worked_steps(game: Mapping[str, object], scaffold_type: str) -> list[str]:
    del game
    if scaffold_type == "visual_guidance":
        return ["වචනය, ශීර්ෂය, හෝ කේත දර්ශනයේ ලක්ෂණ සසඳන්න; පිළිතුර නොපෙන්වයි."]
    if scaffold_type == "worked_parallel_example":
        return ["නව පුහුණු කාඩ්පතක් බලමු.", "නව විකල්ප සසඳමු.", "නව ප්‍රතිචාරය සකසමු."]
    return ["පළමු කොටස තෝරන්න.", "සියලු විකල්ප සසඳන්න.", "ප්‍රතිචාරය සකසා පරීක්ෂා කරන්න."]


def package_hash() -> str:
    return hashlib.sha256(
        json.dumps(
            {"area": AREA_ID, "version": PACKAGE_VERSION, "groups": SOURCE_GROUPS}, sort_keys=True
        ).encode()
    ).hexdigest()
