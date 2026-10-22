# Adaptive gamified learning

> Read this file first. It describes one component: the Grade 5 Sinhala-medium adaptive game
> loop. Code lives in `backend/app/gamification/`, `frontend/src/features/mobile-learning-flow/`
> (the app shell) and `frontend/src/features/areas/` (one folder per area game). §6 links the
> README of each.

## 1. Purpose

The component runs curriculum-aligned games so a child can show they can solve a fresh item
after support is gone. Finishing a game, earning coins, or answering while help is on screen
is participation. Mastery needs repeated, valid evidence on an unsupported item.

The research contribution is a misconception-conditioned Independence-Gain scaffold-selection
policy. It chooses among scaffold types by the later unsupported improvement it expects, then
updates from the improvement it observes. Games, retrieval, difficulty detection, and profiles
support that policy.

## 2. Scope

- Learners are Grade 5 and Sinhala-medium (`grade = 5`, `curriculum_medium = si`).
- Learner-facing copy, items, feedback, and scaffolds are Sinhala. The 57-area coverage target
  is Mathematics (16 areas), Sinhala (25) and Environment (16). The 18 English (`G5-AREA-ENG-*`) area
  games run on the same engine but are outside that target.
- The client is React packaged with Capacitor for Android and iOS. Phaser draws the interactive
  scene and talks only to React. React owns navigation, accessibility, Sinhala copy, and the
  server conversation. The layout fills the device.
- The server is FastAPI and PostgreSQL. It scores from an immutable rubric and assigns the
  measurement role when an item is presented.

Grade 4 content, Tamil-medium content, and a public website are outside this component.
Knowledge tracing, paper generation, learner-state fusion, and verified tutoring belong to the
other components. This component reads their published outputs and continues when an output is
missing. A language model does not choose the scaffold.

A skill is publishable when its Grade 5 source, page, outcome, medium, and reviewer are recorded.

## 3. One episode

1. Present items with no support. Role: `unsupported_before`.
2. Record the interaction. The server scores it.
3. Detect difficulty from stored signals and a versioned rule.
4. Estimate a misconception distribution, including `unknown_or_other`. The child does not see
   a technical diagnosis.
5. Choose the scaffold expected to improve the next unsupported attempt. Log every eligible
   action, exclusions, predicted gain, uncertainty, and whether the choice explored.
6. Show that scaffold during `supported_practice` and record what was shown.
7. Remove the scaffold and confirm `assistance_state = none`.
8. Present a fresh parallel item, role `unsupported_after`. It is unseen and unrevealed.
9. When the pair is valid and the episode is in proposed mode, compute raw Independence Gain
   and update later choices. Invalid, contaminated, and incomplete episodes are stored and do
   not train the policy.

The pilot API's domain model (`backend/app/gamification/domain/types.py`, `EpisodePhase`) names
every step:

```text
CREATED -> BASELINE_RESERVED -> BASELINE_ACTIVE -> BASELINE_SCORED
  -> GAMEPLAY_ACTIVE -> DIFFICULTY_DETECTED -> MISCONCEPTION_ESTIMATED
  -> SUPPORT_DECIDED -> SUPPORT_ACTIVE -> SUPPORTED_PRACTICE_COMPLETE
  -> SUPPORT_WITHDRAWN -> INDEPENDENT_CHECK_ACTIVE -> INDEPENDENT_CHECK_SCORED
  -> REWARD_VALIDATED -> POLICY_UPDATED -> COMPLETED
```

A baseline episode may go from `REWARD_VALIDATED` to `COMPLETED` without `POLICY_UPDATED`.
Any nonterminal state may move to `ABORTED` or `INVALIDATED` with a stable reason. Withdrawal,
independent scoring, and reward validation stay in the path.

The mobile area games (`application/engine/area_flow.py`) store a shorter status for the same
steps: `before_presented → support_active → support_complete → support_withdrawn →
after_presented → completed`, or `invalidated`. Each step also appends an event
(`unsupported_before_scored`, `support_withdrawn`, `unsupported_after_scored`,
`episode_completed`, …).

Roles, assigned at presentation: `practice`, `unsupported_before`, `supported_practice`,
`unsupported_after`, `retention`. Unsupported roles and retention require
`assistance_state = none`. Retention is reported separately from immediate Independence Gain.

```text
B = sum(unsupported_before scores) / sum(unsupported_before maximums)
A = sum(unsupported_after scores) / sum(unsupported_after maximums)
Independence Gain = A - B
```

The pair is valid when the items share an approved skill and a reviewed parallel family, the
after item is unseen and unrevealed, support was fully withdrawn, scoring versions match, and
the event order is complete.

## 4. Models

| Model | Question | Output |
| --- | --- | --- |
| Model 1 | Why is this learner likely struggling? | A distribution over the reviewed catalogue, including `unknown_or_other`, plus confidence and the evidence used |
| Model 2 | Which eligible help should be shown, and in which order? | The help order for the episode, why the first help leads (Model 1 reason, learning state, or a learned post-withdrawal preference), and the decision record. The pilot API's bandit also stores a predicted reward and uncertainty for every eligible scaffold |
| Model 3 | Did unsupported performance improve after support was removed? | Validity, the before and after proportions, raw Independence Gain, and whether the policy may update |

Model 3 is the measurement engine. Supported correctness is not its reward.

Help (scaffold) types are defined in `backend/app/gamification/content/support_types.py`:
visual guidance, step-by-step guidance that still requires the learner to act, conceptual
re-explanation, a simpler version of the same game, prerequisite repair, and a worked parallel
example that leaves the scored probe hidden. Each area may use only the types listed for it in
`data/gamification/grade5-area-support-catalog/`. One episode can show several help rounds in
order (the multi-help loop, `application/support_rounds.py`).

The same phone flow also runs a baseline: the subject's fixed help order, no use of the
misconception distribution or the learning state, and no policy update from Independence Gain.

Low Model 1 evidence moves the belief toward `unknown_or_other` and keeps confidence low.
Missing mastery, learner state, or a curriculum passage is stored as an absence.

How each model works, and which implementation each app path runs: [Models](models.md) and
[`backend/app/gamification/modeling/README.md`](../../backend/app/gamification/modeling/README.md).

## 5. Ownership

This component owns game items, scaffolds, rubrics, answer keys, episodes, telemetry, beliefs,
decisions, Independence Gain, rewards, consent, and the evidence outbox. Those game records are
not indexed as curriculum evidence.

It reads the learner id, Knowledge Tracing mastery, learner-state recommendation and support
need, and official curriculum passages through `app.curriculum`. Unapproved or rejected
passages are not shown.
Names and guardian details stay out of these records. The only foreign product key is
`learners.id`. Cross-component skill calls use the Universal Skill Node parent.

Domain and application code do not import another component. Architecture tests allow
`app.curriculum.application`, `app.knowledge_tracing.application.mastery`, and
`app.learner_state.application.support_need` only from `app/gamification/infrastructure/`.
Knowledge Tracing has not decided whether this evidence should update mastery, so this
component does not write Knowledge Tracing tables.

Coins, XP, badges, and streaks reward participation. Reports keep supported performance,
unsupported performance, and support dependence separate.

## 6. Code

Each code folder has its own README with a "where is…?" table:

- [`backend/app/gamification/README.md`](../../backend/app/gamification/README.md): API, the shared
  episode engine (`application/engine/area_flow.py`), one `application/<slug>_flow.py` profile per
  area, content, models, persistence.
- [`backend/app/gamification/modeling/README.md`](../../backend/app/gamification/modeling/README.md):
  Model 1, Model 2 and Model 3, and which implementation each app path runs.
- [`frontend/src/features/mobile-learning-flow/README.md`](../../frontend/src/features/mobile-learning-flow/README.md):
  the app shell, help UI and API client.
- [`frontend/src/features/areas/README.md`](../../frontend/src/features/areas/README.md): every area
  game, with its area id, backend flow, content module and data folder.
- [`data/gamification/README.md`](../../data/gamification/README.md): versioned content and
  synthetic development data.
- [`tools/README.md`](../../tools/README.md): every offline builder and analysis command.

Machine contracts in this folder are generated, never edited by hand:

- `mobile-learning-contracts-v1.json`: the mobile learning-flow API, built by
  `tools/gamification/learning_flow/build_mobile_learning_contracts.py`. The frontend types in
  `frontend/src/features/mobile-learning-flow/api/generated.ts` come from it
  (`npm run generate:mobile-learning-types`).
- `openapi-pilot-v1.json`: the pilot API. `frontend/src/features/gamification/api/generated.ts`
  comes from it (`npm run generate:api`).

Routes (all under `/api/v1`):

| Prefix | Router | Used for |
|---|---|---|
| `/development/learning-flow` | `api/learning_flow_router.py` | every area-game episode, learner-state camera consent, telemetry, reconstruction |
| `/learning-flow` | `api/learning_flow_router.py` | draft missions, area support types, fixture rounds |
| `/research-dashboard` | `api/research_dashboard_router.py` | the researcher-only dashboard |
| `/adaptive-episodes`, `/game-sessions`, `/admin`, … | `api/router.py` | the pilot API |

Every learning-flow request carries the development caller mark `X-Dev-Principal:
NOT_FOR_PRODUCTION` with `X-Dev-Role` `learner` or `researcher`. The draft mission list needs
the researcher role. How to run it locally: [Local development](local-development.md).
The production React entry mounts only `MobileLearningApp`; the old hash routes and inspector are not part
of the child bundle. `VITE_MOBILE_LEARNING_CONDITION` is an engineering-build input, not a child setting.
Native project generation is reproducible through `npm run native:generate` from locked inputs.

Telemetry: the pilot client's `TelemetryQueue` (`frontend/src/features/gamification/telemetry/queue.ts`)
keeps sequence-numbered events with stable event ids and client occurrence time, in memory, and
hands them over as one batch. It does not queue answers or episode transitions, does not retry,
and does not persist. The child app's client has a `telemetry` call for
`/development/learning-flow/episodes/{id}/telemetry`, but no area game sends telemetry yet.
Durable, offline-safe telemetry and native process-death recovery remain open work.

The answer-time learner-state, visual-feature, consent, and learner-evidence contract is
documented in [Learner-state integration at answer submission](learner-state-answer-integration.md).

## 7. Before a child uses it

Nothing in this component is approved for children. A named reviewer approves content, ethics
and release; passing tests do not approve those decisions.

- **Pilot slice.** The first complete loop to be reviewed is one Grade 5 Sinhala-medium skill, one
  reusable template, and the three original scaffold types, in baseline and proposed modes, on
  the phone. Its content is still researcher-authored draft awaiting educator review.
  The skill area is Grade 5 Mathematics fractions (`MAT-FRC`,
  `data/gamification/grade5-pilot-slice/v1/`). `load_pilot_content_package` refuses it unless
  `allow_draft=True`. The pilot play path returns `CURRICULUM_RETRIEVAL_UNAVAILABLE` until the
  shared retriever supplies a passage.
- **Area games.** 37 development-only area games (16 Mathematics, 18 English, 3 Sinhala) run the
  full unsupported-before → Model 1 → Model 2 → help rounds → acknowledged withdrawal → fresh
  unsupported-after → raw Independence Gain sequence. The index is
  [`frontend/src/features/areas/README.md`](../../frontend/src/features/areas/README.md). Content,
  misconception catalogues, scaffold mappings and curriculum mappings all wait for human review;
  where an area has a package README in `data/gamification/grade5-<slug>/`, it records exactly
  what remains blocked.
- **Draft missions.** The draft mission catalogue covers 54 mapped areas (16 Mathematics, 22
  buildable Sinhala, 16 Environment; `data/gamification/grade5-draft-mission-catalog/v1/`). It is
  served only to the development researcher role. Environment areas play as fixture rounds;
  other areas without a game open the draft template player.
