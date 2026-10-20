# Connection between the game and the knowledge model

The knowledge model learns from every answer a child gives, in the game and on paper. This note says
what the knowledge-tracing side does now, and what it still needs from the game.

## What the knowledge-tracing side does now

**1. It can save a game answer that has no bank question.** The game has its own questions, so
`POST /api/v1/attempts` accepts either form:

```json
{ "learner_id": "…", "skill_code": "MAT-FRC", "difficulty": "easy", "language": "si",
  "correct": true, "time_ms": 8000, "hints": 0, "answered_at": "2026-10-18T09:00:00+05:30" }
```

or the earlier form with `"question_id": "3.41"` instead of `skill_code` and `difficulty`. One form
only. `skill_code` is one of the 30 skills, `difficulty` is `easy`, `medium` or `hard`. A repeated
`Idempotency-Key` returns the same answer.

**2. It can read the game's outbox.** `python -m scripts.ingest_game_evidence` reads the table
`learner_evidence_outbox` (event `gamification_item_scored`) and saves each usable record as a game
answer under the key `game:<attempt_id>`. It never changes the game's table, and reading twice does
not count an answer twice. Use `--dry-run` to see what it would do.

A record is used only if:

| Rule | Why |
|---|---|
| `model_ingestion_eligible` is `true` | The game says the record may reach a model. |
| `universal_skill_id` is one of our 30 skills **and** matches the crosswalk for the record's `skill_id` | A wrong skill label would teach the model the wrong thing. |
| `difficulty` is `easy`, `medium` or `hard` | The model needs a level. |
| `correct` is a plain `true` or `false`, and `attempt_id` is present | Right or wrong, and no double counting. |
| The learner exists and has a language (`si` or `ta`) | The language comes from the record, else from the learner. |

Everything else is skipped and counted with its reason. `supported: true` counts as one hint.
`response_time_ms` may be empty; times over 10 minutes are cut to 10 minutes.

**3. One shared learner, until there is a login.** The game and the practice screens (papers,
results, progress) both use the development learner `00000000-0000-4000-8000-000000000721`, so a
child's game answers and paper answers belong to the same learner. Both frontends read it from the
same setting, `VITE_MOBILE_LEARNING_LEARNER_ID`, with the same default, and a test fails if the two
defaults ever differ. The learner must exist in the database: `python -m scripts.seed_dev_learner`
creates it (once; running it again changes nothing). When there is a login, both should take the
signed-in child's id instead.

## Her skills are parts of our 30 (nothing of hers is changed)

The game keeps finer skills, for example `MAT-DIV` or the item skill `G5-MAT-DIV-WRITTEN-01`. They are
parts of our 30 (`MAT-DIV` is a part of `MAT-OPS`), and she keeps all of them as they are.
`shared/game_skill_map.json` says which of our skills each one belongs to:

* `sub_skills`: her skill label -> ours (`MAT-DIV` -> `MAT-OPS`, `MAT-TIME` -> `MAT-TIM`, ...). A label that
  is already one of our 30 passes through unchanged.
* `item_skills`: her item skill id -> ours (126 items today, covering 11 of our skills; the English games all map to `LAN-BIL`).

The file is **generated**, not typed: `python -m scripts.build_game_skill_map` reads her flows and her own
`areas.json` (which names the parent skill of every area). The reader only reads the file and never
imports the game. A test fails if the file is out of date, so when she adds a game or a skill, run the
command once and commit the file. Her data is the only source; if `areas.json` names a different parent,
the file follows it.

The reader still checks every record: the skill on it, after translation, must agree with the one the map
gives for its item skill. A skill in neither table is skipped, so a wrong or new label cannot slip in.

## How a game answer is released to the model (done)

The game's adventure flows now set `model_ingestion_eligible` with a rule, in
`NumberWorldFlow._model_eligible` (`number_world_flow.py`):

> an answer is released only when the episode ran in the **`pilot`** environment **and** the learner has a
> **research consent** on record that is granted and not expired.

* `development` and `test` answers are never released. They are read only with the trial switch below.
* **Camera consent is not research consent.** They are different purposes in the consent store.
* A pilot episode still needs the explicit `allow_draft` opt-in, because the questions are still drafts.
  Any other environment (for example `production`) is still refused.
* The database allows the `pilot` value through migration `gam_20261021_01`, and the stored API
  description (`mobile-learning-contracts-v1.json`) lists it.
* Record a consent once the guardian's written consent is held:
  `python -m scripts.record_research_consent --learner-id <uuid>` (add `--withdraw` to stop it). A newer
  decision replaces the older one; answers already read are not changed.

Every adventure answer also carries a `difficulty` (easy, medium or hard), a `difficulty_source` and the
mapping version `gamification-skill-level-v1`. The game's skills keep their own finer level; `evidence_difficulty`
reads it as: easy -> easy, medium -> medium, hard -> hard, and the in-between or wide levels (`easy_medium`,
`medium_hard`, `easy-to-hard`) -> medium. A skill with no level of its own gets `medium`, marked `default_unlabelled`, so
the research can leave those answers out later. Today that is addition, subtraction, fractions, number
world, number patterns and time.

The whole chain is one test, `tests/knowledge_tracing/test_game_pilot_end_to_end.py`: the real division
flow, the game's real outbox publisher, and our reader in its strict default mode, which saves the answers
under `MAT-OPS` with their real times.

## What is still open

1. **Approved content.** The questions are still unreviewed drafts. The release rule above does not check
   a review status; the team should decide who approves the items a pilot uses, and add that check if it
   wants it enforced in code.
2. **Levels for six games.** Give the skills of addition, subtraction, fractions, number world, number
   patterns and time a `difficulty` of their own, so they stop falling back to `medium`.
3. **The Sinhala language areas and one environment area have no parent skill** (26 of 57 areas are
   `no_universal_parent` in `areas.json`), and the five aptitude skills (APT-LOG, APT-REL, APT-SPA,
   APT-VIS, APT-WRD) have no game. Decide whether they get skills of ours or stay outside the model.
4. **Optional, later:** the old durable fractions flow (`_publish_score`) and the fixture rounds still
   write `model_ingestion_eligible: false`; they do not release answers.

Not needed from the game: a `language` field (the learner's language is used) and any "published"
marking of outbox rows (the reader does not need it).

Keep the table name `learner_evidence_outbox` and the columns `id`, `idempotency_key`, `event_type`,
`learner_id`, `skill_code`, `universal_skill_id`, `payload_json`, `contract_version`, `created_at`.
A test on our side writes records with the game's own publisher, so a change on either side shows up
as a failing test.

## Trying it on a local database

1. Run the game's migrations as well as ours, so `learner_evidence_outbox` exists.
2. `python -m scripts.seed_dev_learner` creates the shared learner (the game's records and its
   foreign keys need it).
3. Play a game round, so the game writes records.
4. `python -m scripts.ingest_game_evidence --dry-run` shows that every record is held back
   (`not_eligible`).
5. `python -m scripts.ingest_game_evidence --include-development` saves them anyway, for a local
   trial only. Then open the Progress screen: the fractions skill shows a number after 3 answers.

## Left until the game is complete

- Running the reader on a schedule, or having the game call `POST /attempts` itself (either works).
- Using records from real children, which depends on points 1 and 2 above.
- Skills other than fractions, which depends on points 4 and 5.
