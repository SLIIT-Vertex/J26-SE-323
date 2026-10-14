# Grade 5 draft mapping rules

These deterministic rules give the Sinhala-medium development build complete candidate coverage.
They do not constitute curriculum or expert approval. Every generated binding remains `draft`.

## Scope

The canonical Grade 5 package currently contains 548 candidates: Mathematics (113), Environmental
Studies (238), Sinhala (128), and English as a subject (69). All are in the Sinhala-medium Version 1
scope. No Tamil syllabus candidate is present.

## Mathematics

Mappings inherit the candidate's root competency:

| Stable skill | Root competencies |
| --- | --- |
| `MAT-NUM` | `C01`, `C04` |
| `APT-PAT` | `C02` number patterns |
| `MAT-FRC` | `C03`, `C05` |
| `MAT-OPS` | `C06`–`C10` |
| `MAT-LEN` | `C11` |
| `MAT-MAS` | `C12`, `C13` |
| `MAT-TIM` | `C14` |
| `MAT-MON` | `C15` |
| `MAT-GEO` | `C16`, `C17` |
| `APT-DIR` | `C18` directions |
| `MAT-DAT` | `C19` |

These mappings are generated with high confidence, but still require review before approval.

## Environmental Studies

The existing six stable skills are much broader than the syllabus outcomes, so all Environmental
Studies mappings are low confidence:

| Stable skill | Root competency rule |
| --- | --- |
| `ENV-BIO` | `C13`–`C40` |
| `ENV-PHY` | `C41`, `C46`–`C48`, `C64`–`C77` |
| `ENV-HLT` | `C49`–`C63` |
| `ENV-AGR` | `C78`–`C84` |
| `ENV-GEO` | `C95`–`C104` |
| `ENV-CIV` | all remaining Environmental Studies roots |

## Sinhala

Specific English-gloss keywords are applied first for idioms, tense, grammar, orthography,
vocabulary, and writing. Remaining candidates inherit a curriculum-level rule: `L05` maps to
vocabulary, `L06`/`L07`/`L09` to writing, `L10` to grammar, and the other levels to comprehension.
Keyword matches are high confidence; level and root fallbacks are medium confidence.

## English as a subject

All English candidates map to the stable `LAN-BIL` legacy node with medium confidence. This means
English subject content delivered with Sinhala instructions and support. It does not introduce
English-medium delivery, and the Tamil strand remains deferred.

## Review order

Review low-confidence Environmental Studies mappings first, then medium-confidence Sinhala and
English mappings. Change a generated rule or add a hand-authored override; do not edit the generated
binding file directly. Rebuild the package and retain unresolved mappings as `draft`.
