# Skill Mapper Evaluation Protocol V2

## Status and scope

This document defines the next evaluation protocol for the Conversational Skill
Mapper. It does not change the mapper, the pinned E5 model, the `0.82` match
threshold, the `0.70` candidate threshold, or the `0.03` minimum margin. It does
not authorize Task 11 integration.

`docs/skill_nodes.xlsx` remains the sole authoritative source for the 30 skill
identities, names, Sinhala designations, and curriculum scopes. This protocol
does not modify or duplicate that taxonomy as an operational source of truth.

## Existing evidence and dataset provenance

The current resources have these roles:

| Resource | Provenance | Permitted use |
|---|---|---|
| `skill-mapper-evaluation-v1.json` | Design-authored, preliminary | Diagnostic baseline only |
| `skill-mapper-development-v1.json` | Design-authored, preliminary | Development experiments |
| `skill-mapper-held-out-v1.json` | Design-authored, preliminary, already inspected | Existing benchmark; not an untouched final test set and not for further threshold tuning |
| `skill-mapper-relevance-v1.json` | Design-authored, preliminary | Development of relevance behavior |
| `skill-mapper-enrichment-v1.json` | Design-authored provisional language text | Retrieval experiment; qualified language review pending |

Every future example must carry one of these provenance labels:

- `DESIGN_AUTHORED_UNREVIEWED`: written by the project team and not accepted as
  linguistic or curriculum ground truth.
- `HUMAN_REVIEWED`: reviewed by an appropriately qualified Sinhala or Tamil
  language reviewer and, where needed, a Grade 4–5 curriculum subject-matter
  reviewer. The review record must retain date, disposition, and corrections.
- `INDEPENDENTLY_SOURCED`: collected independently of model output and threshold
  selection. Its source, permission or licence, collection method, de-identification,
  and annotation process must be recorded.

No existing dataset qualifies as independently sourced or human-reviewed.

## V2 corpus construction protocol

The next versioned corpus must cover every authoritative skill. Before collection,
freeze a case schema, annotation guide, mapper configuration, and split policy.
Do not generate labels from the mapper prediction.

For each of the 30 skills, the coverage gate requires at least one independently
labelled example in each of these forms:

1. English
2. Sinhala script
3. Tamil script
4. Singlish
5. Tanglish
6. code-mixed language
7. informal or misspelled child language

This 210-case coverage gate is a minimum matrix, not a claim of statistical
adequacy. Larger, independently collected samples are required before reporting
stable population estimates.

The corpus must also contain explicitly labelled interaction cases. A case may
satisfy both the skill/language matrix and an interaction category.

- unsupported curriculum topics, expected `NO_MATCH`
- greetings and off-topic messages, expected `NOT_SKILL_RELATED`
- genuinely ambiguous skill requests, expected `AMBIGUOUS`
- short answers or submitted attempts
- contextual follow-ups where history resolves the skill
- stale-context overrides where a new self-contained question must replace the
  active skill
- close curriculum boundaries between confusable skills
- symbol-heavy questions and spelling variation

Ambiguous examples must be independently annotatable as ambiguous; disagreement
between authors is not by itself evidence of learner-message ambiguity.

## Split and review discipline

1. Use design-authored examples only for development and failure diagnosis.
2. Have qualified reviewers correct language and intended meaning before examples
   enter a human-reviewed calibration set.
3. Record curriculum review for boundary cases and skill labels.
4. Freeze the model, enrichment, relevance gate, decision policy, and evaluation
   script before opening an independently sourced final test split.
5. Never tune on the final split. Report every frozen configuration attempted on
   any benchmark used for comparison.
6. Keep exact duplicates and near-duplicates in the same split. Check semantic
   leakage across splits before evaluation.

The existing held-out benchmark has already informed analysis. It cannot be
renamed or reused as fresh independent evidence.

## Required metrics

Report counts and denominators with every rate:

- **Raw top-1 retrieval accuracy:** expected skill ranked first divided by
  skill-labelled cases. This ignores the decision policy.
- **Raw top-3 retrieval accuracy:** expected skill anywhere in the first three
  ranks divided by skill-labelled cases.
- **Confirmed-match precision:** correct confirmed `MATCHED` outputs divided by
  all confirmed `MATCHED` outputs, including unsupported cases incorrectly
  confirmed.
- **Confirmed-match coverage:** skill-labelled cases receiving a confirmed
  `MATCHED` output divided by all skill-labelled cases.
- **False confirmations:** `MATCHED` outputs with no expected skill or with the
  wrong confirmed skill. Report count, case IDs, and rate among confirmations.
- **Incorrect abstentions:** expected `MATCHED` cases emitted as `AMBIGUOUS`,
  `NO_MATCH`, or `NOT_SKILL_RELATED`. Report count, case IDs, and rate among
  expected matches.
- **Status behavior:** a complete expected-status by actual-status confusion
  matrix, including separate `NO_MATCH` and `NOT_SKILL_RELATED` rows.
- **Intent accuracy:** expected intent versus emitted intent, with a confusion
  matrix once the reviewed corpus is available.
- **Slices:** all retrieval and decision metrics by language category and by
  expected skill ID. Suppress or clearly warn about rates with very small
  denominators; never average per-skill rates without stating the weighting.

Cosine similarity from E5 is a ranking signal, not a calibrated probability of
correctness, learner mastery, or curriculum membership.

## Taxonomy coverage audit

The workbook contains 30/30 expected nodes. Every node has an official English
scope and a Sinhala designation. A designation is not a full Sinhala description.
Only five nodes have provisional Sinhala, Tamil, Singlish, and Tanglish enrichment;
none has qualified language approval. The remaining 25 have no enrichment or
romanized example.

| Skill | Official name | Enrichment | Sinhala coverage | Tamil coverage | Romanized coverage | Main confusability boundary | Review still required |
|---|---|---:|---|---|---|---|---|
| APT-DIR | Spatial Orientation & Shadows | No | Designation only | None | None | APT-SPA, APT-VIS, ENV-GEO | Curriculum SME; Sinhala/Tamil language |
| APT-LOG | Logical Deduction & Ordering | No | Designation only | None | None | APT-PAT, APT-REL, APT-WRD | Curriculum SME; Sinhala/Tamil language |
| APT-PAT | Pattern Recognition & Series | No | Designation only | None | None | APT-LOG, APT-VIS, MAT-NUM | Curriculum SME; Sinhala/Tamil language |
| APT-REL | Kinship & Relational Logic | No | Designation only | None | None | APT-LOG, APT-WRD | Curriculum SME; Sinhala/Tamil language |
| APT-SPA | Spatial & 3D Geometry | No | Designation only | None | None | APT-DIR, APT-VIS, MAT-GEO | Curriculum SME; Sinhala/Tamil language |
| APT-VIS | Visual Discrimination & Analogy | No | Designation only | None | None | APT-PAT, APT-SPA, MAT-GEO | Curriculum SME; Sinhala/Tamil language |
| APT-WRD | Verbal Logic & Cryptograms | No | Designation only | None | None | APT-LOG, LAN-VOC | Curriculum SME; Sinhala/Tamil language |
| ENV-AGR | Traditional Agriculture & Implements | No | Designation only | None | None | ENV-BIO, ENV-CIV | Curriculum SME; Sinhala/Tamil language |
| ENV-BIO | Plant & Animal Biology | Yes, provisional | Designation + provisional text | Provisional text | Provisional Singlish/Tanglish | ENV-AGR, ENV-HLT | Curriculum SME; qualified Sinhala/Tamil review |
| ENV-CIV | Civic Heritage, Symbols & Safety | No | Designation only | None | None | ENV-AGR, ENV-GEO, ENV-HLT | Curriculum SME; Sinhala/Tamil language |
| ENV-GEO | Sri Lankan Geography & Map Reading | No | Designation only | None | None | APT-DIR, ENV-CIV | Curriculum SME; Sinhala/Tamil language |
| ENV-HLT | Health, Nutrition & Diseases | Yes, provisional | Designation + provisional text | Provisional text | Provisional Singlish/Tanglish | ENV-BIO, ENV-CIV | Curriculum SME; qualified Sinhala/Tamil review |
| ENV-PHY | Physical Science & Mechanics | No | Designation only | None | None | APT-VIS, MAT-GEO | Curriculum SME; Sinhala/Tamil language |
| LAN-AGR | Subject-Verb Agreement | No | Designation only | None | None | LAN-TNS, LAN-WRT | Language/curriculum SME |
| LAN-BIL | Basic Second Languages | No | Designation only | None | None | LAN-VOC, LAN-CMP | Language/curriculum SME |
| LAN-CMP | Reading Comprehension | No | Designation only | None | None | LAN-IDM, LAN-VOC, LAN-WRT | Language/curriculum SME |
| LAN-IDM | Proverbs & Idiomatic Phrases | No | Designation only | None | None | LAN-CMP, LAN-VOC | Language/curriculum SME |
| LAN-ORT | Orthography & Spelling | No | Designation only | None | None | LAN-VOC, LAN-WRT | Language/curriculum SME |
| LAN-TNS | Tenses & Speech Registers | No | Designation only | None | None | LAN-AGR, LAN-WRT | Language/curriculum SME |
| LAN-VOC | Vocabulary & Word Relations | No | Designation only | None | None | APT-WRD, LAN-BIL, LAN-IDM | Language/curriculum SME |
| LAN-WRT | Creative Structured Writing | No | Designation only | None | None | LAN-AGR, LAN-CMP, LAN-TNS | Language/curriculum SME |
| MAT-DAT | Data Handling & Charts | No | Designation only | None | None | MAT-NUM, MAT-OPS | Curriculum SME; Sinhala/Tamil language |
| MAT-FRC | Fractions & Decimals | Yes, provisional | Designation + provisional text | Provisional text | Provisional Singlish/Tanglish | MAT-NUM, MAT-OPS | Curriculum SME; qualified Sinhala/Tamil review |
| MAT-GEO | Geometric Properties & Symmetry | No | Designation only | None | None | APT-SPA, APT-VIS, MAT-LEN | Curriculum SME; Sinhala/Tamil language |
| MAT-LEN | Length, Perimeter & Distance | No | Designation only | None | None | MAT-GEO, MAT-MAS, MAT-TIM | Curriculum SME; Sinhala/Tamil language |
| MAT-MAS | Mass & Capacity | No | Designation only | None | None | MAT-LEN, MAT-OPS | Curriculum SME; Sinhala/Tamil language |
| MAT-MON | Financial Math & Bills | No | Designation only | None | None | MAT-NUM, MAT-OPS | Curriculum SME; Sinhala/Tamil language |
| MAT-NUM | Number Concept & Place Value | No | Designation only | None | None | APT-PAT, MAT-FRC, MAT-OPS | Curriculum SME; Sinhala/Tamil language |
| MAT-OPS | Fundamental Operations | Yes, provisional | Designation + provisional text | Provisional text | Provisional Singlish/Tanglish | MAT-FRC, MAT-NUM | Curriculum SME; qualified Sinhala/Tamil review |
| MAT-TIM | Time & Calendar Arithmetic | Yes, provisional | Designation + provisional text | Provisional text | Provisional Singlish/Tanglish | MAT-LEN, MAT-OPS | Curriculum SME; qualified Sinhala/Tamil review |

## Qualified language review package

`research/adaptive-tutor/skill-mapper-language-review-v1.csv` contains all 30
nodes. It copies official identity and scope fields from the workbook for reviewer
orientation, includes the five existing provisional enrichments, and leaves the
other proposed-language cells empty instead of inventing translations.

Reviewers should:

1. verify intended meaning against the authoritative scope;
2. correct Sinhala or Tamil wording in the correction fields rather than silently
   overwriting the proposal;
3. review Singlish or Tanglish for plausible child usage and spelling variation;
4. identify ambiguity with neighboring skills;
5. set a disposition only after review and add comments needed to explain a
   correction.

The package contains no reviewer identity or approval claim. `qualified_review_pending`
means a proposal exists but remains unreviewed; `not_drafted` means there is no
proposal to review yet.

## Decision-policy review of the existing benchmark

With enrichment and the relevance gate, raw top-1 retrieval was correct for all
13 skill-labelled cases, while six were confirmed and seven correctly retrieved
skills were abstained. The seven cases were:

| Case | Language/form | Expected skill | Top score | Margin | Blocking gate |
|---|---|---:|---:|---:|---|
| SM-HOLD-001 | English | MAT-OPS | 0.822061 | 0.008085 | Margin |
| SM-HOLD-002 | Sinhala | MAT-OPS | 0.846897 | 0.024589 | Margin |
| SM-HOLD-004 | Singlish | MAT-FRC | 0.823731 | 0.002942 | Margin |
| SM-HOLD-005 | Tanglish | MAT-OPS | 0.856744 | 0.019153 | Margin |
| SM-HOLD-007 | Misspelled English | MAT-TIM | 0.831880 | 0.024423 | Margin |
| SM-HOLD-008 | Symbol-heavy | MAT-OPS | 0.809148 | 0.014282 | Score |
| SM-HOLD-017 | Sinhala | ENV-BIO | 0.816484 | 0.044776 | Score |

A development experiment using a `0.01` margin produced a false confirmation on
generic case SM-HOLD-015 ("Can you help me with this?"): ENV-HLT scored `0.832645`
with a `0.010533` lead. This demonstrates that a smaller margin can increase
coverage while weakening protection against generic utterances. It does not
establish that `0.03` is optimal. The current margin remains unchanged.

Future uncertainty work should use reviewed development/calibration data and may
compare:

- language- and interaction-stratified reliability plots;
- selective-prediction risk/coverage curves;
- bootstrap confidence intervals for precision and coverage;
- calibration methods such as isotonic or logistic calibration only after enough
  representative labels exist;
- separate evidence requirements for generic, short, and contextual utterances;
- score/margin policies evaluated against predefined false-confirmation limits;
- passage-level error analysis and reviewer-approved enrichment for confusable
  skill pairs.

These are experiment candidates, not approved policy changes. Do not tune them on
the already-inspected benchmark, interpret similarity as probability, or add LLM
reranking.

## Next experiment entry criteria

The next experiment can begin after the five current enrichment records receive
qualified Sinhala and Tamil review, missing language material is drafted and
reviewed across all 30 nodes, curriculum boundary labels are reviewed, and a
versioned corpus satisfying the coverage matrix is frozen. Task 11 remains blocked
until the research team defines and meets its integration evidence threshold.
