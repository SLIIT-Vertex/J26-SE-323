# 05 — Paper grading pipeline (v2)

> **v2 replaces the earlier draft.** It is based on a working test harness (`reference/grading_test_harness/`, explained in `09_GRADING_TEST_FINDINGS.md`) that graded real phone photos of a generated paper with Gemini and Groq. Where this file and the harness disagree, this file is the specification and the harness is the working example.

Goal: from a phone photo of one answered page, produce for every question on that page one of `correct`, `wrong`, `blank`, or "needs the parent to confirm". Reading handwriting and marks is delegated to an **external vision model** (not the research contribution). Every grading decision is plain, tested code, so results are explainable.

## 0. The six rules that came out of testing (do not change without re-running the benchmark)

1. **The vision model never sees the answer key ("blind reading").** When we tested a "keyed" mode (model gets the key and judges), the model invented a circled option on a question the child had not answered, and accepted the misspelling "rabite" as RABBIT. A prompt that says "do not assume" reduced but did not remove this. So: the model only *reports what is written or marked*; our code compares with the key.
2. **One vision call per question block** (the whole question image as it appears on the page, including the child's writing), not one call per answer box. The call lists how many parts the question has and their type/labels, and returns one reading per part.
3. **Read letter by letter, never auto-correct.** Children misspell; the prompt forbids "fixing" words.
4. **Only the child's pen/pencil marks count.** Printed lines, pictures and option labels are not answers; no mark = `blank`.
5. **Uncertainty goes to the parent, never to "wrong".** Low confidence, near-miss, disagreement between two models, instruction parts, vision errors → `needs_review`.
6. **Crops must reach the right page edge.** Children write past the dotted line; a crop that stops at the printed image width cuts the answer off.

## 1. Pipeline for one submission

1. **Store the original** (private storage) and create a `paper_submissions` row (`uploaded`).
2. **Load and orient:** EXIF rotation (`PIL.ImageOps.exif_transpose`), convert to RGB, downscale so the longest side ≤ 3000 px.
3. **Identify paper and page.** Primary: QR `MB1:<token>:<page>` (see `04`). Check token ↔ paper and page ↔ the page the client says; otherwise `failed_alignment` (`wrong_paper` / `wrong_page`).
4. **Align to the canonical page** with one of two methods (record which in `alignment_info.method`):
   - **A. Markers (primary):** 4 ArUco markers → homography to the canonical frame image (1000 × 1473 px for the 184 × 271 mm frame). CLAHE retry; still missing → try method B before failing.
   - **B. Feature registration (fallback, proven on real photos):** render the stored PDF page to an image (2 px per PDF point), compute SIFT features for the photo and each page of that paper, match (ratio test 0.78), `cv2.findHomography(RANSAC, 6 px)`. Take the page with most inliers. **Accept only if inliers ≥ 25.** In the test, the correct page had 199–274 inliers and wrong pages had fewer than 20, so the margin is large; also require best ≥ 3 × second best. Method B needs no markers or QR, and it also finds the page number by itself. If it also fails → `failed_alignment` with reason `markers_missing`/`low_match` and ask the parent to retake the photo. Never guess.
   - After either method, record `blur_score` (variance of Laplacian); below threshold → `failed_alignment`/`blurry`.
5. **Crop each paper item** (whole block, section 2). Keep the **blank crop** of the same area (rendered from the stored PDF) for the optional reference image.
6. **Read** each item with the `VisionProvider` (sections 3–4). Calls run concurrently (limit 3–4 at a time), each with timeout and retries (section 9).
7. **Compare** each part with the key using the rules in section 5, then combine parts (section 6).
8. **Optional second opinion** (section 8) when `VISION_SECOND_PROVIDER` is set.
9. Save `graded_answers` (one row per part) and one `vision_calls` row per call. Submission → `graded` or `needs_review`.
10. After the parent confirms flagged parts (section 10) create `attempts` and recompute mastery.

Steps 2–5 are deterministic and need no network.

## 2. Cropping (step 5 in detail)

- Block rectangle = the stored `block_*` fractions (frame fractions) converted to the canonical image. Pad **8 pt above and 10 pt below** (the paper and the homography are never perfect), and **extend to the right edge of the page**. Left edge: just after the question-number column (never include margin labels).
- The crop is saved as `crop_key`; keep it only as long as the retention policy in `00` allows.
- If two paper items share one bank image (the test paper had one image carrying two question ids), they share one crop; the prompt names which question is meant. Prefer fixing the bank so one image = one question.

## 3. Vision provider interface (`vision/base.py`)

```python
class PartSpec(BaseModel):          # what the model is told about each part — NEVER the answer
    index: int                      # 1-based, order in the answer key
    label: str | None               # e.g. "i", "ii" if the key has labels
    kind: Literal["choice", "number", "text", "instruction"]
    option_labels: list[str] | None # choice parts: e.g. ["1","2","3"] or ["i","ii","iii"]
    instruction: str | None         # grader instruction text from the key, e.g. "color three boxes"

class PartRead(BaseModel):
    part: int
    answer: str = ""                # exactly what the child wrote; choice parts: the option label as printed
    blank: bool = False
    confidence: float = 0.0         # 0..1
    instruction_met: bool | None = None   # only when the part has an instruction
    notes: str = ""

class ItemRead(BaseModel):
    parts: list[PartRead]
    notes: str = ""

class VisionProvider(Protocol):
    name: str; model: str; prompt_version: str
    def read_item(self, crop: bytes, parts: list[PartSpec], language: str,
                  blank_reference: bytes | None = None) -> tuple[ItemRead, CallInfo]: ...

class CallInfo(BaseModel):
    latency_ms: int; tokens_in: int | None; tokens_out: int | None; raw_text: str
```

Implementations: `MockProvider` (scripted; all unit tests), `GeminiProvider`, `OpenAICompatProvider` (Groq, OpenRouter, OpenAI, Mistral, GitHub Models …; see the harness `providers/`). Select with `VISION_PROVIDER`. Ask for JSON output (`responseMimeType: application/json` for Gemini, `response_format: json_object` where supported), validate with Pydantic, strip code fences and `<think>` blocks, retry once on invalid JSON, then raise `VisionError` (→ `needs_review`).

If the model returns a different number of parts than asked, flag every part of that item `needs_review` (`part_count_mismatch`).

## 4. Prompt `item-blind-v2` (keep in `vision/prompts/item_blind_v2.txt`)

```
You are checking a Sri Lankan Grade 5 scholarship practice paper that a child answered by hand and a parent
photographed. The image shows ONE question (printed text and pictures in black, the child's pencil / pen writing
or marks on top). Handwriting may be Sinhala, English letters, digits or Roman numerals. Ignore any partial lines
of neighbouring questions at the very top or bottom edge of the image.
{if blank_reference: A SECOND image is provided: it is the same question BLANK, as printed. Use it only to tell
printed content from the child's additions. The FIRST image is the child's answered version.}

This question has {n} answer part(s):
- Part 1 (labelled 'i.').  [Extra instruction: "…".]
- Part 2 …

Task: transcribe the child's answer for every part.
Rules:
- Transcribe exactly what the child wrote; do NOT solve the question and do NOT correct spelling.
- For a multiple-choice part, report the option label the child circled / ticked / underlined / wrote
  (e.g. "ii" or "2", exactly as printed beside the option).
- If a part has nothing written or marked, set "blank": true and leave the text empty.
- Write numbers with digits (Sinhala digits -> 0-9). Keep units and extra words the child wrote
  (e.g. "31 kg 400 g", "6 more").
- Read word answers LETTER BY LETTER exactly as written. Children misspell: keep wrong, missing or extra
  letters (e.g. "rabite", not "rabbit"). Never auto-correct and never guess what they "meant".
- Only pencil / pen marks made by the child count as an answer. Printed pictures, lines and option labels do not.
  If a part has no such mark, it is blank.
- If you really cannot read it, give your best guess and lower "confidence" (0 to 1).
{if any instruction: For a part with an "Extra instruction", ALSO set "instruction_met" to true/false by looking
at the image (answer then describes what you see).}
Return ONLY JSON, one entry per part, in this shape:
{"parts":[{"part":1,"answer":"<what the child wrote/marked>","blank":false,"confidence":0.9
 {,"instruction_met":true|false|null}}],"notes":"<short, optional>"}
```

The exact text is generated by `blind_prompt()` in `reference/grading_test_harness/gradetest/prompts.py`; port it unchanged, then change it only through a new `prompt_version` and a benchmark run.

**Never** put `accepted_answers`, `correct_option` or any hint of the correct answer into the prompt (an instruction text such as "color three boxes" is allowed because it is an instruction to *look*, not an answer; keep instruction texts free of the expected result where possible, e.g. "check the boxes are coloured").

## 5. Comparison rules (`rules_compare.py`, pure, fully tested)

Port `compare()` and `norm()` from `reference/grading_test_harness/gradetest/answer_key.py` and its tests (`tests/test_answer_key.py`).

Normalisation (`norm`) applied to both the key and the child's reading:
NFKC (this turns Unicode Roman numerals `Ⅳ` into `IV`), remove zero-width characters (U+200B/C/D, U+2060, U+FEFF), Sinhala digits → ASCII, casefold, remove thousand separators (`80,004` → `80004`), collapse whitespace, strip surrounding punctuation and quotes, unwrap one pair of brackets (`(iii)` → `iii`).

Decision per part, in this order:

| # | Condition | Result |
|---|---|---|
| 1 | `blank` or empty after normalisation | `blank` |
| 2 | `norm(answer)` equals `norm(alt)` for any alternative | `correct` (how = `exact`) |
| 3 | Choice equivalence: key and answer both in {`1`,`2`,`3`} ∪ {`i`,`ii`,`iii`} and map to the same number | `correct` (`choice-equivalent`) |
| 4 | Part kind is `number`, the key is a plain number, and the answer contains **exactly one** number equal to the key (so `6 more`, `6 ක් වැඩිය` pass; `16 more`, `6 and 3` do not) | `correct` (`number found in text`) |
| 5 | Equal after removing all spaces and punctuation | `correct` (`loose`) |
| 6 | Text key without digits, length ≥ 4, similarity ratio ≥ 0.85 to an alternative | `wrong` + flag `needs_review`, reason `near_miss` |
| 7 | Otherwise | `wrong` |

- Alternatives (`ans1/ans2`) are tried one by one; the part is correct if any matches.
- A **multi-label answer** from a choice part (e.g. `ii+iii`, two options) → `ambiguous` (flag).
- **Instruction parts** (key has `"…"`): no text comparison for instruction-only parts; the model's `instruction_met` decides (`true` → `correct`, `false` → `wrong`) **and the part is always flagged `needs_review` unless confidence ≥ `VISION_CONFIDENCE_MIN` and a second model agrees**. If the part has both text and an instruction, both must pass.
- Low confidence (`< VISION_CONFIDENCE_MIN`) on a part whose result would be `correct` or `wrong` → keep the result but flag `needs_review` (`low_confidence`).

Tests to write: all of the cases above, plus Sinhala strings with and without ZWJ, Sinhala digits, `Ⅳ` vs `IV`, `(ii)` vs `2`, `31kg 400g` vs `31 kg 400 g` (correct) vs `31 kg 40 g` (wrong), `80004` vs `80,004`.

### 5.1 Optional later: richer MCQ marks

The v1 prompt asks for the chosen label only. If the benchmark shows errors on crossed-out or double marks, add a `marks` list per option (`none/underline/circle/tick/box`, `crossed_out`) and the rule table "one candidate → selected; earlier mark crossed out and another marked → the uncrossed one; two candidates or all crossed out → ambiguous". This was **not tested** in the harness; do it only if needed, as `item-blind-v3`.

## 6. Combining the parts of one question (`combine_parts()`, pure)

| Parts | Question result |
|---|---|
| All `correct` | `correct` |
| All `blank` | `blank` |
| Any `wrong`, or some `blank` while others answered | `wrong` |
| Any part flagged for review | the question waits for the parent; unflagged parts keep their automatic result |

Decision D8: one `attempts` row per question, `correct = (result == correct)`; `blank` creates no attempt. Part results stay in `graded_answers` ("2 of 3 right"). The report may show `partial` (some correct, some not) for feedback, but the attempt is simply wrong.

## 7. Statuses

| Status | Meaning |
|---|---|
| `correct` | Matches the key |
| `wrong` | Answered and does not match |
| `blank` | Nothing written or marked. **Blank is not wrong**; it creates no attempt |
| `ambiguous` | Cannot be interpreted with certainty → parent |
| `needs_review` (flag) | Low confidence, near-miss, instruction part, provider error, model disagreement → parent |

## 8. Second opinion (optional, `VISION_SECOND_PROVIDER`)

In the test the two models made **different** mistakes (each was right where the other was wrong). So when a second provider is configured: read every item with both; per part, **same normalised answer → accept; different → `needs_review`** (`models_disagree`, keep the primary reading). Cost doubles; use it first only for the hardest kinds (handwritten Sinhala text, instruction parts) if cost matters. Store both readings in `graded_answers.second_opinion`.

## 9. Operations (this is what broke during testing)

- **Configurable model names.** `GEMINI_MODEL`, `GROQ_MODEL` … come from environment, never hard-coded: providers retire models (a default Gemini model returned 404 "no longer available to new users" during the test). On a 404 for the configured model, the Gemini provider lists models with `generateContent` and switches once to the newest `gemini-X-flash`, logging a warning; make this a warning in `/health` so the owner pins a model.
- **Retries:** 429/500/502/503/504 → exponential back-off (4 s, 8 s …, max 90 s, honour `Retry-After`), max 5 tries. **Do not retry hard quotas** (message contains `limit: 0`, `PerDay`, `per day`, or tokens-per-day): fail fast and mark the submission `needs_review`/`vision_error` so the parent is not blocked; alert the owner.
- **Latency is high and variable** (about 4–25 s per call, one call took 78 s on a free key). So grading is always a background job; the app polls. Use a concurrency limit (3–4) and a per-call timeout (90 s).
- **Idempotency:** cache by `(submission_id, paper_item_id, provider, model, prompt_version)` so a retry or restart never repeats paid calls.
- **Free tiers are for development only.** Observed: Groq free = 200 000 tokens per day per organisation and one vision model; Gemini free = small daily request caps that differ per model, reset at midnight Pacific time. Production needs a paid key. Check the provider's data-use terms for free vs paid before sending children's photos (free-tier inputs may be used to improve the provider's products; unverified here — read the terms).
- **Cost** (estimate to be replaced by `vision_calls` data): about 1 200–2 800 input tokens per question crop; OpenAI-class small models cost about US$ 0.001–0.005 per question. Log tokens for every call.
- **Privacy:** send only the crop (never the full photo, QR, name or student id). Log timings and token counts, never image content or the transcription of a child's handwriting at INFO level.

## 10. Parent confirmation

- `GET /submissions/{id}` returns, for each flagged part: a signed URL of the **block crop**, the machine reading (`read_text` or `read_selected`), `part_no`, `review_reason`, and the allowed decisions. **No answer key and no correctness hint is shown before the parent decides.**
- `POST /submissions/{id}/confirm` receives the parent's reading per flagged part (option label, text, or blank, and for instruction parts a yes/no "is it done as asked"). The server grades that reading with the same rules; the parent never types "correct".
- Items that were not flagged are finalised automatically (`confirmed_by = 'auto'`). When all items are final: insert `attempts` (`source = 0`, `time_ms = NULL`, `hints = NULL`, `penalty = 0.08`, `answered_at` = upload time, `paper_item_id` set), then `mastery.recompute`.
- A confirmed page cannot be re-uploaded (admin endpoint only, later). Re-uploading an unconfirmed page sets the old submission's `is_current = false`.

## 11. Choosing and monitoring the vision model

Use the harness as the benchmark (`python run.py grade --providers gemini groq --modes blind --ref`), then compare against human labels exported from its report (`labels.json`). Targets before going live (owner may adjust): on at least 100 questions from at least 5 children (consented, names and faces removed): exact reading accuracy ≥ 90 % for choice and number parts, ≥ 80 % for handwritten Sinhala text parts, and **zero** cases where a clearly blank answer is graded as answered. Also report: share of parts sent to the parent, latency, cost per paper. Re-run whenever the model or the prompt version changes.

## 12. Testing without the network

- `MockProvider` returns scripted `ItemRead`s. Unit tests: every row of section 5, `combine_parts`, instruction parts, part-count mismatch, near-miss, number-with-words, blank-vs-wrong, model disagreement.
- `scripts/make_synthetic_photo.py`: render a generated PDF page, apply random perspective, rotation, brightness gradient, blur, noise and fake marks. Tests: markers/QR found in ≥ 95 % of 100 photos; crop IoU ≥ 0.9; method B also registers ≥ 95 % of the same photos with markers hidden; wrong paper / missing marker / blurry give the expected `failed_alignment` reason.
- Real phone photos are still needed to tune the blur and confidence thresholds.
