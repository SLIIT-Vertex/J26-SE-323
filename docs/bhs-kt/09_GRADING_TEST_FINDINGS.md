# 09 — Grading test harness: what was built, what was learned, how to grade every generated paper

This file records the grading experiment that decided the design in `05`. It also explains how to move from "test harness on one paper" to "grade every paper the system generates".

**Honest scope:** the experiment used **one generated test paper (4 pages, 17 questions) answered by one child**, photographed with a phone. It shows which design works and which fails; it is **not** a benchmark. Do not quote accuracy numbers from it in the research report. The real benchmark is in `05` section 11.

## 1. What the harness is

Folder `reference/grading_test_harness/` (run it, read it, port from it; do not ship it as the product).

```
run.py                    commands: check | prepare | grade | report | all | models | layout
gradetest/answer_key.py   key parser + comparison rules  ──►  port to services/grading/rules_compare.py
gradetest/meta.py         skill / difficulty / time file loaders  ──►  port to the question importer
gradetest/locator.py      PDF layout, photo→page registration (SIFT), crops  ──►  alignment method B + crops
gradetest/prompts.py      blind / keyed prompts      ──►  vision/prompts/item_blind_v2.txt
gradetest/providers/      groq, gemini, openrouter, openai, custom, mock  ──►  vision/*
gradetest/grader.py       run loop, JSON parsing, per-part scoring  ──►  grading/pipeline.py
gradetest/report.py       side-by-side HTML report + labels export  ──►  keep as a dev tool
tests/test_answer_key.py  parser / comparison tests  ──►  copy into the backend tests
data/                     the real inputs of the experiment (paper.pdf, 4 photos, answer / skill / difficulty files)
```

Commands used in the experiment (also in the harness README):

```
python run.py check                      # parse answers / skills / difficulty
python run.py prepare                    # align photos to the PDF, write crops + overlays
python run.py grade --providers gemini --modes blind --ref --open
python run.py grade --providers gemini --all-models --modes blind    # try every Gemini model the key can use
python run.py grade --providers groq --efforts none high --modes blind keyed --strict
```

## 2. The teacher's data files (formats the importer must read)

The question bank owner maintains plain-text files; the importer (`02` section 2) must accept them directly.

| File | Line format | Notes |
|---|---|---|
| `answers_<n>.txt` | `4.48 -i.වාහන, ii. සෙල්ලම්` | id, dash, answer key in the syntax below. Lines may end with `\r\n` and trailing spaces. |
| `skillMap-<n>.txt` | `1.1 - APT-VIS` (set 1) or `4.1 APT-VIS` (set 4) | dash is optional. A question may list **two** skills: `4.20 LAN-CMP, LAN-ORT`. |
| `difficult-time-<n>.txt` | one long line: `1.1 - APT-VIS: Easy \| 1.0 min   1.2 - APT-PAT: Medium \| 1.5 mins …` | entries separated by spaces; `min`/`mins`; two skills give `Hard / Medium \| 3.0 / 1.5 mins`. |

**Answer-key syntax** (canonical; implemented and tested in `answer_key.py`):

| Written | Meaning |
|---|---|
| `a, b, c` | three **parts** (three separate answers on one image) |
| `ans1/ans2` | alternatives for one part (either is accepted) |
| `i.වාහන, ii. සෙල්ලම්` | optional labels `i.`/`ii.` in front of parts |
| `80,004` | a comma inside a number (digit, comma, exactly three digits, no space) does **not** split |
| `1000, 90` | comma followed by a space does split |
| `1/2` | slash between digits does **not** split (fraction) |
| `"color three boxes"` | straight double quotes = **instruction to the grader**; the part has no text answer |
| `12 "also check the unit"` | answer and instruction together |
| `“…”` (curly quotes) | ordinary answer text |
| `\,` | literal comma inside one answer |
| `Ⅳ`, `(iii)`, Sinhala digits, ZWJ | normalised before comparing |

Part kind is inferred: `choice` if every alternative is one of `1 2 3 4 i ii iii iv`; `number` if numeric; `instruction` if only a quoted instruction; otherwise `text`. For a `choice` part the importer fills `option_labels` from the key's spelling (`1/2/3` or `i/ii/iii`, plus `4`/`iv` when the key needs it) unless the CSV overrides it.

**Data problems found in the real files** (the importer must report these, never silently accept):

- Questions present in the answer files but missing from the skill/difficulty files (`1.39`, `4.8` in the test data).
- A question with two skills (`4.20`): see decision D9 in `00`.
- The PDF label `4.54` was printed on the question whose key is `4.50` (an ID typo); `4,62` had a comma. The harness has `data/id_fixes.json` for this. In the product the paper generator prints no ID text; ids come from `paper_items`, so this class of error disappears.
- Two ids (`4.61`, `1.62`) sat on one image: the bank image contained two questions. Split such images in the bank (one image = one question).

## 3. How photos are located without a QR code

The test paper had no QR and no markers. Method used (this became alignment method B in `05`):

1. Read from the PDF where each question image sits on the page (image object boxes; the small blue id label in the left margin tells which question it is). In production this information is `paper_items` (page and block box), so no label is needed.
2. Render each PDF page; compute SIFT features for the photo and for each page; match; RANSAC homography; take the page with the most inliers.
3. Warp the photo onto the page; cut one crop per block.

Result on the 4 photos (photo order differed from page order): correct page 199, 218, 226, 274 inliers; every wrong page < 20. Overlays showed the boxes sitting on the right questions, even with creased paper and a dark background. Two crop bugs were found and fixed: the crop must extend to the **right page edge** (answers were written beyond the dotted line) and padding must be small (large padding pulls in neighbouring questions).

A pixel-difference "new ink" detector (photo vs blank render) was tried to detect unanswered questions and **did not work**: faint pencil was missed (a real "3100" scored zero) and leftover printed lines were flagged as marks. Do not build it.

## 4. Vision provider findings (single paper, indicative only)

| Finding | Evidence in the experiment | Consequence in `05` |
|---|---|---|
| Showing the key makes the model confirm instead of read | In keyed mode Groq said "the child circled (ii)" for a question with no mark, and accepted "rabite" for RABBIT. A stricter prompt fixed the spelling case, not the invented circle. In blind mode the same question was reported blank. | Rule 1: blind reading only |
| Reading errors are partly model-specific | Per the owner's review, Gemini and Groq each made a few mistakes and they were on **different** questions | Optional second opinion (`05` section 8) |
| Answers contain extra words | A child wrote "6 ක් වැඩිය" ("6 more") for key `6`; code compared strictly and marked it wrong although the reading was right | Number-in-text rule |
| Groq has one vision model | Docs list a single vision model (`qwen/qwen3.8-27b`), thinking can be tuned (`reasoning_effort`) | Keep model names in config |
| Free tiers are small | Groq: 200 000 tokens/day per organisation (exhausted during repeated test runs, the later ones with thinking on and a second image); Gemini: per-model daily request caps (a run stopped with HTTP 429 after ~17 calls); a default Gemini model was withdrawn (HTTP 404) | Paid key for production; fail-fast on hard quota; configurable model |
| Server overload happens | Gemini returned HTTP 503 several times (retry worked) | Retry with back-off |
| Latency | Groq ≈ 7–20 s per call (once ≈ 60 s); Gemini ≈ 4–25 s (once 78 s) | Background grading, concurrency 3–4 |
| Cost | Groq used 1 200–2 800 input tokens per question; OpenAI small models estimated US$ 0.001–0.005 per question | Log tokens in `vision_calls` |

The harness `models` command lists the model ids a key can use (`python run.py models gemini|groq`).

## 5. From the harness to "grade every generated paper"

The test paper was generated by the paper generator but graded by a separate script. To grade all papers, do this (it is also the content of Steps 7–10 in `08`):

1. **Persist what the harness read from the PDF.** The generator already stores `paper_items` (page, `block_*`). Add nothing new; the harness's "layout.json" is exactly `paper_items` for that paper.
2. **Question bank carries the key in the harness syntax.** `questions` + `question_parts` store parts, alternatives and instructions (`02`). The importer parses `answers_*.txt`, skill maps and difficulty/time files.
3. **Grading service = harness pipeline minus the report.** `grade_submission(submission_id)`:
   align (A then B) → crop blocks → `read_item` per block (blind) → `compare` per part → `combine_parts` → save → flag for the parent.
4. **Parent review screen** shows the block crop and the machine reading (no key).
5. **Attempts + mastery** exactly as before (`source = 0`, penalty `0.08`).
6. **Monitoring:** `vision_calls` table (provider, model, prompt version, latency, tokens, error) → a small admin report: share of items needing review, average latency, cost per paper, errors by provider. Quota or model-withdrawn errors must be visible to the owner.
7. **Keep the harness** for model comparisons: when a new vision model appears, run `run.py grade` on a labelled set and compare agreement before changing `VISION_PROVIDER`.

## 6. Acceptance for "paper grading works for all papers"

- Every generated paper (any child, any selection of questions) can be photographed page by page and graded without a QR-less manual step.
- On the labelled benchmark set the targets of `05` section 11 are met, and the share of questions sent to the parent is reported (high but honest is better than low and wrong).
- The key never appears in any prompt, log line, response or client payload (tests: the forbidden-field test in `02`, plus a test that fails if any prompt string contains an accepted answer).
- A quota failure, a withdrawn model, an invalid JSON reply and a wrong-page photo each produce a clear status, never a silently wrong grade.

## 7. Open items

- Real benchmark with consented children's photos and a human-labelled `labels.csv` (owner).
- Decide the second-opinion provider and whether to pay for it (cost doubles).
- Decide D9 (two-skill questions) with the team that owns the skill model.
- Check the data-use terms of the chosen paid provider before pilot use with real children.
