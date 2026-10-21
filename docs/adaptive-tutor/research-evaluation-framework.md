# Adaptive Tutor Research Evaluation Framework V1

## Scope and evidence boundary

Task 16A defines a reproducible offline evaluation foundation for the Verified
Minimum-Sufficient Adaptive Scaffolding Framework. It measures software-policy conformance where
the repository has suitable data. It does not establish expert pedagogical validity, learner
benefit, comprehensive safety, or production readiness.

No separate approved research proposal or methodology document was found in the repository. The
research questions below therefore operationalize the requested Task 16A scope and must remain
provisional until checked against the approved proposal.

Current assets must not be pooled as though they have equal evidential status:

| Asset | Output/data origin | Label provenance | Permitted claim |
|---|---|---|---|
| Reference Policy V1, 20 scenarios | Design-authored synthetic | Provisional, unreviewed policy expectations | Controller conformance only |
| Skill Mapper development/evaluation/held-out sets | Design-authored synthetic | Unreviewed; held-out set already inspected | Preliminary retrieval behavior only |
| Pinned-E5 Skill Mapper runs | Real model outputs | Compared with design-authored labels | Preliminary model behavior, not validated accuracy |
| Verifier tests | Design-authored synthetic | Implementation-test expectations | Deterministic rule behavior only |
| Fake semantic verifier | Mock-generated judgments | Configured by tests | No semantic-verifier performance claim |
| Generation/orchestration tests | Mock-generated text and synthetic evidence | Implementation-test expectations | Wiring and fail-closed behavior only |
| Learner observations/outcomes | Unavailable | Unavailable | No learner-effectiveness claim |

## Evaluation architecture

```text
Frozen experiment manifest
        +
Canonical Reference Policy V1 (referenced, not copied)
        |
        v
ScaffoldingController.decide
        |
        v
Typed evaluation records
        |
        +--> ordinal metrics and L0-L6 confusion matrix
        +--> escalation/fading transition metrics
        +--> machine-readable JSON report
        +--> human-readable Markdown summary
```

`backend/app/adaptive_tutor/evaluation.py` contains deterministic metrics and the Controller V1
runner. `backend/scripts/evaluate_adaptive_tutor.py` is a thin exporter. Neither imports the API,
database, Gemini adapter, embedding model, or learner services. The runner receives a frozen date,
dataset version, implementation version, configuration, and provenance from
`research/adaptive-tutor/evaluation-manifest-v1.json`; it does not obtain these values from mutable
runtime state.

## Provisional research questions

- **RQ1 — Reference-policy conformance:** How consistently does Controller V1 select assistance
  levels relative to the design-authored Reference Policy V1 labels?
- **RQ2 — Evidence-condition behavior:** How do mastery, support need, error severity, attempt count,
  prior assistance, and prior hint effectiveness affect the selected level and escalation/fading
  direction within the specified policy?
- **RQ3 — Violation detection:** On a future independently labelled response set, how effectively do
  deterministic verifier rules identify assistance-level violations and answer leakage?
- **RQ4 — Fail-closed behavior:** On a frozen missing/unavailable-input dataset, how often does the
  workflow refuse delivery when required evidence is absent or a dependency fails?
- **RQ5 — Comparative performance:** Under controlled model, prompt, data, and rubric conditions,
  how should the proposed framework later compare with conventional and learner-state-aware LLM
  tutoring baselines?

RQ1 and the transition subset of RQ2 can currently be measured as policy conformance. RQ3–RQ5 need
new evidence. None of these questions equates software-policy agreement with effective teaching.

## Metric definitions

Every reported rate must include its numerator and denominator. `NOT_EVALUATED` is used when the
required labels or observations do not exist; it is not replaced with zero.

### Controller metrics

Let `N` be the number of reference scenarios, `y_i` the expected ordinal level, and `p_i` the
Controller level.

1. **Reference-policy agreement:** `sum(I[y_i = p_i]) / N`. This is Reference Policy V1
   conformance, not expert agreement.
2. **Per-level confusion matrix:** `C[a,b] = count(y_i=a and p_i=b)`, with expected levels as rows
   and observed levels as columns. A separate `MISSING` column preserves absent predictions.
3. **Quadratic weighted Cohen's kappa:**
   `kappa = 1 - observed_weighted_disagreement / expected_weighted_disagreement`, using
   `w(a,b)=(a-b)^2/(K-1)^2` for the seven ordered levels. It is descriptive paired-label agreement;
   with design-authored labels it must not be described as independent expert agreement.
4. **Over-support rate:** `count(p_i > y_i) / count(non-missing p_i)`.
5. **Under-support rate:** `count(p_i < y_i) / count(non-missing p_i)`.
6. **Transition-direction conformance:** for records with a prior level, compare the expected and
   observed direction (`ESCALATION`, `MAINTAINED`, or `FADING`). Report matching directions divided
   by eligible transition records. Transition reason conformance additionally requires the matching
   stable Controller reason code.

### Verifier metrics for a future independent dataset

Treat a labelled violation as the positive class. `INDETERMINATE` is an abstention and remains
separate from positive and negative predictions.

- Precision: `TP / (TP + FP)`.
- Recall or violation-detection rate: `TP / (TP + FN)`.
- F1: `2 * precision * recall / (precision + recall)`.
- False-positive rate: `FP / (FP + TN)`.
- False-negative rate: `FN / (FN + TP)`.
- INDETERMINATE rate: `indeterminate / all labelled responses`.
- Answer-leakage detection rate: correctly detected labelled leakage cases divided by all labelled
  leakage cases. Report exact-answer and equivalent-representation slices separately.

No verifier precision, recall, F1, or semantic-correctness metric is computed in Task 16A because
the repository has no independently labelled verifier corpus. Fake semantic-verifier judgments are
excluded.

### Fail-closed and retrieval metrics

- **Fail-closed rate:** unavailable-input cases that return a nondeliverable status divided by all
  frozen unavailable-input cases. A passing test suite alone is not the evaluation denominator.
- **Skill Mapper raw top-1 accuracy:** correct first-ranked skill divided by skill-labelled cases.
- **Confirmed-match precision:** correct confirmed `MATCHED` results divided by all confirmed
  matches, including wrong or unsupported confirmations.
- **Confirmed-match coverage:** skill-labelled cases receiving a confirmed correct match divided by
  all skill-labelled cases.
- **Abstention rate:** expected-match cases producing `AMBIGUOUS`, `NO_MATCH`, or
  `NOT_SKILL_RELATED` divided by expected-match cases.
- **Curriculum grounding validity:** independently reviewed responses whose claims are supported by
  eligible approved evidence divided by reviewed responses requiring grounding. Citation identity
  checks alone do not establish grounding validity.

Similarity scores are ranking signals, not calibrated probabilities.

### Metrics reserved for ethically approved learner studies

- **Assistance efficiency:** preregister a level-cost function and report successful independent
  outcomes per cumulative assistance cost. The cost function and success horizon must be fixed
  before analysing learner data.
- **Learning gain:** report pre/post differences and, only where appropriate, normalized gain
  `(post-pre)/(maximum-pre)`, with raw-score distributions and ceiling effects.
- **Hint dependency:** preregister a measure such as unsupported-transfer success after scaffolded
  practice divided by eligible transfer opportunities, stratified by prior assistance exposure.

These metrics require consented, de-identified learner observations and an approved study design.

## Versioned dataset specifications

`research/adaptive-tutor/evaluation-dataset-schema-v1.json` defines seven dataset families. Every
record requires a stable scenario ID, dataset version, origin, label author, review status, split,
source provenance, skill/grade/language fields, input evidence, applicable RQ, and an explicit
`contains_identifiable_child_data=false` assertion.

| Dataset family | Key outcome fields | Current status |
|---|---|---|
| Controller decision | Expected/observed level and reason codes | Canonical V1 source exists; referenced by ID |
| Transition/fading | Previous level and expected/observed direction | Derivable from canonical V1 source |
| Skill Mapper | Expected/observed status and skill, ranked candidates | Existing design-authored sets require schema migration/review |
| Verifier violation | Violation labels and expected/observed outcome | Missing independent dataset |
| Curriculum grounding | Evidence provenance and reviewed grounding validity | Missing approved corpus and labels |
| Baseline comparison | Condition, response reference, frozen rubric labels | Protocol only |
| Expert review | Reviewer role, disposition, corrections/comments | Protocol only; no review claimed |

Existing canonical fixtures are referenced by path and scenario ID rather than copied into a new
dataset. Grade and language remain `null` in the preliminary Controller records because Reference
Policy V1 does not specify them. The runner does not infer or fabricate these values. Reports omit
learner UUIDs.

## Preliminary measurements

The frozen Task 16A manifest produced these descriptive results on 2026-10-14:

| Measurement | Result | Evidence qualification |
|---|---:|---|
| Reference Policy V1 agreement | 20/20 (100%) | Design-authored synthetic conformance |
| Quadratic weighted kappa | 1.0 on 20 paired labels | Descriptive; not independent expert agreement |
| Over-support | 0/20 | Against design-authored expected levels |
| Under-support | 0/20 | Against design-authored expected levels |
| Transition-direction conformance | 13/13 | Scenarios with prior assistance |
| Transition reason-code conformance | 13/13 | Same eligible scenarios |
| Verifier precision/recall/F1 | NOT_EVALUATED | Independent violation labels unavailable |
| Fail-closed rate | NOT_EVALUATED | No frozen evaluation dataset |
| Curriculum grounding validity | NOT_EVALUATED | Approved corpus/review unavailable |
| Learning gain/effectiveness | NOT_EVALUATED | No learner study |

The existing real-E5 combined conservative run on the already-inspected design-authored held-out
Skill Mapper set reported raw top-1 `13/13`, top-3 `13/13`, confirmed-match precision `6/6`,
confirmed-match coverage `6/13`, seven incorrect abstentions among 13 expected matches, and zero
observed false confirmations. Task 16A does not rerun or relabel that experiment. These small-sample
figures are not independent validation.

## Verifier evaluation protocol for Task 16B

Create a response corpus outside implementation tests. Freeze source prompts, expected assistance
level, trusted answer/equivalence metadata, eligible curriculum evidence, language, grade, and
response provenance before running the verifier. Include independently reviewed examples of:

- exact and equivalent-form answer leakage;
- assistance-level and excessive-assistance violations across L0–L6;
- missing curriculum evidence and unsupported/fabricated citations;
- empty, malformed, and oversized response structures;
- explicit unsafe or age-inappropriate content;
- code-mixed and multilingual responses; and
- responses whose semantic correctness is genuinely uncertain.

Annotators must be blind to verifier output where possible. Record disagreements and adjudication.
Report categories separately; passing bounded unsafe-content patterns must never be described as
comprehensive child safety. Fake semantic judgments remain excluded.

## Baseline and ablation design for Task 16C

- **Baseline A:** conventional LLM tutor without learner-state adaptation, Controller V1, or the
  verifier.
- **Baseline B:** learner-state-aware LLM tutor without the explicit deterministic L0–L6 controller.
- **Proposed framework:** Controller-guided generation followed by verification.
- **Ablations:** proposed framework without Controller, without fading, and without verifier.

Use identical frozen items, model/version, decoding settings, response-language instructions,
curriculum availability, context windows, and maximum output budget wherever the condition permits.
Predefine prompts, random seeds or repeated-sampling plan, failure handling, delivery policy, and
evaluation rubrics. Randomize and blind expert review to condition. Report provider failures and
abstentions rather than silently retrying one condition more often. No baseline output or result is
manufactured in Task 16A.

## Validity and claim restrictions

- Twenty reference cases are too small for population claims and were authored alongside the
  policy, creating circular design-label bias.
- There is no independent curriculum/pedagogy review of Controller labels.
- Multilingual coverage is incomplete and qualified Sinhala/Tamil review is pending.
- Semantic verification is unvalidated; deterministic patterns cannot establish semantic truth or
  comprehensive safety.
- Real KT mastery, reviewed numeric support need, assessment evidence, and tutor history integration
  are missing.
- There is no approved runtime curriculum corpus for grounding evaluation.
- There are no learner outcomes, learning-gain measurements, or educational-effectiveness results.
- Child data, provider eligibility, privacy, consent, retention, and governance restrictions remain
  unresolved for a real study.

Implementation correctness, offline policy conformance, expert pedagogical validity, and learner
effectiveness are four distinct evidence levels. Task 16A reaches only the first two, and the second
only relative to design-authored policy labels.

## Reproduction

From the repository root, without network or database access:

```bash
cd backend
.venv/bin/python scripts/evaluate_adaptive_tutor.py
```

The command validates the manifest/dataset version and regenerates:

- `research/adaptive-tutor/results/controller-reference-policy-v1.json`
- `research/adaptive-tutor/results/controller-reference-policy-v1.md`

Focused tests:

```bash
backend/.venv/bin/pytest -q backend/tests/adaptive_tutor/test_evaluation.py
```

## Task 16B entry criteria

Task 16B should create and independently review a frozen verifier/controller evaluation corpus,
including qualified Grade 4–5 curriculum/pedagogy review and Sinhala/Tamil language review. It must
define annotator guidance, reviewer roles, blinding, adjudication, inter-rater agreement, split
discipline, sample-size rationale, permissions, and non-identifiable provenance. Only then should
verifier precision/recall/F1 or independent Controller agreement be reported.

Task 16C additionally requires authorized comparable model access, frozen prompts and sampling
settings, approved curriculum evidence, evaluation rubrics, and governance approval. It must not use
real children or make learner-facing calls merely because the offline runner works.
