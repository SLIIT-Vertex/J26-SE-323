# 02 — Database (PostgreSQL)

All tables use `snake_case`. Use Alembic migrations; do not create tables by hand. If the group already has `students` (or `users`) tables, reference them instead of creating the stub below, and use the same id type.

## 1. Schema

```sql
-- Stub only if the group has no students table yet.
CREATE TABLE IF NOT EXISTS students (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- The 30 skills. sort_index is the model's skill index (0..29). Never reorder.
CREATE TABLE skills (
    code           text PRIMARY KEY,                -- e.g. 'MAT-FRC'
    sort_index     smallint NOT NULL UNIQUE CHECK (sort_index BETWEEN 0 AND 29),
    area           text NOT NULL CHECK (area IN ('APT','MAT','LAN','ENV')),
    name_en        text NOT NULL,
    name_si        text,
    default_difficulty text NOT NULL DEFAULT 'medium'
                   CHECK (default_difficulty IN ('easy','medium','hard'))
);

CREATE TYPE question_type AS ENUM ('mcq', 'short');

-- One bank image = one question. A question has 1 or more PARTS (see question_parts):
-- most questions have exactly one part; a question with several answers on the same image has one part per answer.
CREATE TABLE questions (
    id                 text PRIMARY KEY,            -- e.g. '3.41' (the bank id)
    skill_code         text NOT NULL REFERENCES skills(code),   -- the FIRST listed skill (decision D9)
    secondary_skill_codes text[] NOT NULL DEFAULT '{}',          -- further skills, e.g. {'LAN-ORT'}; not used by the model
    difficulty         text NOT NULL CHECK (difficulty IN ('easy','medium','hard')),
    difficulty_source  text NOT NULL DEFAULT 'skill_default'
                       CHECK (difficulty_source IN ('skill_default','manual','measured')),
    language           text NOT NULL CHECK (language IN ('si','en')),
    image_key          text NOT NULL,               -- storage key of the question image (private)
    image_width_px     integer NOT NULL CHECK (image_width_px > 0),
    image_height_px    integer NOT NULL CHECK (image_height_px > 0),
    answer_space_in_image boolean NOT NULL DEFAULT true,   -- true: the bank image already has dotted lines / boxes for the answer (the normal case); false: the generator must add answer boxes (see 04)
    est_seconds        integer NOT NULL DEFAULT 60 CHECK (est_seconds > 0),   -- from the difficulty/time file (minutes x 60; sum of times for two-skill questions)
    answer_key_raw     text,                        -- the original key line, e.g. 'i.වාහන, ii. සෙල්ලම්' (traceability, re-import)
    content_hash       text UNIQUE,                 -- SHA-256 of the image bytes: catches the same question imported twice
    source_paper       text,                        -- which past paper it came from (optional)
    source_year        smallint,                    -- optional
    source_question_no text,                        -- number in the original paper (optional, traceability)
    notes              text,
    active             boolean NOT NULL DEFAULT true,
    key_verified_by    text,                        -- second person who checked the answer key
    key_verified_at    timestamptz,
    created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX questions_skill_idx ON questions (skill_code, difficulty) WHERE active;

-- The answers of a question, in the order the child answers them (top to bottom, left to right on the image).
-- A single-answer question has exactly ONE part (part_no = 1). The importer enforces "at least one part".
CREATE TABLE question_parts (
    question_id      text NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    part_no          smallint NOT NULL CHECK (part_no >= 1),
    part_type        question_type NOT NULL,        -- 'mcq' for choice parts, 'short' for number / text / instruction parts
    answer_kind      text NOT NULL DEFAULT 'text'
                     CHECK (answer_kind IN ('choice','number','text','instruction')),  -- inferred by the importer (see 2.2)
    option_labels    text[],                        -- MCQ part: e.g. {'1','2','3','4'} or {'I','II','III','IV'}
    correct_option   text,                          -- MCQ part: one of option_labels, same spelling
    accepted_answers text[],                        -- short part: raw strings (alternatives); normalised at grading time; may be empty for an instruction-only part
    instruction      text,                          -- grader instruction from the key (the text inside "..."), e.g. 'color three boxes'
    label_on_image   text,                          -- optional hint for the vision prompt, e.g. '(a)', 'ii'
    PRIMARY KEY (question_id, part_no),
    CONSTRAINT mcq_part_fields CHECK (
        part_type <> 'mcq' OR (option_labels IS NOT NULL AND array_length(option_labels,1) >= 2
                               AND correct_option = ANY(option_labels))),
    CONSTRAINT short_part_fields CHECK (
        part_type <> 'short' OR instruction IS NOT NULL
        OR (accepted_answers IS NOT NULL AND array_length(accepted_answers,1) >= 1))
);

-- One row per answered question. Both digital and paper.
CREATE TABLE attempts (
    id            bigserial PRIMARY KEY,
    student_id    uuid NOT NULL REFERENCES students(id),
    question_id   text NOT NULL REFERENCES questions(id),
    source        smallint NOT NULL CHECK (source IN (0,1)),   -- 1 digital, 0 paper
    correct       boolean NOT NULL,
    time_ms       integer,                                      -- digital only
    hints         integer,                                      -- digital only
    penalty       real NOT NULL CHECK (penalty BETWEEN 0 AND 1),-- computed by the backend (see 03)
    answered_at   timestamptz NOT NULL,
    paper_item_id uuid,                                         -- set for paper attempts
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX attempts_history_idx ON attempts (student_id, answered_at, id);
CREATE UNIQUE INDEX attempts_paper_item_uq ON attempts (paper_item_id) WHERE paper_item_id IS NOT NULL;

CREATE TABLE mastery_snapshots (
    id             bigserial PRIMARY KEY,
    student_id     uuid NOT NULL REFERENCES students(id),
    computed_at    timestamptz NOT NULL DEFAULT now(),
    model_version  text NOT NULL,
    n_attempts     integer NOT NULL,
    skills         jsonb NOT NULL      -- {"MAT-FRC": {"mastery": 0.62, "attempts": 14}, "APT-PAT": {"mastery": null, "attempts": 1}, ...}
);
CREATE INDEX mastery_latest_idx ON mastery_snapshots (student_id, computed_at DESC);

CREATE TYPE paper_status AS ENUM ('generated','partially_uploaded','graded','needs_review','confirmed','cancelled');

CREATE TABLE papers (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id            uuid NOT NULL REFERENCES students(id),
    qr_token              text NOT NULL UNIQUE,          -- opaque, 12 chars base32; no personal data
    status                paper_status NOT NULL DEFAULT 'generated',
    mode                  text NOT NULL DEFAULT 'practice' CHECK (mode IN ('practice','diagnostic')),
    params                jsonb NOT NULL,                -- requested size, minutes, focus skills
    mastery_snapshot_id   bigint REFERENCES mastery_snapshots(id),
    model_version         text NOT NULL,
    page_count            smallint NOT NULL,
    pdf_key               text NOT NULL,
    created_at            timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE paper_items (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id       uuid NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    position       smallint NOT NULL,                    -- printed question number (1-based)
    question_id    text NOT NULL REFERENCES questions(id),
    page           smallint NOT NULL,                    -- 1-based
    -- Boxes are fractions (0..1) of the FRAME between the 4 marker centres.
    block_x real NOT NULL, block_y real NOT NULL, block_w real NOT NULL, block_h real NOT NULL,
    answer_boxes jsonb,                                  -- OPTIONAL: [{"part_no":1,"x":..,"y":..,"w":..,"h":..}, ...]; null when the question image already contains its answer space (grading reads the whole block, see 05)
    shown_difficulty text NOT NULL,
    predicted_p      real,                               -- model's predicted P(correct) when selected
    UNIQUE (paper_id, position)
);

CREATE TYPE submission_status AS ENUM ('uploaded','failed_alignment','graded','needs_review','confirmed');

CREATE TABLE paper_submissions (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id        uuid NOT NULL REFERENCES papers(id),
    page            smallint NOT NULL,
    image_key       text NOT NULL,                       -- original photo, private
    status          submission_status NOT NULL DEFAULT 'uploaded',
    failure_reason  text,
    alignment_info  jsonb,                               -- {"method":"markers"|"features", marker positions or inlier count, reprojection error, blur_score}
    is_current      boolean NOT NULL DEFAULT true,       -- newest upload for this (paper, page)
    uploaded_at     timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX one_current_submission ON paper_submissions (paper_id, page) WHERE is_current;

CREATE TABLE graded_answers (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id    uuid NOT NULL REFERENCES paper_submissions(id) ON DELETE CASCADE,
    paper_item_id    uuid NOT NULL REFERENCES paper_items(id),
    part_no          smallint NOT NULL DEFAULT 1,        -- which answer of the question (1 for ordinary questions)
    crop_key         text NOT NULL,                      -- cropped image used for grading (private)
    vision_provider  text NOT NULL,
    vision_model     text NOT NULL,
    prompt_version   text NOT NULL,
    raw_response     jsonb,                              -- provider output, no answer key inside
    match_how        text,                               -- exact | choice-equivalent | number found in text | loose | similar | different | empty
    instruction_met  boolean,                            -- the model's yes/no for parts that have an instruction
    second_opinion   jsonb,                              -- optional second provider's reading and whether it agreed
    read_selected    text,                               -- MCQ: the option label the rules chose
    read_text        text,                               -- short answer: what was written
    auto_status      text NOT NULL CHECK (auto_status IN ('correct','wrong','blank','ambiguous')),
    confidence       real,
    needs_review     boolean NOT NULL DEFAULT false,
    review_reason    text,
    final_status     text CHECK (final_status IN ('correct','wrong','blank')),  -- null until decided
    confirmed_by     text,                                                      -- 'auto' or parent id
    confirmed_at     timestamptz,
    UNIQUE (submission_id, paper_item_id, part_no)
);

-- One row per vision API call: cost, latency and quota monitoring (no image content, no transcriptions).
CREATE TABLE vision_calls (
    id              bigserial PRIMARY KEY,
    submission_id   uuid REFERENCES paper_submissions(id) ON DELETE SET NULL,
    paper_item_id   uuid REFERENCES paper_items(id) ON DELETE SET NULL,
    provider        text NOT NULL,
    model           text NOT NULL,
    prompt_version  text NOT NULL,
    role            text NOT NULL DEFAULT 'primary' CHECK (role IN ('primary','second_opinion')),
    latency_ms      integer,
    tokens_in       integer,
    tokens_out      integer,
    http_status     smallint,
    error_code      text,                               -- e.g. 'quota_daily', 'rate_limit', 'model_not_found', 'invalid_json'
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX vision_calls_day_idx ON vision_calls (provider, model, created_at);
```

The `skills` table must be seeded from `shared/feature_spec.json` (code and `sort_index` from the list order). Add a startup check that fails loudly if the table and the JSON disagree.

## 2. Question import (CSV or JSON)

### 2.1 What is stored for every question

| Field | Required | Purpose |
| --- | --- | --- |
| `id` (e.g. `3.41`) | yes | Bank id |
| image (`image_key`, width, height, `content_hash`) | yes | The question picture; the hash catches duplicates |
| `skill_code` | yes | One of the 30 skills; the model's input |
| `difficulty` + `difficulty_source` | yes (defaults from the skill) | `easy`/`medium`/`hard`; see decision D1 |
| `language` | yes | `si` or `en` |
| **parts** (1 or more): answer key (alternatives, labels, instruction), kind, option labels | yes | See 2.2 (the key syntax of the question-bank text files) |
| `secondary_skill_codes` | optional | Questions that list two skills (D9) |
| `est_seconds` | yes (default 60) | Time budget for the paper generator |
| `key_verified_by` / `key_verified_at` | filled after import | Second-person check of the answer key |
| `active` | yes (default true) | Switch a question off without deleting it |
| `source_paper`, `source_year`, `source_question_no`, `notes` | optional | Traceability |

Do **not** store per-question statistics (times shown, share answered correctly) on the question row; compute them from `attempts` when needed (they will later replace guessed difficulties).

### 2.2 The answer key syntax (one line per question) — parts, alternatives, instructions

The question bank owner keeps plain-text files (formats in `09` section 2). The key syntax below is implemented and tested in `reference/grading_test_harness/gradetest/answer_key.py` (`parse_answer`); **port it, do not redesign it**. It replaces the earlier `;`-separated CSV columns (`part_count`, `part_types`, `answers`); if Step 1 was already built with those, migrate them to this syntax.

| Written in the key | Meaning |
| --- | --- |
| `a, b, c` | three parts (three answers on one image), in the order the child answers them |
| `ans1/ans2` | alternatives of ONE part; either is accepted |
| `i.වාහන, ii. සෙල්ලම්` | optional labels `i.` / `ii.` before parts (stored in `label_on_image`) |
| `80,004` | a comma inside a number is not a separator (digit, comma, exactly three digits, no space after) |
| `1000, 90` | comma + space separates parts |
| `1/2` | slash between digits is a fraction, not an alternative |
| `"color three boxes"` | straight double quotes = instruction to the grader (stored in `instruction`); a part with only an instruction has no text answer |
| `12 "also check the unit"` | answer plus instruction |
| `“…”` | curly quotes are ordinary answer text |
| `\,` | a literal comma inside one answer |

`answer_kind` is inferred: `choice` (every alternative is one of `1 2 3 4 i ii iii iv` → `part_type='mcq'`, `option_labels` default to `1/2/3` or `i/ii/iii`, extended to include the key), `number` (numeric), `instruction` (only a quoted instruction), else `text`. An optional CSV column `option_labels` overrides the default labels.

One bank image is still **one question**; several parts exist only when the image cannot be split. The order of the parts is the contract between the database, the prompt (`05`) and the parent-review screen. If a question can be split into separate images instead, prefer that.

### 2.3 Importer rules

Required columns (CSV/JSON): `id, skill_code, difficulty, language, image_file, answer_key, est_seconds`; optional: `option_labels, secondary_skills`. Alternatively the importer reads the teacher's text files directly: `answers_*.txt` (`id -key`), `skillMap-*.txt`, `difficult-time-*.txt` (formats and the two-skill form in `09` section 2) and merges them by question id.

Rules the importer must enforce (reject the whole file with a list of line errors, never import half):

1. `id` unique; `skill_code` exists; image file exists and is a PNG/JPEG; read width and height from the image; `content_hash` not already present.
2. `difficulty` empty → use the skill's `default_difficulty` and set `difficulty_source='skill_default'`; filled → `manual`.
3. MCQ part: `option_labels` has ≥ 2 labels, the answer is one of them. Labels may be digits, Roman numerals or letters; store exactly as printed on the image.
4. Short part: at least one accepted answer **or** an instruction. Alternatives come from `/` in the key. Store them raw (normalisation happens at grading, see `05`).
5. A question always has at least one part. Parse errors in the key (unbalanced `"`, empty part, unknown label) reject the file with the line number. The importer warns when the image is unusually tall and the key has one part (it may contain more than one question).
5b. **Cross-file checks (report, do not guess):** ids present in the answer file but missing from the skill or difficulty files, and the reverse; a skill code not in `skills`; unparseable difficulty or time; a question with two skills (apply D9). Report the full list at the end; reject the import only for ids that would be incomplete (no skill or no difficulty and no default).
6. **Verification:** `key_verified_by` is empty on import. A report script `scripts/unverified_keys.py` lists unverified questions. The paper generator uses only questions with `key_verified_at IS NOT NULL` once the setting `REQUIRE_VERIFIED_KEYS=true` (default true outside tests).

## 3. Seed data

- `skills`: 30 rows (names to be filled by the project owner; use the code as `name_en` until then).
- A small set of fake questions for tests lives in `tests/fixtures/` (generated images with big printed text; never real exam content).

## 4. Notes

- Image keys are storage keys, not URLs. Signed URLs are created per request and expire (`SIGNED_URL_SECONDS`).
- Never expose `correct_option`, `accepted_answers`, `instruction` or `answer_key_raw` through any client-facing schema. Add a test that serialises every public response model and asserts these field names do not appear. A second test must fail if any vision prompt string contains an accepted answer or the correct option.
- Attempts are append-only. A parent correction creates the `final_status` on `graded_answers` first, and the `attempts` row is created only after the decision is final.
- **One attempt per question, also for multi-part questions (DECISION D8).** The attempt is `correct` only if **all** parts are correct; the part-by-part results stay in `graded_answers` for feedback ("2 of 3 right"). The digital game must apply the same rule so both sources mean the same thing. Because a multi-part question is harder to get fully right, the owner should label its difficulty with that in mind (usually one level up).
