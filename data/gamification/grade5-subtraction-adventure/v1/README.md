# Grade 5 Subtraction draft package: Nimo's Midnight Monster Café

Development-only package for `G5-AREA-MAT-04` (`අඩු කිරීම`) and universal skill `MAT-OPS`. Nimo is
the chef for one night at a café that only opens at midnight; the customers are little monsters,
and every order asks what is left after they eat.

| Skill | Played as |
|---|---|
| `G5-MAT-C07-L01-O01`, one exchange | A café order (mission) |
| `G5-MAT-C07-L01-O02`, two exchanges (repository draft mapping) | A café order (mission) |
| `G5-MAT-SUB-DIFF-BETWEEN-01`, the difference of two orders | A two-monster order (mission) |
| `G5-MAT-SUB-HOW-MANY-MORE-01`, how many more one monster ate | A two-monster order (mission) |
| `G5-MAT-SUB-NO-REGROUP-01`, no exchange | Help only (where prerequisite repair lands) |

| Game | When | What the child does |
|---|---|---|
| Monster Order Mayhem (the mission) | Every episode starts here, unsupported; each new order picks a mission skill at random | On the order board the child opens a snack pack above a column where there are too few (a borrow mark), then fills in what is left column by column. For a two-monster order the child first puts the bigger order on top. Nothing is checked until the order is sent. |
| Magical Snack Swap (training) | Most help rounds | The snacks sit in trays of boxes, packets and singles. The order is given tray by tray; a tray with too few needs a pack opened from the tray on its left, which bursts into ten. What stays in the trays is the answer. |
| Feed the Fluffballs (training) | The plainest help, and no-exchange items | One column at a time the little monsters eat that column's snacks one by one; when the plate is short, a pack from the next column bursts into ten. What is left becomes that column's digit. |

A muddled order opens the multi-help loop (the server picks every help round). After the help is
withdrawn, a fresh unsupported order of the same kind measures Independence Gain. The scored answer
is the same as before: the result digits and the exchanges for a café order, and the chosen bigger
amount and the result for a two-monster order.

The runtime definitions live in `backend/app/gamification/content/subtraction_adventure.py`. The
misconception and scaffold catalogues keep their versions; the expanded-form skill is no longer
played. The photographed page does not supply a complete two-exchange worked example, so
`G5-MAT-C07-L01-O02` stays a repository draft mapping.

This package is blocked from production and general child delivery until curriculum,
Sinhala-language, educator, usage-rights, accessibility, answer-leakage, ethics/privacy,
model-safety, and release reviews are recorded. Artwork is in
`frontend/public/curriculum/game/G5-AREA-MAT-04/`.
