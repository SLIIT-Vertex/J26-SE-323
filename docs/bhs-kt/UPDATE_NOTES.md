# UPDATE NOTES — grading redesign (2026-10-11)

This update changes how **every generated paper is graded**. It comes from the grading experiment recorded in `09_GRADING_TEST_FINDINGS.md`. If you already built from the older docs, read this file first, then the changed files listed below.

## 1. The change in one paragraph

The vision model **reads** what the child wrote or marked, **without ever seeing the answer key** (blind reading). Our own code **compares** the reading with the key. One vision call is made per question block (the whole cropped question, including handwriting). Photos are aligned with ArUco markers + QR first, and with SIFT feature registration against the rendered PDF page when markers are missing. Anything uncertain goes to the parent for confirmation. Failures (quota, withdrawn model, bad JSON, wrong page) produce clear statuses, never silent wrong grades.

## 2. Files changed

| File | Status | What changed |
|---|---|---|
| `05_GRADING_PIPELINE.md` | **rewritten (v2)** | Six rules; alignment A (ArUco+QR) and B (SIFT+RANSAC); block crops; `PartSpec/PartRead/ItemRead`; blind prompt `item-blind-v2`; comparison rule table; combining parts; statuses; second opinion; operations (retries, quota, model switch, caching); parent confirmation; benchmark; offline tests. |
| `09_GRADING_TEST_FINDINGS.md` | **new** | Map from the test harness to production modules; teacher file formats and answer-key syntax; data problems found; registration results; provider findings; how to go from the harness to "grade every paper"; acceptance; open items. |
| `00_README.md` | patched | Stack row, doc map, rule 3, glossary (Part), decisions D5, D9 (two-skill questions), D10 (reading unit). |
| `01_ARCHITECTURE.md` | patched | Grading module layout, flow 2.2, pure modules, `.env` additions, error handling, background work. |
| `02_DATABASE.md` | patched | `secondary_skill_codes`, `answer_key_raw`, `answer_kind`, `instruction`, `answer_space_in_image`; relaxed short-part constraint; optional `answer_boxes`; alignment method; `graded_answers.match_how / instruction_met / second_opinion`; new `vision_calls` table; answer-key syntax; importer reads teacher text files; forbidden client fields now include `instruction` and `answer_key_raw`. |
| `04_PAPER_GENERATOR.md` | patched | Answer boxes are only drawn when `answer_space_in_image = false`; grading uses the whole block; extra whitespace test. |
| `06_API_SPEC.md` | patched | Forbidden fields, `low_match` failure reason, review reasons, block crops, instruction-part yes/no, `/health` warnings. |
| `08_IMPLEMENTATION_ORDER.md` | patched | Steps 1, 7, 8, 9, 10 and the owner's task list updated. |
| `reference/grading_test_harness/` | **new** | The working test harness (code, tests, the real test data). Read and port from it; do not ship it as the product. |
| `03`, `07`, `shared/`, `reference/mindbridge_dkt_v2_1.py` | unchanged | |

## 3. Things the IDE must not get wrong

1. The key (accepted answers, correct option, instruction text) is **never** put in a prompt, log or client response. Add the tests described in `02` and `08` Step 8.
2. Do not build a "new ink" pixel-difference detector. It was tried and failed on real photos (`09` section 3).
3. Crops must extend to the right edge of the frame and use only small vertical padding; otherwise children's answers are cut off or neighbouring questions are pulled in.
4. Compare in code: choice equivalence (`i/ii/iii` = `1/2/3`), number-in-text (`6 ක් වැඩිය` accepts key `6`), alternatives with `/`, near-miss → parent review.
5. Model names live in `.env`. A withdrawn model (HTTP 404) switches automatically and shows a warning; a hard daily quota stops quickly and shows a warning.
6. Free API tiers are for development only. Production needs a paid key and a check of the provider's data-use terms before children's photos are sent.

## 4. Prompt to give the IDE

Copy everything between the lines.

---

You are working on the MindBridge backend. Read, in this order: `00_README.md`, `01_ARCHITECTURE.md`, `UPDATE_NOTES.md`, `05_GRADING_PIPELINE.md`, `09_GRADING_TEST_FINDINGS.md`, then `02_DATABASE.md`, `04_PAPER_GENERATOR.md`, `06_API_SPEC.md` and `08_IMPLEMENTATION_ORDER.md`.

The grading design changed (see `UPDATE_NOTES.md`). A working test harness is in `reference/grading_test_harness/`; port its answer-key parser, comparison rules, file loaders, page registration and provider code into the modules named in `09` section 1, and copy its tests.

If the project already exists, do this in order and stop after each item until its tests pass:

1. Migrations for the schema changes in `02` (new columns, `vision_calls`), and the importer for the teacher text files and key syntax with cross-file checks.
2. Paper generator changes from `04` (answer boxes optional; `answer_space_in_image`).
3. `alignment.py` method B and block crops (`05` sections 1–2).
4. `rules_compare.py`, `combine_parts()` and the vision interface with the mock provider.
5. `GeminiProvider` and the OpenAI-compatible provider with the blind prompt, retries, quota handling, model auto-switch, caching and `vision_calls` logging.
6. Submissions API changes from `06`, parent review of block crops, instruction-part yes/no.
7. A benchmark script that runs the labelled photos through the production pipeline and prints agreement, share sent to the parent, latency and cost.

Do not change the DKT model service. Never put the answer key in any prompt, log or client response. Ask me for anything marked USER INPUT in `08`; do not invent data.

---

## 5. Open items for the owner

- Consented, labelled photos for the real benchmark (the one-paper experiment is indicative only).
- Choose the second-opinion provider, and whether the doubled cost is acceptable.
- Decide D9 (questions with two skills) with the team that owns the skill model.
- Fix the data problems listed in `09` section 2.
- Create a paid key for the chosen provider and read its data-use terms.
- `reference/grading_test_harness/data/photos/` holds photos of a child's handwriting from the test. Remove them before sharing the repository outside the team.
