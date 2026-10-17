# Grade 5 Sinhala-medium content slice

This package contains one atomic Mathematics skill: finding one half of an even discrete set.
The exact outcome is tied to the National Institute of Education Grade 5 Mathematics teacher's
guide, printed page 31 (PDF page 50), whose outcome is unnumbered. `G5-MAT-C03-L01-O01` is an
internal stable identifier, not an invented official outcome code.

All child-facing content is a researcher-authored draft. The source has been located and pinned,
but usage rights and the required curriculum, Sinhala-language, accessibility, and answer-leakage
reviews remain pending. The production loader therefore rejects this package. Answer keys are
kept in the server-only file and never occur in the public item schema.

Regenerate the manifest after an authorized content change:

```sh
backend/.venv/bin/python tools/gamification/datasets/build_grade5_sinhala_curriculum_slice.py
backend/.venv/bin/python tools/gamification/datasets/build_grade5_sinhala_curriculum_slice.py --check --verify-source
```
