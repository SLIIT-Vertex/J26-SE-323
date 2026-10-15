"""Conventional non-learning policy required for the baseline experiment arm."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BaselinePolicyDecision:
    scaffold_id: str
    policy_version: str
    reason_code: str
    consumes_misconception_beliefs: bool = False
    authorizes_learning_from_ig: bool = False


@dataclass(frozen=True, slots=True)
class BaselinePolicyDefinition:
    policy_version: str
    selection_kind: str
    fixed_scaffold_id: str | None = None
    rule_version: str | None = None

    def __post_init__(self) -> None:
        if self.selection_kind not in {"fixed", "rule_based"}:
            raise ValueError("baseline selection_kind must be fixed or rule_based")
        if self.selection_kind == "fixed" and not self.fixed_scaffold_id:
            raise ValueError("fixed baseline policy requires fixed_scaffold_id")
        if self.selection_kind == "rule_based" and not self.rule_version:
            raise ValueError("rule-based baseline policy requires rule_version")


class ConventionalBaselinePolicy:
    """Select a fixed scaffold or an explicit rule result without beliefs or learning."""

    def __init__(self, contract: BaselinePolicyDefinition) -> None:
        self.contract = contract

    def select(self, *, rule_result_scaffold_id: str | None = None) -> BaselinePolicyDecision:
        if self.contract.selection_kind == "fixed":
            scaffold_id = self.contract.fixed_scaffold_id
            reason = "BASELINE_FIXED"
        else:
            scaffold_id = rule_result_scaffold_id
            reason = "BASELINE_RULE"
        if not scaffold_id:
            raise ValueError("baseline rule must return an approved scaffold ID")
        return BaselinePolicyDecision(
            scaffold_id=scaffold_id,
            policy_version=self.contract.policy_version,
            reason_code=reason,
        )
