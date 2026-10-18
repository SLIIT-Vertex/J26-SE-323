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

## What the game still has to do

1. **Fix `universal_skill_id` in the durable flow.** `_publish_score` writes `"MAT-FRC"` on every
   record. It should use the skill of the question that was played. Until then, every record for a
   skill other than fractions is refused.
2. **Decide when `model_ingestion_eligible` becomes `true`.** It is always `false` today, and the
   flow only runs in `development` or `test`. Tell us who decides, and how it is switched on
   (real children, parent consent, approval). Until it is, nothing real is read.
3. **Send the real difficulty.** `difficulty` is a fixed `"easy"` today. Send `easy`, `medium` or
   `hard`, converted from the question's own level.
4. **Send `response_time_ms`.** The mobile app sends no response time, so it is always empty.
5. **More questions, with variety.** The flow that writes the records has 3 questions in total (one
   before help, one practice, one after help), all for one fractions skill, so every episode scores
   the same two. It needs a bank of questions per skill and a way to pick different ones, for as many
   of our 30 skills as possible. The questions are still `draft`.
6. **Review the skill crosswalk.** All 548 rows are `draft`, none reviewed. It reaches 25 of our 30
   skills; the five aptitude skills (APT-LOG, APT-REL, APT-SPA, APT-VIS, APT-WRD) have no game skill.
   Confirm that is intended.

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
