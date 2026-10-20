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
* `item_skills`: her item skill id -> ours (87 items today, covering 11 of our skills).

The file is **generated**, not typed: `python -m scripts.build_game_skill_map` reads her flows and her own
`areas.json` (which names the parent skill of every area). The reader only reads the file and never
imports the game. A test fails if the file is out of date, so when she adds a game or a skill, run the
command once and commit the file. Her data is the only source; if `areas.json` names a different parent,
the file follows it.

The reader still checks every record: the skill on it, after translation, must agree with the one the map
gives for its item skill. A skill in neither table is skipped, so a wrong or new label cannot slip in.

## What the game still has to do

Checked on 2026-10-20 by running the game's real division flow through its own publisher and then
through our reader (17 playable areas publish through the same code).

1. **`model_ingestion_eligible` is still always `false`**, in every publisher, and
   `playable_area_package.py` types it as `Literal[False]`. Tell us who decides, and how it is switched
   on (real children, parent consent, approval). Until then nothing real is read.
2. **`difficulty` is missing.** The adventure flows send no `difficulty` (it is `null`), so every record
   is skipped as `unknown_difficulty`. Send `easy`, `medium` or `hard`, converted from the item's own
   level (the older flow's `_difficulty_band` does this).
3. **The Sinhala language areas and one environment area have no parent skill** (26 of 57 areas are
   `no_universal_parent` in `areas.json`), and the five aptitude skills (APT-LOG, APT-REL, APT-SPA,
   APT-VIS, APT-WRD) have no game. Decide whether they get skills of ours or stay outside the model.
4. **Optional, later:** the old durable fractions flow (`_publish_score`) writes `MAT-FRC` on every
   record; give it the area's skill. Not needed for the adventure flows.

Done on her side: real `response_time_ms`, and 17 playable areas (16 mathematics, 1 English) with generated
items instead of 3 questions for one skill.

Result today: `python -m scripts.ingest_game_evidence` still skips every record, for items 1 and 2.
With both set, her division answers are saved under `MAT-OPS` with their real times (tried on her real flow).

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
