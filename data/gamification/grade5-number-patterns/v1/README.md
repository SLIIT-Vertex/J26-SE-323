# Grade 5 Number Patterns draft package: Nimo's Bubble Trouble

Development-only package for `G5-AREA-MAT-03` (`සංඛ්‍යා රටා`) and universal skill `APT-PAT`. A
seashell blows Nimo into an underwater playground, where a cheeky octopus dares him to a
bubble-submarine race. Four pattern skills, each of which can be the race:

| Skill | Pattern | Example |
|---|---|---|
| `G5-MAT-PAT-DIFF-ASC-01` | +2 | 1, 3, 5, 7, … |
| `G5-MAT-PAT-DIFF-DESC-01` | −2 | 12, 10, 8, 6, … |
| `G5-MAT-PAT-RATIO-2-01` | ×2 | 5, 10, 20, 40, … |
| `G5-MAT-PAT-RATIO-5-01` | ×5 | 4, 20, 100, 500 |

| Game | When | What the child does |
|---|---|---|
| Bubble Rush (the mission) | Every episode starts here, unsupported; each new race picks a pattern at random | Steers the submarine through the bubble with the pattern's rule (+2, −2, ×2 or ×5), then through the ring with the next number at each junction. Every ring is passed the same way; only the finish line shows the result. |
| Jellyfish Copy Party (training) | Help on a multiplying pattern | Finds the magic shell (×2 to ×5) that turns the first group of jellyfish into the second, then uses it again to fill each blank. |
| Crab's Bubble Steps (training) | Help on an adding or taking-away pattern, and the plainest help on a multiplying one | Watches Tiki the crab hop the known shells with each jump written over it, then picks the number Tiki lands on next. |

A muddled race opens the multi-help loop (the server picks every help round). After the help is
withdrawn, a fresh unsupported race on the same pattern measures Independence Gain. Choosing a rule
of the other kind (adding where the pattern multiplies, or the reverse) is scored as
`additive_multiplicative_confusion`.

The runtime definitions live in `backend/app/gamification/content/number_patterns.py`. The
misconception and scaffold catalogues keep their versions, so the research models read the same
codes as before; the ×3 and ×4 skills are no longer played.

This package is blocked from production and general child delivery until curriculum,
Sinhala-language, educator, usage-rights, accessibility, answer-leakage, ethics/privacy,
model-safety, and release reviews are recorded. Artwork is in
`frontend/public/curriculum/game/G5-AREA-MAT-03/`.
