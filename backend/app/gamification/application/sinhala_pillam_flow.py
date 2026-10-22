"""Durable G5-AREA-SIN-01 Pillam Journey profile on the shared Sinhala package flow."""

from __future__ import annotations

from app.gamification.application.sinhala_package_flow import SinhalaPackageFlow
from app.gamification.content import sinhala_pillam


class SinhalaPillamFlow(SinhalaPackageFlow):
    experience_id = "sinhala_pillam_journey"
    contract_version = "sinhala-pillam-learning-flow-v1"
    context_version = "g5-sin-pillam-context-v1"
    measurement_version = "sinhala-pillam-independence-measurement-v1"
    missing_skill_error = "SINHALA_PILLAM_SKILL_NOT_FOUND"
    episode_type_error = "SINHALA_PILLAM_EPISODE_REQUIRED"
    operation_prefix = "sinhala_pillam"


SinhalaPillamFlow.bind(sinhala_pillam)
