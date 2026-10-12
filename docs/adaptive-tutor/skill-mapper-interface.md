# Conversational Skill Mapper interface

## Status and scope

Task 9 defines contracts and behavior specifications for a future Conversational Skill Mapper. It
does not implement semantic mapping, confidence estimation, translation, retrieval, or any model
call. The mapper's sole future responsibility is:

```text
free-form learner message + recent context -> skill mapping result
```

It must not calculate mastery, select an assistance level, generate tutoring content, or modify
Scaffolding Controller V1.

## Conceptual flow

```text
Learner Message
      |
      v
Intent Understanding
      |
      v
Skill Mapping
      |
      v
skill_id + confidence/status
      |
      v
Future Mastery Retrieval
      |
      v
Existing Controller V1
```

Only the request/result interface and its validation exist now. Every processing step in the flow
is future work.

## Request contract

`SkillMappingRequest` is immutable and rejects unknown fields.

| Field | Type | Rule | Meaning |
| --- | --- | --- | --- |
| `learner_message` | string | Required and non-blank | Current learner utterance in any supported language or mixture. |
| `conversation_context` | ordered turns | Optional; at most 8 | Recent learner/tutor messages, oldest to newest. |
| `active_skill_id` | string or null | Optional; taxonomy membership checked externally | Previously active skill context, never a forced answer. |
| `preferred_language` | string or null | Optional and non-blank | Presentation/interpretation hint, not a language restriction. |

Each `ConversationTurn` contains a `LEARNER` or `TUTOR` role and non-blank message text. The eight-
turn limit is an interface capacity bound, not a research finding.

## Result contract

`SkillMappingResult` is immutable and rejects unknown fields.

| Field | Type | Rule |
| --- | --- | --- |
| `status` | mapping status | Required |
| `intent` | learning intent | Required; does not imply correctness |
| `skill_id` | string or null | Required for `MATCHED`; forbidden otherwise |
| `confidence` | float or null | Inclusive `0.0–1.0`; required for `MATCHED`; forbidden otherwise |
| `candidate_skills` | ordered candidates | Optional; at most 5; unique skill IDs |
| `clarification_needed` | boolean | True only for `AMBIGUOUS` |
| `clarification_question` | string or null | Required exactly when clarification is needed |
| `reason_codes` | reason-code list | Optional; unique stable codes |

Each candidate contains a structurally valid `skill_id` and normalized confidence. Tuple order is
the proposed rank. Candidate confidence expresses mapper uncertainty; it is not learner mastery.
The five-candidate limit is an interface capacity bound.

## Mapping statuses

- `MATCHED`: one supported skill is confirmed for downstream use; `skill_id` and confidence are
  present.
- `AMBIGUOUS`: evidence does not justify one skill; no confirmed `skill_id` is present, candidates
  may be supplied, and a clarification question is required.
- `NO_MATCH`: the message is learning-related but no supported taxonomy skill is justified. It has
  no confirmed skill or candidates.
- `NOT_SKILL_RELATED`: a greeting or off-topic message should not enter mastery retrieval. It has
  no confirmed skill or candidates.

An uncertain candidate must not be encoded as `MATCHED`. Low-confidence handling and any future
cutoff values are provisional implementation design parameters, not scientifically validated
thresholds. Only a policy-approved `MATCHED` result may proceed to future mastery retrieval.

## Learning intents

- `EXPLANATION_REQUEST`
- `HINT_REQUEST`
- `FOLLOW_UP_QUESTION`
- `ANSWER_SUBMISSION`
- `ANOTHER_EXAMPLE_REQUEST`
- `GREETING`
- `OFF_TOPIC`

Intent and correctness are separate. In particular, `ANSWER_SUBMISSION` identifies the learner's
communicative act; it does not say whether the answer is correct or create a tutoring attempt.

## Reason codes

Stable reason codes describe why a future implementation produced its result:

- `DIRECT_SKILL_EVIDENCE`
- `CONVERSATION_CONTEXT_USED`
- `ACTIVE_SKILL_USED`
- `MULTIPLE_CANDIDATES`
- `INSUFFICIENT_EVIDENCE`
- `OUTSIDE_SUPPORTED_TAXONOMY`
- `NOT_SKILL_RELATED`
- `LOW_CONFIDENCE`

They are audit labels, not generated explanations or proof of mapping accuracy.

## Conversation context behavior

Recent turns and `active_skill_id` are evidence, not routing commands. A dependent message such as
“Why did you multiply that?” may resolve to active `MAT-FRC` when the immediately preceding turns
are about fraction operations. The result should record that context was used.

A self-contained new question overrides stale context when its evidence supports another skill. For
example, “How many days are in a leap year?” may move from active `MAT-FRC` to `MAT-TIM`. If context
does not distinguish plausible skills, the mapper returns `AMBIGUOUS` and asks a concise question;
it must not blindly reuse the active skill.

## Multilingual requirements

The contracts preserve Unicode text without imposing a language-specific representation. A future
mapper must handle English, Sinhala, Tamil, Singlish, Tanglish, code-mixed messages, spelling
mistakes, and informal child language. `preferred_language` may help interpretation or later
presentation but must not exclude other languages in the same message.

Language-specific keyword tables must not be the core mapping method. This task introduces no
translation service, embeddings, semantic search, or model API.

## Taxonomy integration

`docs/skill_nodes.xlsx` is the current authoritative Universal Skill Nodes taxonomy and contains 30
skill IDs across APT, MAT, LAN, and ENV. The Pydantic models validate only that an ID is non-blank;
they deliberately do not duplicate those 30 values in source code.

`validate_skill_ids_against_taxonomy` accepts a caller-supplied set from an authoritative taxonomy
adapter and validates `active_skill_id`, confirmed `skill_id`, and candidate IDs. The future runtime
composition layer must load or receive that authoritative set before accepting a mapping result.
The spreadsheet itself is not loaded by the contracts.

## Structural examples

These confidence values illustrate JSON shape only; they are not measured performance.

Clear supported question:

```json
{
  "request": {"learner_message": "How do I add these fractions?"},
  "result": {
    "status": "MATCHED",
    "intent": "EXPLANATION_REQUEST",
    "skill_id": "MAT-FRC",
    "confidence": 0.8,
    "candidate_skills": [],
    "clarification_needed": false,
    "clarification_question": null,
    "reason_codes": ["DIRECT_SKILL_EVIDENCE"]
  }
}
```

Ambiguous request:

```json
{
  "request": {"learner_message": "Can you explain this?"},
  "result": {
    "status": "AMBIGUOUS",
    "intent": "EXPLANATION_REQUEST",
    "skill_id": null,
    "confidence": null,
    "candidate_skills": [
      {"skill_id": "MAT-FRC", "confidence": 0.55},
      {"skill_id": "MAT-OPS", "confidence": 0.45}
    ],
    "clarification_needed": true,
    "clarification_question": "Is your question about fractions or basic operations?",
    "reason_codes": ["MULTIPLE_CANDIDATES", "LOW_CONFIDENCE"]
  }
}
```

Unsupported topic and greeting use `NO_MATCH` and `NOT_SKILL_RELATED` respectively, with null
confirmed skill/confidence, no candidates, and no clarification question.

## Future prototype evaluation cases

These are semantic expectations for Task 10; they are documentation, not executable claims that a
mapper already works. A matched case requires an implementation-produced confidence, but no value
below is a claimed score.

| Case | Learner message/context | Expected intent | Expected outcome |
| --- | --- | --- | --- |
| English | “How do I add these fractions?” | `EXPLANATION_REQUEST` | `MATCHED`, `MAT-FRC` |
| Sinhala | “භාග දෙකක් එකතු කරන්නේ කොහොමද?” | `EXPLANATION_REQUEST` | `MATCHED`, `MAT-FRC` |
| Tamil | “இரண்டு எண்களை எப்படி வகுப்பது?” | `EXPLANATION_REQUEST` | `MATCHED`, `MAT-OPS` |
| Singlish | “bage dekak ekathu karanne kohomada?” | `EXPLANATION_REQUEST` | `MATCHED`, `MAT-FRC` |
| Tanglish | “intha kanakkula epdi divide panrathu?” | `EXPLANATION_REQUEST` | `MATCHED`, `MAT-OPS` |
| Code-mixed | “මේ fraction eka explain pannunga” | `EXPLANATION_REQUEST` | `MATCHED`, `MAT-FRC` |
| Misspelling | “How do I devide 48 by 6?” | `EXPLANATION_REQUEST` | `MATCHED`, `MAT-OPS` |
| Hint | “Give me one hint for this fraction.” | `HINT_REQUEST` | `MATCHED`, `MAT-FRC` |
| Answer | “I got 8.” with active `MAT-OPS` division context | `ANSWER_SUBMISSION` | Context-supported `MATCHED`, `MAT-OPS` |
| Another example | “Can I see another one?” with active `MAT-FRC` context | `ANOTHER_EXAMPLE_REQUEST` | Context-supported `MATCHED`, `MAT-FRC` |
| Follow-up | “Why did you multiply that?” with fraction context | `FOLLOW_UP_QUESTION` | Context-supported `MATCHED`, `MAT-FRC` |
| Context change | Active `MAT-FRC`; “How many days are in a leap year?” | `EXPLANATION_REQUEST` | `MATCHED`, `MAT-TIM` |
| Ambiguous | “Can you explain this?” without useful context | `EXPLANATION_REQUEST` | `AMBIGUOUS`, clarification required |
| Multiple candidates | “How do I work with these numbers?” | `EXPLANATION_REQUEST` | `AMBIGUOUS`, ranked candidates, clarification required |
| Unsupported | “Teach me algebraic equations.” | `EXPLANATION_REQUEST` | `NO_MATCH`, no fabricated skill |
| Greeting | “Ayubowan teacher!” | `GREETING` | `NOT_SKILL_RELATED` |
| Off-topic | “Who won the cricket match?” | `OFF_TOPIC` | `NOT_SKILL_RELATED` |
| Low confidence | Weak evidence for several taxonomy skills | Applicable intent | `AMBIGUOUS`, never automatic mastery retrieval |

Contract tests separately cover missing/blank messages, out-of-range confidence, duplicate or
oversized candidate lists, unknown taxonomy IDs, and contradictory result states.

## Assumptions and limitations

- No Skill Mapper implementation exists in Task 9, so semantic accuracy is not tested.
- Confidence is an interface value whose production and calibration remain undefined.
- The contracts do not infer language, translate text, classify correctness, or update state.
- Conversation context is caller-supplied and bounded; no session storage is introduced.
- Taxonomy loading and versioning belong to a future authoritative adapter.
- Privacy, latency, model choice, evaluation data, and child-safety evaluation remain future design
  work for the prototype and its deployment review.

## Future Task 10 prototype boundary

A future prototype may implement intent understanding and skill ranking behind these contracts,
consume an authoritative taxonomy snapshot, validate every referenced ID, and return one of the
defined statuses. It must preserve uncertainty, treat active context as defeasible evidence, and
gate mastery retrieval on an accepted `MATCHED` result.

Task 10 must not alter Controller V1 or collapse intent recognition, mastery retrieval, assistance
selection, and response generation into the mapper.
