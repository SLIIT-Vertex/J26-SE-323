# PP1 multi-turn demonstration records

Scenario `pp1-fractions-escalation-fading-v1`, produced by `backend/scripts/pp1_multiturn_demo.py`.
All drafts are **EXPERIMENTAL AI RESPONSE — NOT VERIFIED / NOT FOR LEARNERS**. None was verified,
authorized or delivered to a learner. Transcripts contain no API key, session token or learner ID.

| File stem | Evidence status | Notes |
|---|---|---|
| `…-gemini-sqlite-2026-10-21T154841` | **Partial live evidence** | Real `gemini-3.1-flash-lite`, thinking LOW. 2/7 drafts generated, 5 HTTP 502/503 failures. Predates the L0 fix and the two-consecutive-503 stop rule. Review: `…154841-review.md`. |
| `…-gemini-sqlite-2026-10-21T160403` | **No live draft** | Second approved run, after the L0 fix. First call returned 503; stopped by rule after 1/7 calls. Shows the stop guard working, not Gemini behaviour. |
| `…-HARNESS-FAILURE-no-request-sent-2026-10-21T154648` | Not evidence | Runner bug (closed HTTP client). Offline reproduction confirmed no request was sent. |
| `…-fake-sqlite-*` | Rehearsal only | Fake provider; validates the pipeline, persistence and invariants, not Gemini behaviour. |

Expected levels in each transcript assume every draft is generated and shown. A failed draft is not
previous assistance, so later levels legitimately differ when generation fails.

## Records made before the 2026-10-22 provenance fixes

These records are kept unchanged. Read them with these corrections:

- **Draft source "google-gemini" on fake drafts.** Rehearsals before 2026-10-22T0251 injected the
  fake client underneath the real Gemini adapter, so the browser-e2e `2026-10-22T024131`
  screenshots show "google-gemini" for drafts that are visibly `[FAKE PROVIDER — NOT GEMINI]`.
  Rehearsals now use a separate provider named `fake-rehearsal-not-gemini`.
- **Mastery / support need "SYNTHETIC".** Earlier runs labelled the whole adapter SYNTHETIC
  whenever a cold-start default was configured. For the Postgres run
  `…-fake-configured-2026-10-22T024008` it therefore **cannot be determined** whether the real
  learner's mastery came from knowledge tracing or from the default. Labels are now per value.
- **Scripted attempts recorded as `researcher-review-v1`.** Runner attempts before this fix used
  the same scoring version as the human researcher panel. They now use `scripted-scenario-v1`.
  Existing database rows were not rewritten.

