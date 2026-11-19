# Grade 5 Addition draft package: Nimo's Sky Adventure

Development-only package for `G5-AREA-MAT-02` (`එකතු කිරීම`) and universal skill `MAT-OPS`.
The game is one story with three places, one skill each:

| Place | Skill | What the child does |
|---|---|---|
| Sky City (the mission) | `G5-MAT-C06-L01-O03`, three three-digit numbers with two or three carries | Loads three airship crates into the warehouse and sets the lock to their total, marking each carried place. |
| Number Factory (training) | `G5-MAT-C06-L01-O01`, two three-digit numbers with exactly two carries | Feeds the numbers into place bins, bundles every ten blocks into the next place, and sets the output to the total. |
| Crystal Flight (training) | `G5-MAT-ADD-MENTAL-01`, quick addition facts | Flies Nimo through the energy crystals and sets the energy they make together. |

The two carrying targets are linked directly to the draft curriculum trace on page 12. Quick
facts is a provisional activity mapping from page 8 that requires educator and curriculum review.

Every episode starts on the Sky City mission, unsupported. A wrong answer opens the multi-help
loop: the server orders the help types, and the phone shows each help item in the place that fits
its skill (the Number Factory for carrying, the Crystal Flight for quick facts). After the help is
withdrawn, a fresh unsupported Sky City item with the same addend and carry counts measures
Independence Gain. Only a valid post-withdrawal response can update a skill's future help
preference.

The runtime definitions live in `backend/app/gamification/content/addition_adventure.py`. The
misconception catalogue and the three-scaffold catalogue keep their versions, so the research
models read the same codes as before; codes that only the earlier activities could produce simply
no longer occur.

This package is blocked from production and general child delivery until curriculum,
Sinhala-language, educator, usage-rights, accessibility, answer-leakage, ethics/privacy,
model-safety, and release reviews are recorded. Artwork is in
`frontend/public/curriculum/game/G5-AREA-MAT-02/`; synthetic tests validate mechanics, not
curriculum correctness or research readiness.
