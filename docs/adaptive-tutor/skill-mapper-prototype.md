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

## Known limitations and future improvements

- Real Sinhala/Tamil and romanized-language quality is not established until evaluation runs.
- The taxonomy contains Sinhala designations but no Tamil designations or multilingual scope text.
- Intent rules are small and mostly English-oriented; they intentionally avoid a large keyword
  engine but will miss multilingual intent nuances.
- Generic English clarification questions are not localized.
- E5 similarities are not calibrated confidence probabilities.
- Taxonomy embeddings are cached only in memory and recomputed per process.
- The XLSX adapter targets the authoritative workbook's current first worksheet and column names.
- Threshold calibration, model comparison, error analysis, and independent expert review remain
  future work.

Task 11 should begin only after real-model evaluation is run and important failures or threshold
problems are reviewed. It must still keep mastery retrieval and Controller V1 integration separate.
