# 04 — Paper generator

Input: a student, their latest mastery, and request parameters. Output: a PDF (1–3 pages, A4) plus `papers` and `paper_items` rows with the exact position of every question.

Pipeline: `paper_selection` (choose questions) → `paper_layout` (place them) → `paper_pdf` (draw) → self-check (render the PDF and detect the markers) → save.

## 1. Request parameters (defaults — DECISION D3, tune later)

| Parameter | Default | Meaning |
| --- | --- | --- |
| `mode` | `practice` | `practice` or `diagnostic` |
| `max_questions` | 15 | Hard cap. The page limit usually decides first: a typical question block is 25–60 mm tall and a page has 232 mm of usable height, so 2–3 pages hold about 8–16 questions. |
| `max_minutes` | 25 | Sum of `est_seconds` ≤ this |
| `max_pages` | 3 (allowed 1–3) | Page budget |
| `languages` | `["si","en"]` | Which question languages may appear |
| `focus_skills` | none | Optional list of skill codes to emphasise (value × 1.5) |
| `seed` | random, stored | Makes the paper reproducible |

Constants in `config` (not parameters): `TARGET_MASTERY = 0.80`, `STRETCH_CENTER = 0.60`, `UNKNOWN_NEED = 0.50`, `PER_SKILL_CAP = 3`, `UNKNOWN_SHARE_CAP = 0.25`, `RECENT_DAYS = 30`.

## 2. Selection (`paper_selection.py`, a pure function)

```python
def select_questions(mastery: dict[str, float | None],        # code -> mastery or None
                     item_probs: np.ndarray | None,           # shape (30, 3): P(correct) on a PAPER question per skill and difficulty
                     candidates: list[Candidate],             # active, key-verified, not recently attempted
                     params: PaperParams) -> list[Selected]: ...
```

### 2.1 Candidate pool
Active questions with a verified key, in the allowed languages, not attempted by this student in the last `RECENT_DAYS` days and not already on their last 3 papers.

### 2.2 Value of a question (practice mode)

```
need(skill)  = max(0.05, TARGET_MASTERY - mastery)        if mastery is known
             = UNKNOWN_NEED                               if mastery is null
p_q          = item_probs[skill, difficulty]              # predicted P(correct) on this exact question
stretch(p)   = max(0.05, 1 - abs(p - STRETCH_CENTER) / STRETCH_CENTER)     # best near p = 0.6
fit(q)       = stretch(p_q)                               if mastery known
             = {easy: 0.8, medium: 1.0, hard: 0.6}        if mastery unknown (the model has no basis)
value(q)     = need(skill) * fit(q) * (1.5 if skill in focus_skills else 1.0)
```

Reading: the paper should spend its questions on weak or unknown skills, using questions the child has a fair but not certain chance of answering (the "stretch zone"). The `0.05` floor keeps mastered skills in occasional rotation.

### 2.3 Choosing the questions: a multi-constraint 0/1 knapsack

Choosing which questions go on the paper is a **knapsack problem**: every candidate question has a *value* (section 2.2) and several *costs* (time, page space), the paper has limited capacity, and the aim is the highest total value that fits.

Let `x_i = 1` if candidate question `i` is on the paper, else `0`.

```
maximise   sum_i value_i * x_i

subject to
  sum_i est_seconds_i * x_i             <= max_minutes * 60                         (time budget)
  sum_i layout_height_mm_i * x_i        <= 0.92 * max_pages * USABLE_HEIGHT_MM       (page space; 0.92 allows for packing waste)
  sum_i x_i                             <= max_questions                             (count)
  sum_{i in skill s} x_i                <= PER_SKILL_CAP                  for every skill s       (variety)
  sum_{i in unknown skills} x_i         <= floor(UNKNOWN_SHARE_CAP * max_questions)                 (not only exploration)
  sum_{i in skill s} x_i                >= 1       for each of the 3 weakest KNOWN skills that has candidates   (coverage)
  x_i in {0, 1}
```

**Primary solver (exact):** Google OR-Tools **CP-SAT** (`pip install ortools`). Multiply values by 1000 and round to integers, add the constraints above, set `random_seed` from the paper's seed and a time limit of 5 seconds, and read the solution. The result is optimal for the stated model, and the seed makes it repeatable.

**Classic alternative (for explanation in the report):** with only the time and height constraints, the same problem is solved by dynamic programming over a two-dimensional grid (time in 10-second units, height in 5 mm units). It is exact for those two capacities but cannot handle the per-skill and coverage constraints directly, which is why CP-SAT is the primary solver.

**Baseline and fallback:** also implement `select_greedy` (sort by `value / est_seconds`, add a question if every constraint still holds; run the coverage rule first). Use it (a) as the comparison baseline in the evaluation and (b) as a fallback if the solver reports no solution in time. Record which method produced each paper in `params.selection_method`.

**Research result to produce (`scripts/eval_selection.py`):** for 100 simulated students with different mastery vectors, report total value, number of questions, weak-skill coverage and run time for knapsack vs greedy. Expect knapsack to be at least as good everywhere; the size of the gain is the finding, not an assumption.

### 2.4 Diagnostic mode (new child or many unknown skills)
- Take the skills whose mastery is `null`, ordered by area (APT, MAT, LAN, ENV), then by `sort_index`.
- For each skill choose **one easy and one medium** question (if only one exists, take one).
- Stop at `max_questions`. Record in `params` which skills were covered (`diagnostic_skills`), so the next diagnostic paper continues with the remaining skills.
- With 30 skills this gives about 4 papers of 15 questions. The game can also supply the same diagnostic information digitally.

### 2.5 Edge cases (must have tests)
- A skill with no candidate questions: skip it, record `skipped_skills` in `params`.
- Fewer candidates than `max_questions`: return fewer, never repeat a question.
- `item_probs is None` (no history): use diagnostic mode.
- Total constraints too tight for even one question: raise a clear error `NotEnoughQuestions`.

## 3. Layout (`paper_layout.py`, a pure function)

### 3.1 Page geometry (millimetres, origin top-left; constants in one file)

| Item | Value |
| --- | --- |
| Page | A4 portrait, 210 × 297 |
| ArUco marker | `DICT_4X4_50`, side 12 mm, IDs: top-left 0, top-right 1, bottom-right 2, bottom-left 3. Same on every page. |
| Marker centres | 13 mm from each page edge |
| **Frame** | rectangle between the 4 marker centres: x 13 → 197, y 13 → 284, i.e. **184 × 271 mm** |
| QR code | 20 × 20 mm, x 165–185, y 14–34 (inside the header, clear of the top-right marker) |
| Header text | "MindBridge practice paper · code `<qr_token>` · page `p` of `n`" at x 20, y 22, Helvetica 9 pt, Latin characters only |
| Content area | x 20 → 190, y 40 → 272 (usable height 232 mm) |
| Footer text | "Print at Actual size (100%). Do not use Fit to page." Helvetica 8 pt at y 281, centred, between the bottom markers |

All text drawn by the generator uses Latin characters and digits only (ReportLab does not shape Sinhala correctly). Sinhala appears only inside the question images.

### 3.2 Question block
- Left column (x 20–30): the printed question number, e.g. `7.`, Helvetica 12 pt.
- Image at x 30, width `min(160 mm, width_px * 25.4 / 150)` (assumes 150 dpi unless the question has a `print_dpi`), height in proportion; if the height exceeds 90 mm, shrink to 90 mm high.
- 3 mm clear padding around the image on every side (children underline, circle and cross out on the printed image, so nothing else may be drawn over it).
- **Answer space:** most bank images already contain their answer space (dotted lines, letter boxes, option lists), and children write directly on the image. For these (`questions.answer_space_in_image = true`, the default) draw **nothing** below the image; grading reads the whole block (see `05`). Only when the flag is `false` add answer boxes:
- **Short-answer parts (flag `false` only):** below the image add one **answer box** per short part, in part order, 3 mm below the image (and 3 mm between rows), with a light grey 0.5 pt border and a small Latin number label at its left edge (`1`, `2`, `3`…, the part number).
  - Exactly one short part: one box 160 mm × 14 mm.
  - Two or more short parts: boxes 78 mm × 14 mm, two per row, filled left to right then down (so `n` parts use `ceil(n/2)` rows).
  - The box numbers follow the order of the parts in the database (top to bottom, then left to right on the image). The owner must write the answers in that order (see `02`). Box labels are digits only because the generator cannot print Sinhala letters.
- **MCQ parts** need no extra drawing: the child marks the options printed on the image.
- 6 mm gap between blocks.
- Block height = padding + image height + (3 + 14 × rows of answer boxes + 3 × (rows − 1), only if answer boxes are drawn) + padding. `layout_height_mm(question)` is this value and is used by the selector.

### 3.3 Order and pagination
- Order: area (APT, MAT, LAN, ENV), then easy → hard, so children start with easier questions in each area. Printed numbers run 1..N across pages.
- First-fit: if a block does not fit in the rest of the page, start the next page. A block is never split across pages.
- If layout needs more than `max_pages`: drop the lowest-valued question and re-layout; repeat. Record dropped ids in `params`.

### 3.4 Output of layout
For each item: `page`, `position`, and boxes in **fractions of the frame**:

```
fx = (x_mm - 13) / 184        fy = (y_mm - 13) / 271
fw = w_mm / 184               fh = h_mm / 271
```

`block_*` = the whole block (number column excluded; padding included). `answer_boxes` = a list with one entry per drawn answer box: `{"part_no": 1, "x": …, "y": …, "w": …, "h": …}` (fractions of the frame), or `null` when no boxes were drawn. Store exactly these in `paper_items`. Grading uses `block_*` (the whole block); `answer_boxes` are only used to highlight the part on the review screen. Because everything is relative to the marker rectangle, the paper still grades correctly if a printer scales the page slightly.

## 4. PDF (`paper_pdf.py`)

- ReportLab canvas, A4. Markers: generate with `cv2.aruco.generateImageMarker(dict, id, 400)`, draw with a 2 mm white quiet zone.
- QR content: `MB1:<qr_token>:<page>` (e.g. `MB1:K7QX4M2PD9TB:2`). Use the `qrcode` package, error correction level M. The token is random and opaque (12 base32 characters) and contains nothing about the child.
- Question images: fetch from storage, convert to RGB, downscale to at most 200 dpi at their printed size before embedding (keeps the PDF small), draw with `drawImage`.
- Set PDF metadata title to `MindBridge paper <qr_token>`; no student information.
- **Self-check before saving:** render each page with `pypdfium2` at 150 dpi, run the same marker detector used in grading, and assert that all four markers and the QR are found and that the QR text matches. If this fails, do not save the paper; raise an error.
- Save the PDF through `StorageBackend`, then insert `papers` + `paper_items` in one transaction.

## 5. Printing instructions (shown in the app)
- A4, **Actual size / 100%**, black and white is fine, standard matte paper.
- Do not crop the corners; do not staple or fold over the black squares.
- After the child answers: photograph each page flat, in good light, with all four black squares visible.

## 6. Tests
1. Selection respects every constraint (count, time, height, per-skill cap, unknown share, recent exclusion, verified keys only).
2. Weak skills receive more questions than strong ones on a hand-made mastery vector.
3. Diagnostic mode covers each unknown skill with one easy + one medium question where available.
4. Same seed → identical paper; different seed → different tie-breaks.
5. Layout never overlaps blocks, never leaves a block outside the content area, and keeps fractions in `[0, 1]`.
6. PDF self-check passes; QR decodes to the expected text; marker IDs are in the right corners.
7. A paper with `max_pages=1` and too many questions drops items and records them.
8. Knapsack: on 200 random small instances the solver's value equals a brute-force optimum (n <= 15) and is never below the greedy value; every constraint holds; same seed gives the same paper; solver time-out falls back to greedy.
9. A question with three short parts and `answer_space_in_image = false` gets three numbered answer boxes (two per row), stored in `answer_boxes` in part order, inside the block and inside the content area; with the flag `true` it gets none and `answer_boxes` is null.
10. Layout leaves at least 8 pt of white space above and 10 pt below each block's image area, so a grading crop (`05` section 2) does not swallow a neighbouring question.
