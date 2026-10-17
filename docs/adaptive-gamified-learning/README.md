# Adaptive gamified learning

> Read this file first. It describes one component: the Grade 5 Sinhala-medium adaptive game
> loop. Code lives in `backend/app/gamification/` and `frontend/src/features/phase7/`.

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
- Learner-facing copy, items, feedback, and scaffolds are Sinhala. English appears only as
  subject content inside an approved item.
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
| Model 2 | Which eligible scaffold should be shown? | The selected scaffold, a predicted reward and uncertainty for every eligible scaffold, and the decision record |
| Model 3 | Did unsupported performance improve after support was removed? | Validity, the before and after proportions, raw Independence Gain, and whether the policy may update |

Model 3 is the measurement engine. Supported correctness is not its reward.

Scaffold types are visual guidance, a worked example that leaves the scored probe hidden, and
step-by-step guidance that still requires the learner to act.

The same phone flow also runs a baseline: a predefined scaffold, no use of the misconception
distribution, and no policy update from Independence Gain.

Low Model 1 evidence moves the belief toward `unknown_or_other` and keeps confidence low.
Missing mastery, learner state, or a curriculum passage is stored as an absence.

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

```text
backend/app/gamification/
  api/            HTTP, including the development episode routes
  application/    episode flow, delivery, orchestration
  domain/         episode states
  modeling/       Model 1, Model 2, and Independence Gain
  content/        draft content registry
  infrastructure/ persistence and the curriculum, mastery, and learner-state adapters
frontend/src/features/phase7/   React client, Phaser half-set scene, event queue
data/gamification/               draft content and synthetic development data
```

Machine contracts in this folder are `phase6-mobile-contracts-v1.json` and
`openapi-pilot-v1.json`. Development routes are `/api/v1/development/phase6`. The client flag
`VITE_ENABLE_PHASE7_DRAFT` and the header `X-Dev-Principal` are for local composition only.

The answer-time learner-state, visual-feature, consent, and learner-evidence contract is
documented in [Learner-state integration at answer submission](learner-state-answer-integration.md).

## 7. Before a child uses it

The first complete loop is one reviewed Grade 5 Sinhala skill, one reusable template, and the
three scaffold types, in baseline and proposed modes, on the phone. The first skill area is
Grade 5 Mathematics fractions (`MAT-FRC`). A larger skill inventory is not that loop.

A named reviewer approves content, ethics, and release. Passing tests do not approve those
decisions. Draft content loads only when development mode explicitly allows it. The play path
returns `CURRICULUM_RETRIEVAL_UNAVAILABLE` until the shared retriever supplies a passage.
