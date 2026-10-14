# Grade 5 curriculum game dataset v2.0.0

This is the canonical package. It contains loss-aware source evidence, explicit curriculum and
skill-candidate mappings, model-facing support and verification candidates, QA data, formal
schemas, integrity validation and a machine-readable readiness report.

All skill, misconception, support and verification records remain candidates unless their explicit
approval fields say otherwise. Source workbook notes and instructions are stored as reference text
with `instruction_authority: none`; they are never executed as package-building instructions.

The package is suitable for engineering and review workflows. It is not approved for child-facing
delivery, research claims or learned-model activation. See `readiness_report.json` for current gates.

Curriculum sources, nodes and terms are not stored here. They are shared with the Adaptive Tutor
in `data/curriculum/grade5-curriculum-trace/v1/`. `curriculum_node_id` and `source_id` values
in this package refer to that shared package, whose version and manifest hash are recorded in
`manifest.json` under `curriculum_trace_package`.
