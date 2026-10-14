"""Composition for the pilot shell. The stores are process-local and not for production."""

from app.gamification.application.session_play import SessionPlay
from app.gamification.application.template_selection import TemplateCompatibilityTable
from app.gamification.content.catalog import PilotContentCatalog
from app.gamification.content.loader import load_pilot_content_package
from app.gamification.domain.types import CatalogueVersion
from app.gamification.infrastructure.episode_memory import InMemoryUnitOfWork
from app.gamification.modeling.independence_gain.calculator import RawIndependenceGainCalculator
from app.gamification.modeling.misconception_inference.probabilistic_model import (
    ProbabilisticMisconceptionModel,
)
from app.gamification.modeling.support_selection.learned_policy import LinUCBPolicy
from app.gamification.modeling.support_selection.reference_policy import SafeSupportPolicy

from app.gamification.application.episode_use_cases import wire_episode_use_cases

NOT_FOR_PRODUCTION = "NOT_FOR_PRODUCTION"
PILOT_SKILL = "G5-MAT-C03-L01-O01"


def build_session_play() -> SessionPlay:
    package = load_pilot_content_package(allow_draft=True)
    catalog = PilotContentCatalog(package)
    unit = InMemoryUnitOfWork()
    cases = wire_episode_use_cases(
        uow=unit,
        episodes=unit.episodes,
        catalog=catalog,
        predictor=ProbabilisticMisconceptionModel(
            catalogue_version=catalog.misconception_catalogue_version(),
            error_likelihoods={"MAT-FRC-M06": {"MAT-FRC-M06": 4.0}},
            class_priors={
                "MAT-FRC-M05": 0.2,
                "MAT-FRC-M06": 0.5,
                "MAT-FRC-M07": 0.2,
                "unknown/other": 0.1,
            },
            abstain_threshold=0.99,
        ),
        selector=SafeSupportPolicy(
            catalogue_version=CatalogueVersion(catalog.support_catalogue_version()),
            reference_table=catalog.reference_policy_table(),
            bandit=LinUCBPolicy(),
            artifact_approved=False,
        ),
        calculator=RawIndependenceGainCalculator(),
        allow_draft=True,
        templates=TemplateCompatibilityTable(
            catalog.template_rules(), table_version=catalog.template_table_version()
        ),
    )
    return SessionPlay(
        cases=cases,
        episodes=unit.episodes,
        catalog=catalog,
        taxonomy_version=str(package.versions["skill_taxonomy_version"]),
    )
