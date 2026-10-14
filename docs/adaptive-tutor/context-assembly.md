# Tutor Context Assembly and Readiness Contracts

## Status and scope

Task 15A defines the application boundary that can assemble trusted evidence into the existing
Controller V1 `TutoringContext`. It does not call the controller, retrieve curriculum, generate or
verify a response, expose an API, or persist new data. Those remain later integration tasks.

The assembler fails closed: it returns `NOT_READY` when a required input is missing, invalid, or
unavailable. It never invents, clamps, or translates evidence into a value that an owning component
did not provide.

## Architecture

```text
confirmed SkillMappingResult + shared learner UUID
                         |
                         v
              TutorContextAssembler
               /    |     |     \
      learner / mastery support assessment history
             /     |       |       |       \
 Shared Learner    KT  Learner State  Game/Assessment  Adaptive Tutor
                         |
                         v
           READY + existing TutoringContext
                         or
           NOT_READY + typed issues/provenance
```

There are no HTTP calls between modules. Each owner is accessed through an application-level
provider protocol. The canonical KT `MasteryProvider`, `MasteryRetrievalRequest`, `MasteryResult`,
and `MasteryStatus` are reused rather than duplicated.

## Canonical Controller V1 inputs

| Field | Required semantics |
|---|---|
| `learner_id` | Existing shared learner UUID |
| `skill_id` | Confirmed ID in the caller-supplied authoritative taxonomy |
| `mastery` | Strict finite number in `[0, 1]` |
| `support_need` | Strict finite number in `[0, 1]`; not a categorical action |
| `attempt_count` | Strict non-negative integer |
| `is_correct` | Null at zero attempts; required after a completed attempt |
| `error_severity` | Null at zero attempts; normalized and required after a completed attempt |
| `previous_assistance_level` | Optional canonical L0-L6 value |
| `previous_hint_effective` | Optional boolean; requires a previous assistance level |

Unknown hint effectiveness is intentionally valid when a previous assistance level exists. This is
an existing Controller V1 state used to preserve assistance history. No previous Tutor interaction is
also valid and is represented as `NOT_YET_OBSERVED` history with both history values absent.

## Ownership and current readiness

| Evidence | Owner | Current repository interface | Task 15A interface | Current state |
|---|---|---|---|---|
| Learner UUID and grade | Shared Learner | `LearnerService` / `LearnerRepository` | `LearnerProvider` | Real storage exists; status adapter still needed |
| Confirmed skill ID | Adaptive Tutor Skill Mapper | `SkillMappingResult` and taxonomy validator | Reused directly | Implemented, not orchestrated |
| Per-skill mastery | Knowledge Tracing | Canonical `MasteryProvider` contract | `ContextMasteryProvider` adds only provenance metadata | Contract only; real provider missing |
| Numeric support need | Learner State | Categorical support actions | `SupportNeedProvider` | Numeric mapping/provider missing and must be reviewed |
| Attempt/correctness/error evidence | Game or agreed Assessment owner | KT attempt database model only; no stable read service | `AssessmentEvidenceProvider` | Owner/service unresolved |
| Previous assistance and hint effectiveness | Adaptive Tutor | No persistence/read interface | `AssistanceHistoryProvider` | Provider and persistence missing |

Task 15A does not read another component's private tables. It does not create a combined learner
profile record or transfer write ownership into Adaptive Tutor.

## Provider and evidence states

Non-KT provider contracts use only the states needed at this boundary:

- `AVAILABLE`: valid evidence is present.
- `NOT_FOUND`: the requested record is absent.
- `NOT_YET_OBSERVED`: the owner confirms that evidence has not yet been observed.
- `PROVIDER_UNAVAILABLE`: the provider cannot currently serve the request.
- `PROVIDER_ERROR`: the provider reports a safe operational failure.
- `INVALID_EVIDENCE`: the provider knows the evidence cannot be trusted.

KT retains its existing statuses: `AVAILABLE`, `NOT_FOUND`, `PROVIDER_UNAVAILABLE`, and
`PROVIDER_ERROR`.

Every provider exposes an `EvidenceSource` with a non-blank source ID and an origin of `REAL` or
`SYNTHETIC`. `ContextAssemblyResult` records status and provenance for each consulted input and
reports an aggregate origin of `REAL`, `SYNTHETIC`, or `MIXED`. Provider exception details are not
included in user-safe diagnostics.

## Readiness behavior

`READY` requires a constructed canonical `TutoringContext`, its trusted Grade 4 or 5 learner grade,
and no issues. The grade is returned separately because it is required by later curriculum and
generation contracts but is not a Controller V1 input. `NOT_READY` requires no context or grade and
one or more typed `ContextIssue` values. Issues distinguish missing inputs, invalid evidence,
provider failures, and unsupported inputs.

The assembler validates:

- a `MATCHED` skill result and authoritative taxonomy membership;
- learner/result identity and the Grade 4-5 scope;
- KT result identity and normalized mastery;
- reviewed numeric normalized support need;
- attempt, correctness, and severity relationships;
- assistance-level and hint-effectiveness relationships; and
- the final combined data against the existing `TutoringContext` model.

Legitimate `0.0` scores and an explicitly observed zero-attempt state remain zero. Missing values are
not converted to zero. A categorical Learner State action such as `request_tutor_support` is rejected
as invalid numeric support evidence.

## Cold start

A learner with no mastery record, no validated numeric support need, no assessment attempts, and no
Tutor history is `NOT_READY`. The assessment provider may explicitly represent no attempts as
`NOT_YET_OBSERVED` with `attempt_count=0`, and Tutor history may be `NOT_YET_OBSERVED`; neither is
fabricated. Mastery and support need remain blocking because Controller V1 requires normalized
values.

A real cold-start policy needs reviewed agreements from Knowledge Tracing and Learner State. Task
15A deliberately does not invent that pedagogical policy.

## Synthetic PP1 fixtures

`SyntheticTutorContextFixture` loads fixed, design-authored inputs from the existing 20 Reference
Policy V1 scenarios. Selection requires `allow_synthetic=True`, and all source IDs begin with
`synthetic:`. The fixture never reads or writes learner records and makes no claim of real KT or
Learner State inference.

The fixture's mapping confidence is structural design data used to satisfy the existing matched-result
contract; it is not measured model accuracy or a calibrated probability.

The complete fixtures include valid examples across L0-L6. They provide evidence only; Controller V1
still independently determines the level. `COLD_START` and `PROVIDER_FAILURE` modes exercise missing
data and explicit failures. A failed real provider never activates these fixtures automatically.

### READY synthetic example

```python
fixture = SyntheticTutorContextFixture.select(
    "AT-V1-001",
    allow_synthetic=True,
)
result = assembler_for(fixture).assemble(fixture.assembly_request())

assert result.status == "READY"
assert result.evidence_origin == "SYNTHETIC"
assert result.context.skill_id == "MAT-FRC"  # design-authored synthetic data
```

### NOT_READY missing-mastery example

```python
fixture = SyntheticTutorContextFixture.select(
    "AT-V1-001",
    allow_synthetic=True,
    mode=SyntheticFixtureMode.COLD_START,
)
result = assembler_for(fixture).assemble(fixture.assembly_request())

assert result.status == "NOT_READY"
assert result.context is None
# Reasons include MASTERY_NOT_FOUND and SUPPORT_NEED_NOT_YET_OBSERVED.
```

`assembler_for` in these snippets means an explicitly constructed `TutorContextAssembler` with the
fixture passed to each provider slot; there is no production default or global synthetic switch.

## Task 15B handoff

Task 15B's `TutorOrchestrator` consumes `ContextAssemblyResult` as follows:

1. Stop and return a safe non-tutoring state for `NOT_READY`.
2. Pass `result.context` to Controller V1 only for `READY`.
3. Preserve provenance in operational diagnostics without exposing sensitive provider details.
4. Keep synthetic assembly behind an explicit non-production composition root.

Before real-learner orchestration is ready, teammates must provide:

- a Shared Learner adapter returning `LearnerLookupResult`;
- a real KT implementation of the canonical mastery provider with provenance;
- a reviewed numeric Learner State support-need contract/adapter;
- an agreed Assessment/Game evidence owner and read service; and
- Adaptive Tutor assistance-history persistence and a provider.

Task 15B must not treat `NOT_READY` as permission to substitute defaults, call the LLM, or silently use
synthetic evidence.
