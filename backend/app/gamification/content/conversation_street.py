"""Development-only Grade 5 English Conversation Street content."""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Literal

from app.gamification.content.simpler_items import shown_tokens, simpler_matching_item

AREA_ID = "G5-AREA-ENG-18"
UNIVERSAL_SKILL_ID = "LAN-BIL"
PACKAGE_VERSION = "g5-eng-conversation-street-draft-v1"
CATALOGUE_VERSION = "g5-eng-conversation-misconceptions-v1"
FEATURE_VERSION = "g5-eng-conversation-features-v1"
MAPPING_VERSION = "g5-eng-conversation-source-mapping-v1"
MODEL_VERSION = "g5-eng-conversation-authored-probabilistic-v1"
POLICY_VERSION = "g5-eng-conversation-raw-ig-shadow-v1"
SCORING_VERSION = "g5-eng-conversation-constructed-scoring-v1"
EQUIVALENCE_VERSION = "g5-eng-conversation-parallel-v1"
PROFILE_POLICY_VERSION = "fictional-profile-only-v1"
FRAGMENT_POLICY_VERSION = "reviewed-source-fragments-v1"
CONTEXT_VERSION = "code-scene-context-v1"

Chapter = Literal[
    "conversation_matchmaker",
    "dialogue_director",
    "fictional_profile_reply_lab",
    "show_and_tell_conversation",
]
Role = Literal["unsupported_before", "unsupported_after"]

# Immutable evidence includes the blocked rows; ACTIVE_PAIRS deliberately does not.
SOURCE_PAIRS = (
    ("What's your name?", "I am Ruwan.", "reviewed_source_profile"),
    ("How old are you?", "I am eight.", "reviewed_source_profile"),
    ("Where do you live?", "I live in Maharagama.", "reviewed_source_profile"),
    ("How many sisters do you have?", "I have one sister.", "reviewed"),
    ("How many sisters do you have?", "I have two sister.", "blocked_number_agreement"),
    (
        "How many brothers do you have?",
        "I have one brother. / Two brothers.",
        "blocked_slash_fragment",
    ),
    ("How many brothers do you have?", "I have no brothers.", "reviewed"),
    ("What's your School?", "My School is Dharmapala Vidyalaya.", "blocked_school_review"),
    ("In which grade are you?", "I'm in grade three.", "reviewed_source_profile"),
    ("Can you sing?", "Yes, I can.", "reviewed"),
    ("Can you sing?", "No, I can't. I can dance.", "reviewed"),
    ("Do you have a pet?", "Yes, I have a cat.", "reviewed_source_profile"),
    ("Do you have a pet?", "No, I don't have.", "blocked_incomplete_negative"),
    ("Do you have a pencil?", "Sorry, I don't have.", "blocked_incomplete_negative"),
    ("Do you have a piece of paper?", "Yes, here you are.", "reviewed"),
    ("Is this your pencil?", "Yes, it's mine.", "reviewed"),
    ("Is this your pencil?", "Yes, it's my pencil.", "reviewed"),
    ("Is this your pencil?", "No, it's Saman's pencil.", "reviewed_source_profile"),
    ("What do you like?", "I like buns.", "reviewed_source_profile"),
    ("Do you like ice cream?", "Yes, I do.", "reviewed"),
    ("Do you like ice cream?", "No, I don't.", "reviewed"),
    ("What is this?", "It's a bush.", "reviewed"),
    ("Who is this?", "This is my father.", "blocked_relationship_scene"),
    ("What can you see?", "I can see a house.", "reviewed"),
    ("What can you see in this picture?", "A house, a cat.", "blocked_missing_scene"),
    ("What is in my hand?", "A bag.", "reviewed_fragment"),
    ("What is in my hand?", "An umbrella.", "reviewed_fragment"),
)
BLOCKED_SOURCE_ANSWERS = frozenset(
    answer for _, answer, status in SOURCE_PAIRS if status.startswith("blocked_")
)
ACTIVE_PAIRS = tuple(
    (question, answer)
    for question, answer, status in SOURCE_PAIRS
    if status in {"reviewed", "reviewed_fragment"}
)
STANDALONE_STATEMENTS = (
    "I am Sahan.",
    "I am Sri Lankan.",
    "I am eight.",
    "I live in Nawala.",
    "I go to Dharmapala Vidyalaya.",
    "I am in grade three.",
    "I have one brother and one sister.",
    "I like red.",
    "I have a pet.",
)
PET_STATEMENTS = (
    "It is a cat.",
    "My cat is black.",
    "My cat likes milk.",
    "My cat has four legs.",
    "It has a tail.",
    "It has two eyes.",
    "It has two ears.",
    "It has a small nose.",
    "It has a small mouth.",
    "It has whiskers.",
)

FICTIONAL_PROFILES = (
    {"label": "Fictional profile A", "name": "Mina", "age": "nine", "ability": "sing"},
    {"label": "Fictional profile B", "name": "Kavi", "age": "ten", "ability": "dance"},
)
PROFILE_FRAMES = (
    ("What's your name?", ("I", "am", "{name}."), "name"),
    ("How old are you?", ("I", "am", "{age}."), "age"),
    ("Can you sing?", ("Yes,", "I", "can."), None),
)
SCENES = (
    ("bush", "What is this?", "It's a bush.", "🌿"),
    ("house", "What can you see?", "I can see a house.", "🏠"),
    ("bag", "What is in my hand?", "A bag.", "🎒"),
    ("umbrella", "What is in my hand?", "An umbrella.", "☂️"),
)
# A simpler dialogue keeps at least this many turns to order.
SIMPLER_MINIMUM_TURNS = 2
REVIEWED_DIALOGUES = (
    (
        ("Can you sing?", "speaker-a"),
        ("Yes, I can.", "speaker-b"),
        ("What do you like?", "speaker-a"),
        ("I like buns.", "speaker-b"),
    ),
    (
        ("Do you have a piece of paper?", "speaker-a"),
        ("Yes, here you are.", "speaker-b"),
        ("Is this your pencil?", "speaker-b"),
        ("Yes, it's mine.", "speaker-a"),
    ),
)

MISCONCEPTIONS = (
    "question_response_function_mismatch",
    "dialogue_turn_order_confusion",
    "speaker_role_assignment_confusion",
    "wh_question_response_type_confusion",
    "yes_no_response_polarity_confusion",
    "can_do_have_is_response_frame_confusion",
    "this_your_mine_possession_confusion",
    "singular_plural_number_agreement_confusion",
    "article_a_an_confusion",
    "full_form_contraction_confusion",
    "profile_fact_selection_confusion",
    "scene_referent_confusion",
    "description_subject_pronoun_confusion",
    "source_error_or_normalization_confusion",
    "fragment_full_sentence_policy_confusion",
    "multiple_valid_response_ambiguity",
    "code_scene_or_speaker_ambiguity",
    "incomplete_response_or_omission",
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
        "G5-ENG-CONV-PAIR-01",
        "conversation_matchmaker",
        "ප්‍රශ්නයට පිළිතුර සම්බන්ධ කිරීම",
        "easy-to-hard",
        "conversation_pair_links",
    ),
    AtomicSkill(
        "G5-ENG-CONV-TURN-02",
        "dialogue_director",
        "සංවාද වාර අනුපිළිවෙළ",
        "easy-to-hard",
        "conversation_turn_sequence",
    ),
    AtomicSkill(
        "G5-ENG-CONV-FRAME-03",
        "fictional_profile_reply_lab",
        "චරිතයක පිළිතුර සකසීම",
        "easy-to-hard",
        "fictional_profile_reply",
    ),
    AtomicSkill(
        "G5-ENG-CONV-DESCRIBE-04",
        "show_and_tell_conversation",
        "කේත දර්ශනයකට පිළිතුර",
        "easy-to-hard",
        "conversation_scene_reply",
    ),
)
SKILLS = {skill.skill_id: skill for skill in ATOMIC_SKILLS}


@dataclass(frozen=True, slots=True)
class ConversationStreetItem:
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


def generate_item(skill_id: str, *, role: str, seed: int) -> ConversationStreetItem:
    if skill_id not in SKILLS or role not in {"unsupported_before", "unsupported_after"}:
        raise ValueError("CONVERSATION_STREET_ITEM_REQUEST_INVALID")
    rng = random.Random(
        int.from_bytes(hashlib.sha256(f"{skill_id}:{role}:{seed}".encode()).digest()[:8], "big")
    )
    salt = f"{skill_id}:{role}:{seed}"
    skill = SKILLS[skill_id]
    common = {
        "response_kind": skill.response_kind,
        "activity_id": skill.chapter,
        "command_token": _token("cmd", skill.chapter, salt),
        "profile_policy_version": PROFILE_POLICY_VERSION,
        "fragment_policy_version": FRAGMENT_POLICY_VERSION,
        "context_version": CONTEXT_VERSION,
        "fictional_notice": "Talk as the fictional characters. Do not share facts about yourself.",
    }
    if skill.response_kind == "conversation_pair_links":
        rows: list[tuple[str, str]] = []
        for pair in rng.sample(list(ACTIVE_PAIRS), len(ACTIVE_PAIRS)):
            if pair[0] not in {question for question, _ in rows}:
                rows.append(pair)
            if len(rows) == 2:
                break
        questions = [{"question_token": _token("q", q, salt), "text_en": q} for q, _ in rows]
        responses = [
            {"response_token": _token("r", a, salt), "text_en": a} for _, a in reversed(rows)
        ]
        mapping = {_token("q", q, salt): _token("r", a, salt) for q, a in rows}
        game = {**common, "questions": questions, "responses": responses, "target_mapping": mapping}
        prompt = "සංවාදයේ සෑම ප්‍රශ්නයකටම ගැළපෙන පිළිතුර සම්බන්ධ කරන්න."
    elif skill.response_kind == "conversation_turn_sequence":
        dialogue = rng.choice(REVIEWED_DIALOGUES)
        speakers = {name: _token("sp", name, salt) for name in {speaker for _, speaker in dialogue}}
        turns = [
            {
                "turn_token": _token("t", f"{i}:{text}", salt),
                "text_en": text,
                "speaker_token": speakers[speaker],
            }
            for i, (text, speaker) in enumerate(dialogue)
        ]
        target_sequence = [row["turn_token"] for row in turns]
        target_speakers = {row["turn_token"]: row["speaker_token"] for row in turns}
        rng.shuffle(turns)
        game = {
            **common,
            "dialogue_token": _token("d", "reviewed-dialogue", salt),
            "speaker_labels": [
                {"speaker_token": token, "label": f"Fictional speaker {i + 1}"}
                for i, token in enumerate(speakers.values())
            ],
            "turns": turns,
            "target_sequence": target_sequence,
            "target_speakers": target_speakers,
        }
        prompt = "සංවාදයේ වාර නිවැරදි අනුපිළිවෙළට දමන්න."
    elif skill.response_kind == "fictional_profile_reply":
        profile = rng.choice(FICTIONAL_PROFILES)
        question, frame, fact = rng.choice(PROFILE_FRAMES)
        chunks = tuple(part.format(**profile) for part in frame)
        rows = [
            {"chunk_token": _token("c", f"{i}:{part}", salt), "text_en": part}
            for i, part in enumerate(chunks)
        ]
        target = [row["chunk_token"] for row in rows]
        rng.shuffle(rows)
        game = {
            **common,
            "profile_token": _token("p", profile["label"], salt),
            "profile_label": profile["label"],
            "profile_facts": [
                {"fact_token": _token("f", key, salt), "label": key.title(), "value": value}
                for key, value in profile.items()
                if key in {"name", "age", "ability"}
            ],
            "question_token": _token("q", question, salt),
            "question_text": question,
            "chunks": rows,
            "required_slot_count": len(rows),
            "target_sequence": target,
            "bound_fact": fact,
        }
        prompt = "ඔබ ගැන නොව, මේ චරිත කාඩ්පතෙන් පිළිතුර සකසන්න."
    else:
        scene, question, answer, emoji = rng.choice(SCENES)
        decoy = next(row[2] for row in SCENES if row[0] != scene)
        response_rows = [
            {"response_token": _token("r", answer, salt), "text_en": answer},
            {"response_token": _token("r", decoy, salt), "text_en": decoy},
        ]
        rng.shuffle(response_rows)
        game = {
            **common,
            "scene_token": _token("s", scene, salt),
            "scene_renderer": {
                "variant": [row[0] for row in SCENES].index(scene),
                "emoji": emoji,
                "non_colour_cue": scene,
            },
            "prompt_token": _token("q", question, salt),
            "prompt_text": question,
            "responses": response_rows,
            "response_mode": "select_one",
            "target_response": _token("r", answer, salt),
        }
        prompt = "දර්ශනයට ගැළපෙන පිළිතුර තෝරන්න."
    revision = f"{skill_id}:{role}:{seed % 100000}@v1"
    return ConversationStreetItem(
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

def generate_simpler_item(skill_id: str, *, seed: int, than: Mapping[str, object]) -> ConversationStreetItem | None:
    """The same game and skill with fewer pairs to link than the failed game, from a fresh item."""

    item = generate_item(skill_id, role="unsupported_before", seed=seed)
    if item.game_data["response_kind"] == "conversation_turn_sequence":
        return _shorter_dialogue(item)
    return simpler_matching_item(item, than=than)


def _shorter_dialogue(item: ConversationStreetItem) -> ConversationStreetItem | None:
    """The same reviewed dialogue without its last turn: fewer turns to put in order.

    Turns are whole utterances, so the opening turns are still a dialogue. Sentence chunks are
    not shortened this way, because a cut sentence is no longer English.
    """

    game = dict(item.game_data)
    sequence = list(game["target_sequence"])  # type: ignore[call-overload]
    if len(sequence) <= SIMPLER_MINIMUM_TURNS:
        return None
    kept = sequence[:-1]
    speakers = game["target_speakers"]
    assert isinstance(speakers, Mapping)
    game.update(
        turns=[row for row in game["turns"] if row["turn_token"] in kept],  # type: ignore[union-attr,index]
        target_sequence=kept,
        target_speakers={token: speakers[token] for token in kept},
    )
    stem, _, version = item.revision_id.rpartition("@")
    return replace(item, game_data=game, revision_id=f"{stem}:simpler@{version}")



def public_game_data(item: ConversationStreetItem) -> dict[str, object]:
    private = {
        "target_mapping",
        "target_sequence",
        "target_speakers",
        "target_response",
        "bound_fact",
    }
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
    if kind == "conversation_pair_links":
        mapping = game["target_mapping"]
        assert isinstance(mapping, Mapping)
        return {
            "kind": kind,
            **common,
            "links": [
                {"sequence": i + 1, "question_token": q, "response_token": r}
                for i, (q, r) in enumerate(mapping.items())
            ],
            "unlinked_question_tokens": [],
            "invalid_link_count": 0,
        }
    if kind == "conversation_turn_sequence":
        sequence = list(game["target_sequence"])
        speakers = game["target_speakers"]
        assert isinstance(speakers, Mapping)
        return {
            "kind": kind,
            **common,
            "dialogue_token": game["dialogue_token"],
            "ordered_turn_tokens": sequence,
            "speaker_assignments": [
                {"turn_token": token, "speaker_token": speakers[token]} for token in sequence
            ],
            "unused_turn_tokens": [],
            "invalid_drop_count": 0,
        }
    if kind == "fictional_profile_reply":
        return {
            "kind": kind,
            **common,
            "profile_token": game["profile_token"],
            "question_token": game["question_token"],
            "ordered_chunk_tokens": list(game["target_sequence"]),
            "unused_chunk_tokens": [],
            "invalid_drop_count": 0,
        }
    return {
        "kind": kind,
        **common,
        "scene_token": game["scene_token"],
        "prompt_token": game["prompt_token"],
        "response_token": game["target_response"],
        "ordered_chunk_tokens": [],
        "ordered_statement_tokens": [],
        "invalid_action_count": 0,
    }


def validate_constructed_response(
    item: Mapping[str, object] | ConversationStreetItem, response: Mapping[str, object]
) -> tuple[bool, str, dict[str, object]]:
    game = item.game_data if isinstance(item, ConversationStreetItem) else item["game_data"]
    if not isinstance(game, Mapping):
        raise TypeError("MALFORMED_CONVERSATION_STREET_ITEM")
    expected = correct_response(game)
    if set(response) != set(expected) or response.get("kind") != expected["kind"]:
        raise ValueError("MALFORMED_CONVERSATION_STREET_RESPONSE")
    if response.get("command_token") != game["command_token"]:
        raise ValueError("STALE_CONVERSATION_STREET_COMMAND")
    trace = response.get("interaction_trace")
    if not isinstance(trace, list) or not trace or not all(isinstance(row, str) for row in trace):
        raise ValueError("INVALID_CONVERSATION_STREET_TRACE")
    counter = next(
        key
        for key in ("invalid_link_count", "invalid_drop_count", "invalid_action_count")
        if key in response
    )
    if (
        not isinstance(response[counter], int)
        or not 0 <= response[counter] <= 100
        or not isinstance(response["revisions"], int)
        or not 0 <= response["revisions"] <= 100
    ):
        raise ValueError("INVALID_CONVERSATION_STREET_COUNTER")
    if not isinstance(response["tap_alternative_used"], bool):
        raise TypeError("INVALID_CONVERSATION_STREET_COUNTER")
    kind = str(response["kind"])
    if kind == "conversation_pair_links":
        rows = response["links"]
        mapping = game["target_mapping"]
        assert isinstance(mapping, Mapping)
        if (
            not isinstance(rows, list)
            or response["unlinked_question_tokens"] != []
            or len(rows) != len(mapping)
        ):
            raise ValueError("INCOMPLETE_CONVERSATION_STREET_RESPONSE")
        submitted = {}
        for i, row in enumerate(rows, 1):
            if (
                not isinstance(row, Mapping)
                or set(row) != {"sequence", "question_token", "response_token"}
                or row["sequence"] != i
                or row["question_token"] not in mapping
                or row["response_token"] not in set(mapping.values()) | shown_tokens(game, "response_token")
            ):
                raise ValueError("INVALID_CONVERSATION_STREET_TOKEN")
            submitted[str(row["question_token"])] = str(row["response_token"])
        if len(submitted) != len(rows) or len(set(submitted.values())) != len(rows):
            raise ValueError("DUPLICATE_CONVERSATION_STREET_TOKEN")
        correct = submitted == mapping
    elif kind == "conversation_turn_sequence":
        allowed = set(game["target_sequence"])
        ordered = response["ordered_turn_tokens"]
        assignments = response["speaker_assignments"]
        if (
            not isinstance(ordered, list)
            or set(ordered) != allowed
            or len(ordered) != len(allowed)
            or response["unused_turn_tokens"] != []
        ):
            raise ValueError("INVALID_CONVERSATION_TURN_SEQUENCE")
        if (
            response["dialogue_token"] != game["dialogue_token"]
            or not isinstance(assignments, list)
            or {row["turn_token"]: row["speaker_token"] for row in assignments}
            != game["target_speakers"]
        ):
            raise ValueError("INVALID_CONVERSATION_SPEAKER_ASSIGNMENT")
        correct = ordered == game["target_sequence"]
    elif kind == "fictional_profile_reply":
        ordered = response["ordered_chunk_tokens"]
        target = game["target_sequence"]
        if (
            response["profile_token"] != game["profile_token"]
            or response["question_token"] != game["question_token"]
            or not isinstance(ordered, list)
            or set(ordered) != set(target)
            or response["unused_chunk_tokens"] != []
        ):
            raise ValueError("INVALID_FICTIONAL_PROFILE_REPLY")
        correct = ordered == target
    else:
        allowed = {row["response_token"] for row in game["responses"]}
        if (
            response["scene_token"] != game["scene_token"]
            or response["prompt_token"] != game["prompt_token"]
            or response["response_token"] not in allowed
            or response["ordered_chunk_tokens"] != []
            or response["ordered_statement_tokens"] != []
        ):
            raise ValueError("INVALID_CONVERSATION_SCENE_REPLY")
        correct = response["response_token"] == game["target_response"]
    error = {
        "conversation_pair_links": "question_response_function_mismatch",
        "conversation_turn_sequence": "dialogue_turn_order_confusion",
        "fictional_profile_reply": "profile_fact_selection_confusion",
        "conversation_scene_reply": "scene_referent_confusion",
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
        return ["කථිකයා, ප්‍රශ්නය සහ පිළිතුරු ආකාරය සසඳන්න; නිවැරදි පිළිතුර හෙළි නොවේ."]
    if scaffold_type == "worked_parallel_example":
        return ["වෙනත් සංවාදයක් බලමු.", "කථික වාර සසඳමු.", "නව ප්‍රතිචාරයක් සකසමු."]
    return ["ප්‍රශ්නය හඳුනාගන්න.", "කරුණ හෝ දර්ශනය බලන්න.", "ප්‍රතිචාරය සකසා නැවත පරීක්ෂා කරන්න."]


def package_hash() -> str:
    return hashlib.sha256(
        json.dumps(
            {"area": AREA_ID, "version": PACKAGE_VERSION, "source": SOURCE_PAIRS}, sort_keys=True
        ).encode()
    ).hexdigest()
