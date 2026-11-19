# Grade 5 Numbers draft package: Nimo's Wacky Toybox

Development-only package for `G5-AREA-MAT-01` (`සංඛ්‍යා`) and universal skill `MAT-NUM`. Nimo shrinks
inside a giant toybox and directs the Great Toy Show. One skill per toy:

| Toy | Skill | What the child does |
|---|---|---|
| Toy Parade (the mission) | `G5-MAT-NUM-ORDER-01`, ordering four 4-digit numbers | Puts the four wind-up toys into the parade slots by their number badges, smallest or largest first. |
| Bead Bounce (training) | `G5-MAT-NUM-ABACUS-01`, building a number on a six-rod abacus | Drops beads on each rod; each bead plays a note. Help on a parade item shows every toy's number as bead columns to compare. |
| Costume Shop (training) | `G5-MAT-NUM-POSITION-01` and `G5-MAT-NUM-REPRESENTED-01`, the place and value of a digit | Dresses a digit in the hat of a place; the tag names the place or the value it gives the digit. |

Every episode starts on the parade, unsupported. A wrong order opens the multi-help loop: help on
the parade item is shown in Bead Bounce, and prerequisite repair (diagnosed as the place of a digit)
opens the Costume Shop. After the help is withdrawn, a fresh unsupported parade measures
Independence Gain.

The runtime definitions live in `backend/app/gamification/content/number_world.py`. The
misconception and scaffold catalogues keep their versions, so the research models read the same
codes as before; codes that only the earlier activities could produce simply no longer occur.

This package is blocked from production and general child delivery until curriculum,
Sinhala-language, educator, usage-rights, accessibility, answer-leakage, ethics/privacy,
model-safety, and release reviews are recorded. Artwork is in
`frontend/public/curriculum/game/G5-AREA-MAT-01/`.
