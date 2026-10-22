"""Printable progress, derived only from completed human-played games."""

from collections import Counter
from pathlib import Path
from uuid import UUID

from app.gamification.application.research_dashboard.explain import area_title, resolved_area
from app.gamification.infrastructure.db.research_dashboard_reader import (
    SqlAlchemyResearchDashboardReader,
)


def checklist(session, orchestrator, learner: UUID) -> str:
    counts = Counter(
        resolved_area(run["state"])
        for run in SqlAlchemyResearchDashboardReader(session).runs(learner)
        if run["status"] == "completed" and not run["state"].get("seed_source")
    )
    lines = [
        "# Demo play checklist",
        "",
        f"Learner: {learner}",
        "",
        "Play one or two games per area in the normal app. Follow the help and then try alone.",
        "Only completed, human-played games count below. A tick means at least one is finished.",
        "",
    ]
    for area, flow in sorted(orchestrator._area_flows.items()):
        if not getattr(flow, "runs_support_loop", False):
            continue
        skill_id = next(iter(flow.skills))
        skill = flow.skills[skill_id]
        skill_name = getattr(skill, "name_en", None) or getattr(skill, "name_si", None) or skill_id
        lines.append(
            f"- [{'x' if counts[area] else ' '}] {area_title(area)} — {skill_name}; suggested skill `{skill_id}`; {counts[area]} completed."
        )
    return "\n".join(lines) + "\n"


def save_checklist(session, orchestrator, learner, output):
    content = checklist(session, orchestrator, learner)
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(content)
    return content
