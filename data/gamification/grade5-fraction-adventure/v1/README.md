# Grade 5 Fractions draft package: Nimo's Magic Picture Book

Development-only Grade 5 Sinhala fractions package (`G5-AREA-MAT-05`, `භාග`, universal skill
`MAT-FRC`) derived from photographed textbook pages 69–70. It preserves the existing
`G5-MAT-C03-L01-O01` identity and adds provisional source-linked internal skills. Nothing in this
package is production-approved.

Nimo finds a huge blank picture book: colouring part of a page brings it to life, and Pipi the
paper bird asks for a fraction of each page.

| Skill | Played in |
|---|---|
| `G5-MAT-FRC-QUARTER-TABLE-01`, 1/4, 2/4 and 3/4 of a collection | Color Splash Comic (mission): the quarter garden |
| `G5-MAT-FRC-TENTHS-BUILD-01`, n/10 of a whole | Color Splash Comic (mission): the tenth panels |
| `G5-MAT-C03-L01-O01` and `G5-MAT-C03-L01-O02`, sharing into 2 or 4 equal groups | Sticker Sharing Party (help) |
| `G5-MAT-FRC-HALF-WHOLE-01` and `G5-MAT-FRC-QUARTER-WHOLE-01`, a half or a quarter of a shape | Fold & Pop (help) |

| Game | What the child does |
|---|---|
| Color Splash Comic | Every episode starts here, unsupported; each new page is the quarter garden or the tenth panels at random. The garden is three pages on the same flowers: paint 1/4, then 2/4, then 3/4 of them (the three painted counts are the quarter table). The panels page asks for n/10 of ten panels. Nothing on the page says right or wrong until the page is finished. |
| Sticker Sharing Party | The sticker friends each hold an envelope; the child drags (or taps) stickers in one at a time until every envelope has the same number. For a quarter-table item the child then gathers envelopes to show 1/4, 2/4 and 3/4. |
| Fold & Pop | One sheet of paper: each fold shows equal parts (a whole → halves → quarters, or a strip folded into ten); then the child paints the parts asked for and a paper butterfly pops out. |

A muddled page opens the multi-help loop (the server picks every help round). Help is played in the
game that matches the item: sharing and quarter-table items at the sticker party, shapes and tenths
in Fold & Pop. After the help is withdrawn, a fresh unsupported page of the same kind measures
Independence Gain. The scored answers are the same as before.

The runtime definitions live in `backend/app/gamification/content/fraction_adventure.py`. The
misconception and scaffold catalogues keep their versions; reading shaded tenths
(`G5-MAT-FRC-TENTHS-READ-01`) is no longer played.

Public manifests expose only learner-visible structure. Correct responses and support solutions
stay server-side and may appear only during active answer-revealing support before complete
withdrawal. Artwork is in `frontend/public/curriculum/game/G5-AREA-MAT-05/`; `kit/` holds
open-licence (CC0) pieces: the sticker friends, paint splats, sparkles, paper texture and the
sticker star.
