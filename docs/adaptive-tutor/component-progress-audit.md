# Adaptive AI Tutor — Component Progress Audit

- Component: *A Verified Minimum-Sufficient Adaptive Scaffolding Framework for LLM-Based Primary Tutoring*
- Audit date: 2026-10-21 · Branch `feature/tutor-api` · HEAD `61b58bd` (clean working tree, pushed)
- Method: source inspection, local test/lint runs, committed result files. No live Gemini calls, no
  model downloads, no database writes, no configuration or behaviour changes.

## Evidence legend

| Tag | Meaning |
|---|---|
| **[CODE]** | Verified by reading the current source in this audit |
| **[TEST]** | Covered by a passing automated test (unit/integration, mocks or fixtures unless stated) |
| **[RUN]** | Executed in this audit or recorded in a committed result file with real models/data |
| **[REPORTED]** | Stated by the developer or an earlier session; not re-verified here |
| **[UNKNOWN]** | Could not be checked (e.g. database offline) |

A passing unit test proves wiring and rule behaviour only. It is never treated here as proof that a
feature works end to end or that a research objective is validated.

---

## 1. Executive Summary

The component has a substantial, well-tested **policy and safety skeleton**: a deterministic L0–L6
Controller, fail-closed orchestration, multilingual E5 skill mapping, a Gemini adapter, curriculum
approval gates, a deterministic verifier, persistence for history and assessment, a research API,
and a React research chat. 2,669 backend tests and 602 frontend tests pass.

What is **not** yet demonstrated is the research claim itself in a running system:

1. **Escalation and fading never happen at runtime.** No production code records a
   `RESPONSE_DELIVERED` event and history always returns `previous_hint_effective=None`
   (`tutor_history.py:383`). In live sessions the Controller can only make *initial* decisions
   (max L3) or reset to L0 on success; L4–L6 and fading are reachable only in offline evaluation.
2. **The verified delivery path has never produced an approved response.** It requires approved
   curriculum (0 of 189 chunks approved), an independent semantic verifier (disabled, no provider)
   and a trusted answer (configured for one exact question; empty locally).
3. **The PP1 experimental path bypasses verification by design** and uses SYNTHETIC cold-start
   mastery (0.0) and support need (0.0).
4. **Research validation is limited to design-authored data.** Controller conformance is 20/20
   against labels written alongside the policy; verifier, fail-closed, grounding, baseline and
   learner metrics are `NOT_EVALUATED`.

| Progress view (planning estimates, see §10) | Estimate |
|---|---:|
| Implementation progress | **≈ 69%** |
| Integration readiness (real services/data, end to end) | **≈ 34%** |
| Research validation (defensible evidence) | **≈ 16%** |

---

## 2. Current Architecture

```text
React research chat (ResearchInteraction / ResearchDiagnostics)
        │  X-Tutor-Research-Key, loopback only
        ▼
FastAPI research router (api/router.py) ─► ResearchTutorService (in-memory sessions)
        │
        ▼
TutorOrchestrator.run (application/orchestration.py)
  1 ConversationalSkillMapper (E5, pinned revision)          ── REAL model
  2 TutorContextAssembler: learner · KT mastery · Learner-State support need
                           · assessment ledger · assistance history
  3 ScaffoldingController.decide (deterministic V1)
  ── decision_only=True (PP1) stops here ─► ExperimentalHintGenerator ─► Gemini (unverified)
  4 HybridCurriculumRetriever (pgvector, APPROVED-only)
  5 Gemini generation (≤ 3 drafts)
  6 verify_generation_result (deterministic checks + optional semantic verifier)
  7 Authorization: REAL evidence + non-simulated verifier + authorized provider
        ▼
APPROVED_RESPONSE  (never observed at runtime)
```

Persistence: `tutor_interaction_events`, `tutor_assessment_interactions`,
`tutor_assessment_attempts` (Alembic `20261018_02`, `20261018_03`). Research sessions are held in a
process-local dict (`research_sessions.py:240`) and are lost on restart.

---

## 3. Research Objectives vs Implementation

No approved proposal exists in the repository. `research-evaluation-framework.md` defines
*provisional* RQ1–RQ5; these are used here.

| RQ | Question (abridged) | Implementation | Evidence | Status |
|---|---|---|---|---|
| RQ1 | Controller agreement with Reference Policy V1 | `controller.py`, `evaluation.py` | [RUN] 20/20, κw = 1.0 on design-authored labels | Measured, **not independently validated** |
| RQ2 | Effect of mastery/support/severity/history on level and escalation/fading | Controller logic complete | [RUN] 13/13 transitions offline only; runtime transitions unreachable (§1) | **Partially measured; runtime gap** |
| RQ3 | Verifier violation detection | `verification.py` | No labelled corpus | **NOT_EVALUATED** |
| RQ4 | Fail-closed rate on missing/failed inputs | Orchestrator fail-closed branches | [TEST] behaviour only; no frozen dataset | **NOT_EVALUATED** |
| RQ5 | Comparison with baselines A/B and ablations | Protocol only | None | **NOT_STARTED** |
| (support) | Skill mapping reliability | E5 mapper + v2 benchmark | [RUN] diagnostic, unreviewed corpus | Preliminary |

The central "minimum-sufficient with escalation **and fading**" claim currently rests only on
offline synthetic scenarios.

---

## 4. Feature Completion Matrix

Status key: COMPLETE · PARTIAL · NOT IMPLEMENTED · BLOCKED · UNKNOWN. Data key: R=real,
S=synthetic, M=mock/fixture. Priority: P0 (blocks research claim) → P3.

### A. Multilingual input and Skill Mapper

| Item | Status | Source | Tests | Runtime evidence | Data | Remaining | Pri |
|---|---|---|---|---|---|---|---|
| E5 retrieval (`query:`/`passage:` prefixes, normalized cosine, pinned rev) | COMPLETE | `skill_mapper.py` `SemanticSkillRetriever`; `embeddings.py` | [TEST] `test_skill_mapper.py` (31) | [RUN] benchmark v2 | R model / S labels | — | — |
| Ambiguity + clarification | COMPLETE (mechanism) | `ConversationalSkillMapper.map` (0.82 / 0.70 / 0.03) | [TEST] | [RUN] clarifies 108/119 test cases | R/S | Thresholds unvalidated | P1 |
| Fraction-notation signal with time/date veto | COMPLETE | `has_explicit_fraction_notation` | [TEST] 30+ cases | [RUN] probes | R/S | Reviewed evaluation | P2 |
| English / Sinhala / Tamil / code-mixed | PARTIAL | taxonomy has EN scope + SI name only | [TEST] | [RUN] test top-1: EN 9/13, SI 6/14, TA 7/13 | R/S | Reviewed multilingual skill text | P1 |
| Singlish / Tanglish | PARTIAL (weak) | no romanized resources in live path | — | [RUN] top-1 4/14 and 5/13 | R/S | Romanized enrichment + review | P1 |
| Enrichment & relevance gate | PARTIAL | catalogs exist; **not used in live composition** (`local_research.py:154`) | [TEST] | eval-only | S | Decide & evaluate | P2 |
| Cross-encoder (bge-reranker-v2-m3) | PARTIAL — benchmark only | `backend/tools/skill_mapper_benchmark/` | [TEST] 15 | [RUN] §8 | R model / S labels | Not integrated by design | P2 |
| Latency | COMPLETE (measured) | — | — | [RUN] E5 p50 ≈ 6–8 ms; hybrid ≈ 0.5–0.7 s; all-30 ≈ 1.1–1.4 s | R | — | — |

### B. Deterministic Scaffolding Controller

| Item | Status | Source | Tests | Runtime evidence | Remaining | Pri |
|---|---|---|---|---|---|---|
| L0–L6 decision logic, reason codes | COMPLETE | `controller.py` `ScaffoldingController.decide` | [TEST] `test_controller.py` (16), `test_reference_scenarios.py`, `test_evaluation.py` | [RUN] 20/20 reference | Independent review | P1 |
| Initial selection (max L3) | COMPLETE | `_initial_level` | [TEST] | [REPORTED] L0 at pre-interaction in UI | — | — |
| Escalation / fading / maintenance | COMPLETE in code, **unreachable at runtime** | `_select_level` needs `previous_assistance_level` + `previous_hint_effective` | [TEST] offline only | None live (§9) | Wire history (P0) | **P0** |
| Determinism | COMPLETE | pure function; `assert` used for invariants | [TEST] | — | Replace `assert` (stripped under `-O`) | P3 |
| Missing/conflicting evidence | PARTIAL | Controller requires numeric mastery/support; unknown handled upstream by NOT_READY or synthetic defaults | [TEST] | — | Explicit cold-start policy in research design | P1 |

### C. Learner Context

| Item | Status | Source | Tests | Runtime | Data | Remaining | Pri |
|---|---|---|---|---|---|---|---|
| Shared learner lookup | COMPLETE | `shared_learner.py` | [TEST] | [REPORTED] | R | — | — |
| KT mastery | PARTIAL | `knowledge_tracing_mastery.py`; real model, mastery from paper answers | [TEST] (17) | [UNKNOWN] DB offline | R when history exists | Tutor attempts never update KT | P1 |
| Learner-State support need | PARTIAL | `learner_state_support_need.py`; requires fresh same-session capture | [TEST] (14) | [UNKNOWN] | R when captured | Practical capture in tutor session | P1 |
| Assessment evidence | PARTIAL | `assessment_evidence.py`, `tutor_assessment.py`; only researcher-annotated attempts | [TEST] | [REPORTED] annotation flow | R (manual) | Learner answer capture/auto-grading | P1 |
| Interaction history | PARTIAL — defect | `tutor_history.py`; never sees DELIVERED; hint effectiveness always `None` | [TEST] with hand-written DELIVERED events | — | — | **P0 fix** | **P0** |
| Cold start (PP1) | PARTIAL, research-only | `local_research.py:206-207` mastery 0.0, support 0.0 | [TEST] | [REPORTED] | **S** | Justify defaults; per-value provenance | P1 |
| Synthetic isolation | PARTIAL | Provider-level SYNTHETIC label even when a real value is returned (`knowledge_tracing_mastery.py:52`) | [TEST] | — | — | Label per value | P2 |

### D. Gemini Integration

| Item | Status | Source | Tests | Runtime | Remaining | Pri |
|---|---|---|---|---|---|---|
| google-genai adapter, timeout, no-retry | COMPLETE | `gemini.py` `GeminiLlmProvider` | [TEST] (18) | [RUN earlier session] 1 probe success with thinking LOW; adapter call timed out | Reliability study | P1 |
| Sanitized error reason codes | COMPLETE | `ProviderFailureReason` | [TEST] | — | — | — |
| Level-specific prompts | COMPLETE | `generation.py` `build_generation_prompt`, `assistance_level_instruction` | [TEST] (20) | — | Prompt evaluation | P2 |
| Model / thinking config | PARTIAL | local `.env`: `gemini-3.1-flash-lite`; `TUTOR_GEMINI_THINKING_LEVEL` unset | — | [REPORTED] real responses reach UI | Pin & document model | P1 |
| Real response reaches frontend | PARTIAL | experimental field only | [TEST] | **[REPORTED]**, not verified in this audit | Captured demo evidence | P1 |

### E. Curriculum RAG

| Item | Status | Source | Runtime / data | Remaining | Pri |
|---|---|---|---|---|---|
| Ingestion, chunking, registry | COMPLETE (pipeline) | `app/curriculum/*`, `scripts/build_curriculum_*` | 189 chunks, Grade 5, SI 149 / EN 40 / **TA 0**, 17 of 30 skills, MAT-FRC 4 | Coverage | P1 |
| Approval gate | COMPLETE | `pgvector_index.py:154,179,184` APPROVED-only | **0/189 approved** (`REVIEW_PENDING`) | Curriculum review | **P0 for verified path** |
| Retrieval in live DB | UNKNOWN | `HybridCurriculumRetriever` | DB offline during audit | Demonstrate | P1 |
| Grounding/provenance in responses | PARTIAL | citation identity checks in verifier | Never exercised with approved evidence | Grounding evaluation | P1 |
| Mandatory L6 evidence | COMPLETE (gate) | `orchestration.py:366` | L6 unreachable at runtime anyway | — | — |
| PP1 unreviewed template | Research-only | `fractions-content.UNREVIEWED.txt` | S/unreviewed; never indexed | — | — |

### F. Semantic Verification and Authorization

| Item | Status | Source | Tests | Remaining | Pri |
|---|---|---|---|---|---|
| Deterministic checks (structure, level structure, leakage, script, unsafe patterns, citations) | COMPLETE (rules) | `verification.py` | [TEST] (25) | Independent labelled corpus | P0 (RQ3) |
| Mathematical correctness | NOT IMPLEMENTED deterministically | delegated to semantic `factual_support` | — | Decide approach | P1 |
| Answer-leakage trusted answers | PARTIAL | `ConfiguredResearchTrustedAnswerProvider`: **one exact question** | [TEST] | Answer source at scale | P1 |
| Semantic verifier adapter | PARTIAL | `semantic_verifier.py` (OpenAI-compatible) | [TEST] (5, mocked) | Provider, independence, never run live | P1 |
| Regeneration (≤ 2 retries) | COMPLETE | `orchestration.py:416-508` | [TEST] | — | — |
| Authorization / fail-closed | COMPLETE | `TutorWorkflowResult.validate_delivery_boundary`, provider allow-list | [TEST] (30 orchestration) | Frozen RQ4 dataset | P1 |
| Research-only safeguards | COMPLETE | loopback + key (`router.py:120-137`), experimental text never in `response_text`, contract validators | [TEST] | — | — |

### G. Multi-turn Tutoring

| Item | Status | Source | Remaining | Pri |
|---|---|---|---|---|
| Sessions | PARTIAL | in-memory `ResearchTutorService` | Persistence if needed | P2 |
| Attempts + feedback | PARTIAL | researcher annotation (`AttemptForm`, `/attempts`) | Learner answer entry | P1 |
| Assessment persistence | COMPLETE | ledger tables + idempotency | — | — |
| Context update after attempt | PARTIAL | attempt count & severity flow; mastery static | KT feedback | P1 |
| Level changes across turns | **BLOCKED by defect** | history wiring (§1) | **P0** | **P0** |
| Frontend history/continuity | COMPLETE (in-page) | `ResearchInteraction` turns | — | — |

### H. Frontend

| Item | Status | Evidence | Remaining | Pri |
|---|---|---|---|---|
| Chat UI, pinned composer, retry, new chat | COMPLETE | [TEST] `ResearchInteraction.test.tsx` | Browser validation | P2 |
| Unverified amber bubble + "Not verified" tag | COMPLETE | [TEST] | — | — |
| Researcher diagnostics (tiles, evidence, checks, technical) | COMPLETE | [TEST] | — | — |
| Real API integration | PARTIAL | [REPORTED] | Recorded demo | P1 |
| Learner-facing experience | NOT APPROPRIATE YET | Mindy tab embeds the research chat | Separate learner path behind verified delivery | P2 |
| Accessibility / mobile | PARTIAL | ARIA roles and labels in jsdom tests only | Manual or Playwright checks | P2 |
| Test enforcement | PARTIAL | 602 tests pass, but `check.sh push` does **not** run vitest; Node 26 needs `--no-experimental-webstorage` | Add to CI | P2 |
| Research key in client bundle | RISK | `VITE_TUTOR_RESEARCH_KEY` is embedded at build time | Acceptable only on loopback | P2 |

### I. Research and Evaluation — see §3, §8, §12.

### J. Infrastructure and Quality

| Item | Status | Evidence |
|---|---|---|
| Migrations for tutor tables | COMPLETE | Alembic `20261018_02/03` [CODE] |
| Database state | UNKNOWN | PostgreSQL not running at audit time |
| Config gating & secrets | COMPLETE | all live paths opt-in; secrets server-side [CODE] |
| Logging | PARTIAL | sanitized warning logs; no metrics/tracing |
| Tests | COMPLETE (unit/integration) | §6 |
| End-to-end automated test with real services | NOT IMPLEMENTED | — |
| Deployment readiness | NOT READY | loopback-only research mode, in-memory sessions |

---

## 5. Real vs Synthetic vs Mocked Dependencies

| Dependency | Live research (verified path) | PP1 experimental | Tests |
|---|---|---|---|
| Skill Mapper (E5) | R | R | Fake embeddings |
| Learner | R | R | SQLite fixtures |
| KT mastery | R or NOT_READY | **S 0.0 if missing** (provider labelled S always) | Fakes |
| Support need | R or NOT_READY | **S 0.0 if missing** | Fakes |
| Assessment | R (researcher annotation) | R (researcher annotation) | Fixtures |
| History | R but never DELIVERED | R, never DELIVERED | Hand-written events |
| Curriculum | R gate, 0 approved | Unreviewed template (S) | Synthetic retriever |
| Gemini | R | R (unverified output) | Recording fakes |
| Semantic verifier | Not configured | Not used | `DeterministicFakeSemanticVerifier` |
| Trusted answer | Not configured | Not used | Fixtures |

---

## 6. Test and Runtime Evidence

Commands run during this audit:

| Command | Result |
|---|---|
| `backend/.venv/bin/python -m pytest -q` | **2669 passed, 1 skipped** (118.6 s) |
| `npx vitest run` with `NODE_OPTIONS=--no-experimental-webstorage` | **602 passed / 79 files** |
| `npx vitest run` (plain, Node 26.5) | 602 failed: `localStorage` shadowed by Node web storage (CI uses Node 24) |
| `npx tsc -b` | pass |
| `npx biome lint src --error-on-warnings` | pass |
| `ruff check .` (backend) | pass |
| Read-only DB query | **failed: PostgreSQL not running**, so DB evidence is UNKNOWN |

Adaptive-tutor test inventory: 28 files, 370 test functions before parametrization (largest:
skill mapper 31, orchestration 30, verification 25, context assembly 24).

Committed runtime evidence:

- `research/adaptive-tutor/results/controller-reference-policy-v1.json`: 20/20 agreement (synthetic).
- `research/adaptive-tutor/skill-mapper-v2/results/benchmark-v2.json`: real E5 and bge-reranker on an
  unreviewed corpus.
- No committed evidence of an `APPROVED_RESPONSE`, a live multi-turn escalation, or grounded
  retrieval.

Reported only (earlier sessions):

- Real Gemini text reached the research UI.
- The UI showed the Controller decision L0 / PRE_INTERACTION.

---

## 7. Technical Debt and Risks

| # | Issue | Evidence | Impact | Severity |
|---|---|---|---|---|
| 1 | No `RESPONSE_DELIVERED` producer; `previous_hint_effective` always `None` | `tutor_history.py:383`; `grep` shows tests only | Escalation and fading unreachable live; RQ2 cannot be shown at runtime | **Critical** |
| 2 | Hint effectiveness has no defined data source | not derived anywhere | Controller transition inputs undefined in practice | **Critical** |
| 3 | 0/189 curriculum chunks approved; no Tamil; 17/30 skills | `chunks.jsonl` | Verified path and grounding blocked | High |
| 4 | Semantic verifier not configured; one trusted question | `.env`, `local_research.py` | `APPROVED_RESPONSE` impossible | High |
| 5 | Provider-level synthetic labelling | `knowledge_tracing_mastery.py:52`, `learner_state_support_need.py:50` | PP1 logs cannot separate real from default values | Medium |
| 6 | Tutor attempts do not update KT mastery | no KT writes from tutor | Mastery static within a session | Medium |
| 7 | Design-authored, unreviewed datasets throughout | provenance fields | All metrics diagnostic | High (research) |
| 8 | In-memory research sessions | `research_sessions.py:240` | Lost on restart | Low |
| 9 | Frontend tests not in push/CI check | `scripts/check.sh` | Regressions unguarded | Low |
| 10 | Documentation drift | `pp1-experimental-demo.md:56-57` says missing KT/LS stays blocked; code uses synthetic defaults | Misleading for PP1 | Low |
| 11 | Local environment | `backend/.venv` is a symlink to `.venv313`; disk was full during setup | Fragile setup | Low |
| 12 | `assert` used for invariants in Controller/orchestrator | `controller.py:84` and others | Stripped under `python -O` | Low |

---

## 8. Skill Mapper Evaluation Status

Corpus v2: 270 design-authored cases (`DESIGN_AUTHORED_UNREVIEWED`). Development 151 and test 119,
group-disjoint, with all 30 skills × 7 language forms. Policies were fitted on development under zero
observed false confident matches. **Diagnostic only.**

Test split (counts with denominators):

| Configuration | Top-1 | Confident & correct | False confident | Clarify | Macro-F1 | p50 latency CPU / MPS |
|---|---|---|---|---|---|---|
| E5 (HEAD) | 57/101 | 7/101 | 0/119 | 111/119 | 0.099 | 6 / 8 ms |
| E5 (working tree, live) | 57/101 | 10/101 | 0/119 | 108/119 | 0.113 | 6 / 7 ms |
| E5 recalibrated on dev | 55/101 | 2/101 | 0/119 | 104/119 | 0.055 | 7 / 8 ms |
| Hybrid E5 top-15 + bge | 72/101 | 32/101 | **3/119** | 57/119 | 0.394 | 714 / 534 ms |
| All-30 bge | 71/101 | 30/101 | **3/119** | 60/119 | 0.377 | 1371 / 1084 ms |

- 95% bootstrap CI for coverage: hybrid 0.23–0.41 vs E5 working tree 0.04–0.16.
- Hybrid false confident matches: `SM2-MAT-NUM-7` (misspelled number → MAT-OPS), `SM2-INT-02`
  ("What is 3/4?") and `SM2-INT-06` ("How much is half of it?"). The last two are confidently mapped
  to MAT-FRC; their AMBIGUOUS labels are themselves debatable and need review.
- Singlish remains weak in every configuration (top-1 ≤ 5/14).
- The evidence veto changed no outcome.
- The hybrid shortlist hit its k = 15 cap because E5 never reached 95% development recall.

Conclusion: the reranker improves ranking and coverage but did not meet the zero-false-match target
on held-out data and is 75–150× slower. The live mapper is unchanged.

Required before any decision:

1. Qualified review of the corpus labels.
2. A fresh, independently sourced test split.
3. Reviewed multilingual and romanized skill text.

---

## 9. End-to-End Readiness

| Path | Demonstrated? | Evidence |
|---|---|---|
| Question → mapping → context → Controller decision (L0) | Yes, research mode | [REPORTED] UI response; [TEST] |
| … → experimental Gemini draft shown as unverified | Yes, research mode | [REPORTED] |
| Attempt annotation → new Controller decision | Partly | [TEST] `test_research_multiturn.py`: always an *initial* level |
| Escalation L2 → L3 → L4 … or fading over turns | **No** | Defect §7-1 |
| Approved-curriculum retrieval in a live response | **No** | 0 approved chunks |
| Verified `APPROVED_RESPONSE` delivered | **No** | Verifier and trusted answers unconfigured |
| Learner-facing verified tutor | **No** | — |

---

## 10. Progress Percentages and Calculation

**These are planning estimates, not objective measurements.** No approved proposal defines weights.
Weights below come from the architecture's pipeline stages and the provisional RQs, giving extra
weight to the Controller and verification as the component's research contribution. Scores are
auditor judgements from §4.

### 10.1 Implementation progress (code exists and is tested, any data)

| Workstream | Weight | Score | Weighted | Basis |
|---|---:|---:|---:|---|
| A Skill Mapper | 10 | 75 | 7.5 | Complete E5 path; multilingual resources and CE not integrated |
| B Controller | 15 | 90 | 13.5 | Complete V1; cold-start policy implicit |
| C Learner context | 12 | 60 | 7.2 | All adapters exist; history and KT feedback gaps |
| D Gemini | 8 | 85 | 6.8 | Adapter, errors, prompts done |
| E Curriculum RAG | 10 | 60 | 6.0 | Pipeline and gates done; content not approved |
| F Verification & authorization | 15 | 65 | 9.75 | Rules done; no math check; one trusted answer |
| G Multi-turn | 12 | 50 | 6.0 | Sessions and ledger done; transitions not wired |
| H Frontend | 8 | 70 | 5.6 | Research UI done; no learner path |
| I Evaluation tooling | 5 | 70 | 3.5 | Controller runner and mapper benchmark |
| J Infrastructure | 5 | 65 | 3.25 | Migrations and gating; no observability |
| **Total** | **100** | | **≈ 69.1** | |

### 10.2 Integration readiness (works end to end with real services and data)

| Workstream | Weight | Score | Weighted | Basis |
|---|---:|---:|---:|---|
| A | 10 | 50 | 5.0 | Live, but confident coverage about 10% |
| B | 15 | 40 | 6.0 | Live initial decisions only |
| C | 12 | 25 | 3.0 | Real only when history exists; PP1 uses synthetic |
| D | 8 | 55 | 4.4 | Reported working; reliability unmeasured |
| E | 10 | 5 | 0.5 | No approved content; DB unknown |
| F | 15 | 5 | 0.75 | Verified path never run live |
| G | 12 | 30 | 3.6 | Turns work; levels don't transition |
| H | 8 | 55 | 4.4 | Reported live; no browser validation |
| I | 5 | 70 | 3.5 | Offline runners execute |
| J | 5 | 50 | 2.5 | DB offline at audit |
| **Total** | **100** | | **≈ 33.7** | |

### 10.3 Research validation (defensible evidence)

| Evidence area | Weight | Score | Weighted | Basis |
|---|---:|---:|---:|---|
| RQ1 Controller conformance | 15 | 40 | 6.0 | Measured; circular labels |
| RQ2 Evidence/transition behaviour | 15 | 25 | 3.75 | Offline only |
| RQ3 Verifier detection | 20 | 5 | 1.0 | Protocol only |
| RQ4 Fail-closed | 10 | 15 | 1.5 | Tests, no frozen dataset |
| RQ5 Baselines/ablations | 20 | 5 | 1.0 | Protocol only |
| Skill mapping validity | 10 | 25 | 2.5 | Unreviewed corpus benchmark |
| Expert/learner review | 10 | 0 | 0.0 | None |
| **Total** | **100** | | **≈ 15.8** | |

Unknowns excluded from scores: live DB contents, KT data availability for demo learners, Learner
State capture in tutor sessions, and Gemini reliability on the current model.

---

## 11. PP1 Readiness

No PP1 rubric is in the repository; readiness is judged against a credible prototype demonstration.

| Criterion | Ready? |
|---|---|
| Live question → skill → Controller decision in UI | Yes (reported) |
| Real Gemini draft clearly labelled unverified | Yes (reported) |
| Researcher diagnostics and provenance | Yes |
| Multi-turn escalation/fading demonstration | **No** (P0 defect) |
| Verified response | No (acceptable for PP1 if stated explicitly) |
| Offline Controller evaluation results | Yes (synthetic) |
| Skill mapper benchmark | Yes (diagnostic) |

**Verdict:** PP1 can show the architecture, safety boundaries and a single-turn live decision. To
claim *adaptive* scaffolding, fix the history wiring (P0-1) and record one multi-turn session.

---

## 12. Final Research Readiness

Not ready. Missing:

- independently reviewed Controller labels
- a verifier violation corpus (RQ3)
- a frozen fail-closed dataset (RQ4)
- baseline runs (RQ5)
- approved curriculum and grounding review
- reviewed multilingual skill data
- ethics/governance for any learner study

---

## 13. Prioritized Remaining Tasks

Effort assumes one developer, existing code, and reviewers available when needed. Uncertainty is
±50% where external review is involved.

| ID | Task | Pri | Effort | Depends on | Acceptance criteria |
|---|---|---|---|---|---|
| T1 | Define and record a research-mode "presented" history event (distinct from learner DELIVERED); derive `previous_hint_effective` from the next annotated attempt | P0 | 2–3 d | — | Integration test: L2 → incorrect ×N → L3 → L4 per policy; correct → fading; synthetic origin labelled |
| T2 | Record a live multi-turn PP1 session showing escalation and fading | P0 | 0.5 d | T1 | Saved transcript/screens with provenance; ≥ 1 escalation and 1 fading |
| T3 | Fix PP1 doc drift; document cold-start defaults and justification | P1 | 0.5 d | — | Doc matches code; defaults justified |
| T4 | Per-value provenance for defaults | P2 | 1 d | — | REAL mastery labelled REAL in PP1 mode; tests |
| T5 | Pin Gemini model + thinking level; measure success/latency over N fixed prompts (with approval) | P1 | 1 d | approval | Success rate and p95 latency reported |
| T6 | Curriculum review: approve MAT-FRC (then others); add Tamil | P0 (verified path) | 1–3 wk (external) | curriculum reviewer | ≥ 1 skill with approved chunks; retrieval returns APPROVED evidence live |
| T7 | Configure independent semantic verifier + trusted-answer source beyond one question | P1 | 3–5 d | provider approval | One `APPROVED_RESPONSE` produced live in research mode |
| T8 | Verifier violation corpus (RQ3) with blind review | P0 (research) | 2–3 wk | reviewers | Precision/recall/F1 with CIs |
| T9 | Frozen fail-closed dataset (RQ4) | P1 | 2–3 d | — | Rate with denominator in a results file |
| T10 | Independent review of Reference Policy V1 labels | P1 | 1–2 wk | pedagogy expert | Agreement and κ vs expert labels |
| T11 | Baselines A/B + ablations (RQ5) | P1 | 2–3 wk | T6–T8, model access | Frozen comparison report |
| T12 | Corpus v2 human review + fresh test split; rerun mapper benchmark | P1 | 1–2 wk | language reviewers | Reviewed metrics; integration decision |
| T13 | Feed tutor attempts into KT (with KT owner) | P2 | 3–5 d | KT team | Mastery changes after tutor attempts |
| T14 | Add vitest to `check.sh push`/CI; Playwright smoke | P2 | 1–2 d | — | CI fails on frontend test regressions |
| T15 | Learner-facing path (separate from research UI) behind verified delivery | P3 | 1–2 wk | T6, T7 | Only `APPROVED_RESPONSE` shown to learners |

Required integrations with other team members:

- **Knowledge Tracing:** T13.
- **Learner State:** practical same-session capture.
- **Shared curriculum RAG:** T6, under the agreed joint plan `shared-rag-joint-plan.md`.
- **Gamification:** the Mindy tab hosts the tutor.

Recommended order: T1 → T2 → T3 → T5 → T9 → T6 ∥ T12 → T7 → T8 → T10 → T11 → T4/T13/T14 → T15.

---

## 14. Recommended Next Three Development Milestones

1. **M1 — Adaptive loop demonstrable (PP1).** T1, T2, T3, T5. Exit: recorded live session with
   escalation and fading, honest labels, pinned model.
2. **M2 — First verified response.** T6 (MAT-FRC approved), T7, T9. Exit: one live
   `APPROVED_RESPONSE` grounded in approved curriculum, plus a frozen fail-closed report.
3. **M3 — Defensible evaluation.** T8, T10, T12, then T11. Exit: reviewed datasets with RQ1–RQ5
   metrics reported with denominators and CIs, and limitations stated.
