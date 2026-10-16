# Limitations of the bilingual hybrid-state knowledge tracing component

Read this before quoting any number from the evaluation. Each item says what is true today and
what would change it.

## What was and was not tested

| Area | Status |
|---|---|
| Model weights reproduce the Colab outputs | Verified exactly (golden test) |
| Paper selection (knapsack vs greedy) | Measured on simulated students and the real question bank (`scripts/evaluate_all.py`) |
| Paper PDF, QR codes, corner markers, self-check | Tested on generated PDFs and synthetic photos |
| Photo alignment and cropping | Tested on **synthetic** photos (rotation, perspective, blur, shadow) - **no real phone photos of a printed, hand-written paper yet** |
| Marking (rules, blind reading, review policy) | Tested with a scripted reader (mock) and an offline fake Gemini server - **never with real Gemini output on real handwriting** |
| Full journey (diagnostic paper -> game -> photo -> marking -> mastery -> next paper) | `tests/knowledge_tracing/test_end_to_end.py`, with the mock reader |

## Model

1. **Trained on simulated data.** The GRU was trained on simulated students, not on children.
   Its accuracy on real children is unknown. Any AUC quoted from Colab describes how well it
   learns the simulator.
2. **Mastery is still fairly high for a child who gets almost everything wrong.** For 1000
   simulated children with 1 correct answer out of 6 in one skill, mastery was min 0.160,
   median 0.261, max 0.374 (seed 11; `scripts/optimism_check.py`). It is not above 0.5, but it is not
   near 0 either. Do not read 0.26 as "26% of questions will be right" for a real child.
3. **Paper answers carry no time or hints.** A constant penalty (0.08) is used. On the 3 golden
   histories this moved mastery by at most 0.039, but on 100 simulated students (30% paper
   answers) the change was median 0.041, 95th percentile 0.071, max 0.115, and 31.3% of skill
   values moved by more than the 0.05 threshold (seed 11; `penalty_sensitivity --students 100`). The
   simplification is NOT safe in general; collect paper time or hints, or report this effect.
4. **Mastery is the probability of a correct answer to a medium paper question**, and is `null`
   for a skill with fewer than 3 answers. A skill with few answers is "unknown", not "weak".
5. **History cap of 140 answers.** Older answers are dropped.

## Paper selection

6. **The 70/30 split depends on the question bank.** With a small bank, or after a child has
   answered most questions of a skill in the game (the paper avoids repeats), the paper cannot
   reach 70% weak - the end-to-end test shows this with a 6-question-per-skill bank. Roughly 25
   questions per skill is needed for the split to hold week after week.
7. **Time estimates are guesses.** Paper time per question is estimated from game times; no
   paper timing has been measured.
8. **Difficulty is the question's label** (easy/medium/hard); it is not learned from answers.

## Reading and marking

9. **Handwriting is read by a general vision model.** Accuracy on Sinhala/Tamil children's
   handwriting has not been measured. `scripts/benchmark_vision.py` is ready; it needs labelled,
   consented photos.
10. **Starting values, not tuned values:** blur limit 2.0, near-miss similarity 0.80, reader
   confidence floor 0.60, the unit and negator tables. They must be tuned on the benchmark.
11. **Hand-over rate is unknown.** The policy sends a question to the parent only when the reader
    cannot decide. How often that happens on real photos is not measured.
12. **One reader.** A second opinion (a second model) is supported but only one is configured;
    the OpenAI-compatible reader is not written.
13. **Pages can stay at "grading"** if the server restarts while a page is being marked. There is
    no retry sweep; the parent re-uploads the page.

## Privacy and operation

14. **Photo deletion is not scheduled.** `scripts/delete_expired_photos.py` must be run daily
    (cron / Task Scheduler). Until then, expired photos are never *served* (410) but the files
    remain on disk.
15. **No authentication.** Access checks (parent <-> child) belong to the platform team's login
    work; endpoints here trust the `learner_id`.
16. **The report is the one place the answer key leaves the server** (by decision): correct
    answers appear in a separate list, only for questions the child got wrong or left blank.
17. **Pictures sent to Gemini** leave the system. Using a paid key (no training on inputs) and
    parental consent are needed before real children use it.

## Not done in this component

- The game does not yet call `POST /attempts`.
- Frontend screens (paper download, upload, review, report).
- Per-question time on paper.
- Checking model mastery against real paper accuracy.

## How to reproduce the numbers

```
cd backend
.venv\Scripts\python -m scripts.evaluate_all --out ..\research\evaluation.md
.venv\Scripts\python -m pytest tests\knowledge_tracing\test_end_to_end.py
```
