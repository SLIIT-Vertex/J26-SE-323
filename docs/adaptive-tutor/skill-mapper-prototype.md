# Conversational Skill Mapper prototype

## Implemented scope

Task 10 implements a local, evaluable semantic retrieval prototype behind the Task 9 contracts.
It loads the authoritative skill taxonomy, embeds taxonomy passages and learner queries, ranks
skills by cosine similarity, applies conservative conversation/intent handling, and either matches
or abstains.

It does not retrieve mastery, call Controller V1, persist conversations, generate tutoring text,
verify responses, use an LLM API, or integrate with the frontend.

## Selected semantic model

The initial adapter targets [`intfloat/multilingual-e5-small`](https://huggingface.co/intfloat/multilingual-e5-small)
at revision `d829207ab28e6a5fb3aafb5d4c44111b8146db32`. The model card describes 12 layers,
384-dimensional embeddings, multilingual training, and required `query:`/`passage:` prefixes. Its
main weight file is approximately 471 MB. Low-resource language performance may be weaker, so
Sinhala, Tamil, Singlish, and Tanglish behavior must be measured rather than assumed.

The adapter uses `sentence-transformers`, normalized embeddings, and cosine similarity. It is lazy:
constructing or importing the adapter performs no model import, network request, or download.
Sentence Transformers currently recommends Python 3.10+, which is compatible with the backend's
Python 3.11 requirement.

## Architecture

```text
docs/skill_nodes.xlsx
        |
        v
XlsxSkillTaxonomyCatalog -> SkillNode passages
                                |
Learner message -> text preparation -> EmbeddingModel
                                |
                                v
                     SemanticSkillRetriever
                                |
                intent + supplied context handling
                                |
                                v
                    provisional decision policy
                                |
                                v
                     SkillMappingResult
```

- `XlsxSkillTaxonomyCatalog` reads the spreadsheet through Python's standard ZIP/XML support.
- `EmbeddingModel` is the replaceable application boundary used by real and fake embedders.
- `SentenceTransformerE5EmbeddingModel` supplies the optional real E5 implementation.
- `SemanticSkillRetriever` caches taxonomy embeddings and orders ties by `skill_id`.
- `ConversationalSkillMapper` applies intent, context, matching, ambiguity, and abstention rules.

## Taxonomy source

`docs/skill_nodes.xlsx` remains the only maintained taxonomy. The adapter reads its domain tag,
skill ID, English name, Sinhala designation, and description/scope fields. Retrieval passages use
all five fields. Missing names/descriptions and duplicate IDs fail fast. No generated or hardcoded
30-ID copy is stored in application code.

## Setup and local inference

Install the optional inference dependency:

```bash
cd backend
.venv/bin/pip install -e '.[dev,skill-mapper]'
```

The evaluation command is cache-only by default and will report `NOT RUN` instead of downloading:

```bash
cd backend
.venv/bin/python scripts/evaluate_skill_mapper.py
```

Permit the initial Hugging Face model download explicitly:

```bash
cd backend
.venv/bin/python scripts/evaluate_skill_mapper.py --allow-download
```

Later cache-only runs use the same command without `--allow-download`. `--model`, `--revision`,
`--cache-folder`, and `--device` make the backend replaceable and configurable.

## Text, intent, and conversation behavior

Text preparation applies Unicode NFC normalization and whitespace normalization. It does not strip
fractions, operators, numbers, Sinhala, Tamil, or code-mixed content.

Intent handling is deliberately conservative and separate from skill retrieval. Small rules cover
recognized greetings, explicit English hint/example forms, context-dependent follow-ups, and
numeric answer submissions. Other messages default to explanation requests. This is not claimed to
be multilingual intent understanding; future evaluation may justify a learned intent component.

Conversation turns are used only for `FOLLOW_UP_QUESTION`, `ANSWER_SUBMISSION`, and
`ANOTHER_EXAMPLE_REQUEST`. In those cases, recent supplied turns form part of the semantic query
and an active taxonomy skill receives a small provisional bonus. A self-contained new topic uses
only the current message, so stale active context cannot automatically retain the old skill.
Invalid active skills are rejected before retrieval. No session state is stored.

## Scores and provisional policy

Cosine similarities are clamped to the Task 9 contract's `0–1` field and exposed as provisional
retrieval scores, not calibrated probabilities or learner mastery.

Default prototype parameters are:

| Parameter | Default |
| --- | ---: |
| Match score | `0.82` |
| Candidate score | `0.70` |
| Minimum first/second margin | `0.03` |
| Active-skill contextual bonus | `0.02` |

These values are configuration defaults, not scientific findings. The E5 model card warns that
absolute cosine scores cluster high; relative ranking is generally more meaningful. Thresholds
must be tuned on development data separate from the reported evaluation set.

- `MATCHED`: top score meets the match threshold and margin.
- `AMBIGUOUS`: candidate evidence exists, but score or separation is insufficient.
- `NO_MATCH`: a recognized learning-shaped message has insufficient taxonomy evidence.
- `NOT_SKILL_RELATED`: a recognized greeting or low-evidence non-learning interaction.

Only `MATCHED` is eligible for future mastery retrieval. That integration is not implemented.

## Evaluation

`research/adaptive-tutor/skill-mapper-evaluation-v1.json` contains preliminary, manually authored
examples across English, Sinhala, Tamil, Singlish, Tanglish, code-mixed text, misspellings,
ambiguity, unsupported content, greetings, follow-ups, answers, and context changes. Its labels are
design expectations, not validated ground truth.

The optional evaluation command reports:

- exact skill-match accuracy for labeled cases;
- top-k retrieval accuracy;
- status and intent agreement;
- breakdowns by language category;
- observed failure cases.

The command prints results as JSON. If the optional package or cached weights are unavailable, it
prints `REAL MODEL EVALUATION: NOT RUN` semantics and no scores.

### Real-model run: 2026-10-12

The pinned `intfloat/multilingual-e5-small` revision was downloaded and evaluated with
`sentence-transformers` 5.7.0, `transformers` 5.19.0, and `torch` 2.14.1. A subsequent cache-only
run also completed, confirming that evaluation does not require another download.

These 18 cases are preliminary, design-authored examples, not independently validated ground
truth. The sample is too small and unevenly distributed to support research-performance claims or
final threshold selection.

| Metric | Result |
| --- | ---: |
| Examples executed | 18/18 |
| Labeled skill examples | 14 |
| Final confirmed exact matches | 5/14 (35.7%) |
| Raw top-1 retrieval | 11/14 (78.6%) |
| Top-3 retrieval | 11/14 (78.6%) |
| Status agreement | 7/18 (38.9%) |
| Intent agreement | 17/18 (94.4%) |
| False `MATCHED` results | 0 |
| Incorrect abstentions from expected `MATCHED` | 9 |

The mapper emitted 5 `MATCHED`, 12 `AMBIGUOUS`, 0 `NO_MATCH`, and 1
`NOT_SKILL_RELATED` result. Here, "final confirmed exact" requires the decision policy to emit
`MATCHED`; raw top-1 measures retrieval ranking before abstention.

| Case | Language | Expected skill/status | Top retrieval | Top score | Margin | Actual status |
| --- | --- | --- | --- | ---: | ---: | --- |
| 001 | English | MAT-FRC / MATCHED | MAT-FRC | 0.851680 | 0.040710 | MATCHED |
| 002 | Sinhala | MAT-FRC / MATCHED | MAT-FRC | 0.829754 | 0.026979 | AMBIGUOUS |
| 003 | Tamil | MAT-OPS / MATCHED | MAT-NUM | 0.815448 | 0.011161 | AMBIGUOUS |
| 004 | Singlish | MAT-FRC / MATCHED | LAN-AGR | 0.784061 | 0.001422 | AMBIGUOUS |
| 005 | Tanglish | MAT-OPS / MATCHED | APT-VIS | 0.817534 | 0.000605 | AMBIGUOUS |
| 006 | Code-mixed | MAT-FRC / MATCHED | MAT-FRC | 0.824143 | 0.008184 | AMBIGUOUS |
| 007 | English misspelled | MAT-OPS / MATCHED | MAT-OPS | 0.796676 | 0.002898 | AMBIGUOUS |
| 008 | English | MAT-TIM / MATCHED | MAT-TIM | 0.798895 | 0.036010 | AMBIGUOUS |
| 009 | English | AMBIGUOUS | LAN-IDM | 0.810567 | 0.004602 | AMBIGUOUS |
| 010 | English | NO_MATCH | MAT-GEO | 0.832480 | 0.014864 | AMBIGUOUS |
| 011 | Singlish | NOT_SKILL_RELATED | LAN-IDM | 0.775790 | 0.009468 | NOT_SKILL_RELATED |
| 012 | English | NOT_SKILL_RELATED | LAN-AGR | 0.732400 | 0.005506 | AMBIGUOUS |
| 013 | English contextual | MAT-FRC / MATCHED | MAT-FRC | 0.837425 | 0.031107 | MATCHED |
| 014 | Symbolic contextual | MAT-FRC / MATCHED | MAT-FRC | 0.850412 | 0.040792 | MATCHED |
| 015 | English contextual | MAT-FRC / MATCHED | MAT-FRC | 0.823978 | 0.037516 | MATCHED |
| 016 | English context change | MAT-TIM / MATCHED | MAT-TIM | 0.845900 | 0.033756 | MATCHED |
| 017 | English | ENV-BIO / MATCHED | ENV-BIO | 0.811470 | 0.021221 | AMBIGUOUS |
| 018 | Sinhala | ENV-HLT / MATCHED | ENV-HLT | 0.792460 | 0.024516 | AMBIGUOUS |

Language-category results are descriptive only because most categories contain one or two labeled
examples:

| Category | Final exact | Top-3 | Status agreement |
| --- | ---: | ---: | ---: |
| English | 1/3 | 3/3 | 2/6 |
| Sinhala | 0/2 | 2/2 | 0/2 |
| Tamil | 0/1 | 0/1 | 0/1 |
| Singlish | 0/1 | 0/1 | 1/2 |
| Tanglish | 0/1 | 0/1 | 0/1 |
| Code-mixed | 0/1 | 1/1 | 0/1 |
| English misspelled | 0/1 | 1/1 | 0/1 |
| English contextual | 2/2 | 2/2 | 2/2 |
| English context change | 1/1 | 1/1 | 1/1 |
| Symbolic contextual | 1/1 | 1/1 | 1/1 |

The current `0.82` match threshold and `0.03` margin avoided false confirmed matches in this set,
but rejected six cases whose correct skill was ranked first. The `0.70` candidate threshold made
almost every non-greeting input a candidate and produced no `NO_MATCH`, including algebra outside
the taxonomy and an off-topic cricket question. Lowering the match threshold alone would be unsafe:
the unsupported algebra example scored 0.832480, while several valid examples scored below it.
The margin helps prevent confident decisions for incorrectly ranked Tamil, Singlish, and Tanglish
examples, but is slightly too strict for the Sinhala fraction example at a 0.026979 margin. These
parameters therefore remain unvalidated and should not be tuned on these same 18 examples.

## Task 10.2 focused multilingual experiment

Task 10.2 preserves the original 18-example file as a frozen diagnostic baseline and adds two
disjoint, frozen datasets:

- `skill-mapper-development-v1.json`: 20 design-authored cases on which calibration is allowed.
- `skill-mapper-held-out-v1.json`: 18 design-authored cases on which calibration is prohibited.
  It has now been inspected and is an existing benchmark, not a fresh untouched final test set.

Both files state that they are not independently validated ground truth. No qualified Sinhala or
Tamil reviewer has reviewed them; the language review status is explicitly `not_reviewed`.

### Optional enrichment

`skill-mapper-enrichment-v1.json` contains additional retrieval passages for five existing IDs:
`MAT-FRC`, `MAT-OPS`, `MAT-TIM`, `ENV-HLT`, and `ENV-BIO`. It does not define skill identity or
modify `docs/skill_nodes.xlsx`. Each entry records its language, provenance, and review status.
English entries are derived from the authoritative scope. Sinhala, Tamil, Singlish, and Tanglish
entries are design-authored provisional variants with qualified review pending.

When enabled, the retriever embeds the authoritative passage and each enrichment independently,
then uses the maximum similarity for that skill. This avoids diluting a short multilingual alias
inside one large mixed-language passage. Unknown IDs, duplicate records, duplicate entries, blank
text, and missing provenance/review status are rejected. Omitting enrichment retains the Task 10
behavior.

### Optional relevance gate

`skill-mapper-relevance-v1.json` contains seven small semantic counter-examples: four unsupported
academic examples and three off-topic examples. The optional gate embeds them with the same pinned
E5 model and compares their best score with the best supported-skill score. A winning unsupported
example produces `NO_MATCH`; a winning off-topic example produces `NOT_SKILL_RELATED`. This is a
two-sided semantic comparison rather than a large keyword engine or a second model.

Relevance alone is not reliable: without enrichment, weak supported-language representations can
let a negative example win for a valid message. The combined configuration is therefore the only
improved configuration considered for further research evaluation.

### Real-model A-D comparison

All runs used the pinned model revision and the original `0.82` match, `0.70` candidate, and `0.03`
margin settings. `Exact` means a correct final `MATCHED` result, not merely top-1 retrieval.

Development split:

| Configuration | Exact | Top-1 | Top-3 | False matches | Incorrect abstentions | Status | Intent |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A: baseline | 1/15 | 9/15 | 11/15 | 0 | 14 | 3/20 | 19/20 |
| B: enrichment only | 6/15 | 14/15 | 15/15 | 0 | 9 | 8/20 | 19/20 |
| C: relevance only | 1/15 | 9/15 | 11/15 | 0 | 14 | 5/20 | 19/20 |
| D: combined conservative | 6/15 | 14/15 | 15/15 | 0 | 9 | 11/20 | 20/20 |

Held-out split:

| Configuration | Exact | Top-1 | Top-3 | False matches | Incorrect abstentions | Status | Intent |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A: baseline | 2/13 | 7/13 | 11/13 | 0 | 11 | 4/18 | 17/18 |
| B: enrichment only | 6/13 | 13/13 | 13/13 | 0 | 7 | 8/18 | 17/18 |
| C: relevance only | 2/13 | 7/13 | 11/13 | 0 | 11 | 6/18 | 17/18 |
| D: combined conservative | 6/13 | 13/13 | 13/13 | 0 | 7 | 11/18 | 18/18 |

On the frozen original 18-example diagnostic baseline, configuration D improved final exact matches
from 5/14 to 9/14, raw top-1 from 11/14 to 13/14, top-3 from 11/14 to 14/14, status agreement from
7/18 to 13/18, and intent agreement from 17/18 to 18/18, with zero false confirmed matches in both
runs.

Configuration D correctly handled all held-out greeting, off-topic, unsupported trigonometry, and
unsupported chemistry cases. Its held-out language results remain small-sample observations:

| Category | Final exact | Top-3 | Status agreement |
| --- | ---: | ---: | ---: |
| English | 1/2 | 2/2 | 5/6 |
| Sinhala | 0/2 | 2/2 | 0/2 |
| Tamil | 1/1 | 1/1 | 2/2 including greeting |
| Singlish | 0/1 | 1/1 | 0/1 |
| Tanglish | 0/1 | 1/1 | 0/1 |
| Code-mixed | 1/1 | 1/1 | 1/1 |
| English misspelled | 0/1 | 1/1 | 0/1 |
| Symbolic | 0/1 | 1/1 | 0/1 |
| English contextual | 1/1 | 1/1 | 1/1 |
| English context change | 1/1 | 1/1 | 1/1 |
| Symbolic contextual | 1/1 | 1/1 | 1/1 |

### Threshold calibration outcome

A development-only `0.01` margin increased development exact matches to 12/15 with zero false
matches. When the then-unseen held-out split was first inspected, however, it falsely confirmed the generic request
"Can you help me with this?" as `ENV-HLT` at 0.832645 with a 0.010533 margin. The calibration is
therefore rejected. The conservative `0.03` margin remains unchanged. This preserves zero false
confirmed matches but leaves seven held-out incorrect abstentions.

All seven conservative held-out failures ranked the expected skill first but abstained:

| Case | Language | Skill | Score | Margin | Blocking condition |
| --- | --- | --- | ---: | ---: | --- |
| SM-HOLD-001 | English | MAT-OPS | 0.822061 | 0.008085 | margin |
| SM-HOLD-002 | Sinhala | MAT-OPS | 0.846897 | 0.024589 | margin |
| SM-HOLD-004 | Singlish | MAT-FRC | 0.823731 | 0.002942 | margin |
| SM-HOLD-005 | Tanglish | MAT-OPS | 0.856744 | 0.019153 | margin |
| SM-HOLD-007 | English misspelled | MAT-TIM | 0.831880 | 0.024423 | margin |
| SM-HOLD-008 | Symbolic | MAT-OPS | 0.809148 | 0.014282 | score |
| SM-HOLD-017 | Sinhala | ENV-BIO | 0.816484 | 0.044776 | score |

The evaluator accepts `--enrichment`, `--relevance`, `--configuration`, and
`--relevance-minimum-advantage` and reports relevance scores, per-case retrieval scores, expected
skill ranks, false matches, and incorrect abstentions. For example:

```bash
cd backend
.venv/bin/python scripts/evaluate_skill_mapper.py \
  --dataset ../research/adaptive-tutor/skill-mapper-held-out-v1.json \
  --enrichment ../research/adaptive-tutor/skill-mapper-enrichment-v1.json \
  --relevance ../research/adaptive-tutor/skill-mapper-relevance-v1.json \
  --configuration D-combined-conservative
```

## Known limitations and future improvements

- Enrichment improved held-out top-3 retrieval to 13/13, but conservative confirmed-match coverage
  remains only 6/13.
- Sinhala, Singlish, and Tanglish held-out skills ranked correctly but were abstained; qualified
  review and broader natural-language coverage are still missing.
- Only one skill-labeled Tamil and one Singlish/Tanglish example occur in the held-out split, so no
  language-quality conclusion is justified.
- Provisional translations and romanizations must not be promoted to production taxonomy data
  without qualified Sinhala/Tamil review.
- The relevance counter-example set is tiny, English-only, and design-authored. Broader unsupported
  and off-topic cases may behave differently.
- Short follow-ups and context changes passed, but the sample remains too small to establish
  robustness or rule out stale active-skill bias.
- Generic English clarification questions are not localized.
- E5 similarities are not calibrated confidence probabilities.
- Taxonomy embeddings are cached only in memory and recomputed per process.
- The XLSX adapter targets the authoritative workbook's current first worksheet and column names.
- Independent expert review and a larger separately sourced evaluation set remain necessary.

Task 11 integration is not advised yet because qualified language review is missing and the
held-out evidence is both small and insufficient for conservative confirmed-match coverage.

Task 10.3 evaluation rules, the complete taxonomy coverage audit, and the distinction between
design-authored, human-reviewed, and independently sourced evidence are defined in
`docs/adaptive-tutor/skill-mapper-evaluation-protocol-v2.md`. The corresponding 30-skill reviewer
worksheet is `research/adaptive-tutor/skill-mapper-language-review-v1.csv`; it records proposals as
pending and does not claim that qualified review has occurred.
