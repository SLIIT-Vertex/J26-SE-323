"""Append-only SQL persistence for deterministic Independence Gain measurements."""

from sqlalchemy.orm import Session

from app.gamification.infrastructure.db.models import (
    AuthoritativeAttemptV3Model,
    IndependenceMeasurementV3Model,
    ItemPresentationV3Model,
    ProbeReservationV3Model,
    ScaffoldExposureRecordV3Model,
    SupportWithdrawalConfirmationV3Model,
)
from app.gamification.modeling.independence_gain.phase3 import (
    IndependenceMeasurement,
    MeasurementInput,
    Phase3Error,
)


class SqlAlchemyPhase3MeasurementStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_authoritative_input(self, data: MeasurementInput) -> None:
        for row in data.reservations:
            self._add_once(
                ProbeReservationV3Model,
                row.reservation_id,
                id=row.reservation_id,
                episode_id=row.episode_id,
                learner_id=row.learner_id,
                item_revision_id=row.item_revision_id,
                parallel_family_id=row.parallel_family_id,
                measurement_role=row.role.value,
                reservation_version=row.reservation_version,
                reserved_at=row.reserved_at,
                expires_at=row.expires_at,
                used_at=row.used_at,
                contamination_sources_json=list(row.contamination_sources),
            )
        for row in data.presentations:
            self._add_once(
                ItemPresentationV3Model,
                row.presentation_id,
                id=row.presentation_id,
                episode_id=row.episode_id,
                learner_id=row.learner_id,
                item_revision_id=row.item_revision_id,
                skill_id=row.skill_id,
                parallel_family_id=row.parallel_family_id,
                equivalence_version=row.equivalence_version,
                measurement_role=row.role.value,
                assistance_state=row.assistance_state.value,
                sequence_no=row.sequence,
                reservation_id=row.reservation_id,
                created_at=row.created_at,
            )
        for row in data.scaffold_exposures:
            self._add_once(
                ScaffoldExposureRecordV3Model,
                row.exposure_id,
                id=row.exposure_id,
                episode_id=row.episode_id,
                scaffold_revision_id=row.scaffold_revision_id,
                rendered_step_ids_json=list(row.rendered_step_ids),
                answer_revealing=row.answer_revealing,
                started_at=row.started_at,
                completed_at=row.completed_at,
            )
        if data.withdrawal is not None:
            row = data.withdrawal
            self._add_once(
                SupportWithdrawalConfirmationV3Model,
                row.confirmation_id,
                id=row.confirmation_id,
                episode_id=row.episode_id,
                exposure_id=row.exposure_id,
                all_support_removed=row.all_support_removed,
                answer_revealing_state_cleared=row.answer_revealing_state_cleared,
                client_confirmed_at=row.client_confirmed_at,
                server_verified_at=row.server_verified_at,
            )
        for row in data.attempts:
            self._add_once(
                AuthoritativeAttemptV3Model,
                row.attempt_id,
                id=row.attempt_id,
                presentation_id=row.presentation_id,
                item_revision_id=row.item_revision_id,
                measurement_role=row.role.value,
                assistance_state=row.assistance_state.value,
                earned_score=row.earned_score,
                maximum_score=row.maximum_score,
                rubric_version=row.rubric_version,
                scoring_version=row.scoring_version,
                server_authoritative=row.server_authoritative,
                idempotency_key=row.idempotency_key,
                scored_at=row.scored_at,
            )
        self._session.flush()

    def add(self, measurement: IndependenceMeasurement) -> IndependenceMeasurementV3Model:
        existing = self._session.get(IndependenceMeasurementV3Model, measurement.measurement_id)
        values = _values(measurement)
        if existing is not None:
            stored = _row_values(existing)
            comparable_values = dict(values)
            comparable_values["calculated_at"] = values["calculated_at"].replace(tzinfo=None)
            comparable_stored = dict(stored)
            comparable_stored["calculated_at"] = stored["calculated_at"].replace(tzinfo=None)
            if comparable_stored != comparable_values:
                differing = tuple(
                    key for key in values if comparable_stored[key] != comparable_values[key]
                )
                raise Phase3Error(f"MEASUREMENT_IDEMPOTENCY_CONFLICT:{','.join(differing)}")
            return existing
        row = IndependenceMeasurementV3Model(**values)
        self._session.add(row)
        self._session.flush()
        return row

    def _add_once(self, model: type, identity: object, **values: object) -> None:
        existing = self._session.get(model, identity)
        if existing is None:
            self._session.add(model(**values))
            return
        differing = tuple(
            key
            for key, value in values.items()
            if _comparable(getattr(existing, key)) != _comparable(value)
        )
        if differing:
            raise Phase3Error(f"AUTHORITATIVE_RECORD_CONFLICT:{','.join(differing)}")


def _comparable(value: object) -> object:
    if hasattr(value, "tzinfo") and hasattr(value, "replace"):
        return value.replace(tzinfo=None)
    return value


def _values(measurement: IndependenceMeasurement) -> dict[str, object]:
    return {
        "id": measurement.measurement_id,
        "episode_id": measurement.episode_id,
        "decision_id": measurement.decision_id,
        "before_presentation_ids_json": [str(value) for value in measurement.before.presentation_ids],
        "after_presentation_ids_json": [str(value) for value in measurement.after.presentation_ids],
        "before_earned": measurement.before.earned,
        "before_maximum": measurement.before.maximum,
        "after_earned": measurement.after.earned,
        "after_maximum": measurement.after.maximum,
        "raw_independence_gain": measurement.raw_independence_gain,
        "percentage_point_value": measurement.percentage_point_value,
        "formula_version": measurement.formula_version,
        "scoring_versions_json": list(measurement.scoring_versions),
        "rubric_versions_json": list(measurement.rubric_versions),
        "equivalence_version": measurement.equivalence_version,
        "valid": measurement.valid,
        "exclusion_reasons_json": list(measurement.exclusion_reasons),
        "policy_update_status": measurement.policy_update_status.value,
        "measurement_version": measurement.measurement_version,
        "calculated_at": measurement.calculated_at,
    }


def _row_values(row: IndependenceMeasurementV3Model) -> dict[str, object]:
    return {
        "id": row.id,
        "episode_id": row.episode_id,
        "decision_id": row.decision_id,
        "before_presentation_ids_json": row.before_presentation_ids_json,
        "after_presentation_ids_json": row.after_presentation_ids_json,
        "before_earned": row.before_earned,
        "before_maximum": row.before_maximum,
        "after_earned": row.after_earned,
        "after_maximum": row.after_maximum,
        "raw_independence_gain": row.raw_independence_gain,
        "percentage_point_value": row.percentage_point_value,
        "formula_version": row.formula_version,
        "scoring_versions_json": row.scoring_versions_json,
        "rubric_versions_json": row.rubric_versions_json,
        "equivalence_version": row.equivalence_version,
        "valid": row.valid,
        "exclusion_reasons_json": row.exclusion_reasons_json,
        "policy_update_status": row.policy_update_status,
        "measurement_version": row.measurement_version,
        "calculated_at": row.calculated_at,
    }
