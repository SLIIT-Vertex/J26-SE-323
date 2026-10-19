# Grade 5 Addition Adventure draft package

Development-only package for `G5-AREA-MAT-02` (`එකතු කිරීම`) and universal skill `MAT-OPS`.
The three carrying targets `G5-MAT-C06-L01-O01` through `O03` are linked directly to the draft
curriculum trace on page 12. Mental addition, running totals, contextual addition, and the two
table-reading targets are provisional activity mappings from pages 62–65 and require
educator and curriculum review; they are not promoted to verified outcomes.

The five mobile games preserve the photographed textbook representations: quick quantity facts,
the 82-start running-total trail, place-aligned column addition and carrying, three-addend story
contexts, and semantic seedling/school tables for totals, differences, and greatest row totals.
School-name transcriptions remain explicitly pending human Sinhala-language review. Each activity
has a deterministic support route that starts with its defined default and escalates through an
exact failed-task visual cue, worked visual demonstration, and explicit guided steps. Only a valid,
unsupported post-withdrawal response can update that skill's future support preference.

The runtime definitions live in
`backend/app/gamification/content/addition_adventure.py`. The package includes the distinct
versioned addition misconception catalogue and the three-scaffold catalogue. It preserves raw
post-withdrawal Independence Gain as the only proposed-policy reward and keeps baseline selection
isolated from Model 1.

This package is blocked from production and general child delivery until curriculum,
Sinhala-language, educator, usage-rights, accessibility, answer-leakage, ethics/privacy,
model-safety, and release reviews are recorded. Existing repository-supplied artwork is reused
from `frontend/public/curriculum/game/G5-AREA-MAT-02/`; synthetic tests validate mechanics,
not curriculum correctness or research readiness.
