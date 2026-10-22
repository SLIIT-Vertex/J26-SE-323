"""One vocabulary for the judge-facing Research view. Raw codes stay in disclosures."""

TYPE_NAMES = {
    "visual_guidance": "Visual hint",
    "step_by_step_guidance": "Question-by-question guidance",
    "conceptual_reexplanation": "Explain the idea again",
    "simpler_same_game": "Easier version first",
    "prerequisite_repair": "Practise the skill underneath",
    "worked_parallel_example": "Watch a solved example",
}
FAMILY_NAMES = {
    "representation": "Misread the picture or layout",
    "procedure": "Missed a step",
    "relation": "Mixed up two ideas",
    "prerequisite": "An earlier skill is missing",
    # Model 1 abstained: too little or too uncertain evidence to name a reason.
    "unclear": "Reason not identified",
}
STATUS_NAMES = {
    "completed": "Finished",
    "invalidated": "Left out of the results",
    "awaiting_before": "Ready for the first try",
    "before_presented": "Ready for the first try",
    "opened": "Ready to begin",
    "support_active": "Trying with help",
    "support_complete": "Help finished",
    "support_withdrawn": "Help removed",
    "after_presented": "Trying alone",
    "awaiting_after": "Ready to try alone",
    "awaiting_withdrawal": "Removing the help",
    "withdrawal_pending": "Removing the help",
    "authorized_delayed": "The Contextual Support Selection learned from this fair test",
    "not_authorized_baseline": "The fixed order stays unchanged",
    "not_authorized_invalid": "This was not a fair test, so it cannot change the help choice",
    "not_authorized_no_support": "Right first time; no help was needed",
    "not_authorized_incomplete": "Waiting for the child to finish",
    "not_authorized_pending": "Waiting for the child to finish",
    "succeeded": "Managed it with help",
    "supported_success": "Managed it with help",
    "failed": "This help was not enough",
    "order_exhausted": "Every available help was tried",
    "viewed": "Watched the demonstration",
    "support_viewed": "Watched the demonstration",
    "valid": "Passed the fair-test checks",
    "invalid": "Left out of the results",
    "not_applicable_no_support": "No help was needed",
    "AVAILABLE": "A recent reading was available",
    "UNCERTAIN": "The reading was not clear enough",
    "NOT_FOUND": "No reading was available",
    "STALE": "The reading was too old or from another session",
    "PROVIDER_UNAVAILABLE": "The reading could not be fetched",
    "calm": "Calm and focused",
    "confused": "A bit confused",
    "disengaged": "Losing focus",
    "not_available": "No fresh reading",
    "uncertain": "The reading was not clear enough",
    "engaged": "Focused",
    "not_confused": "Calm and focused",
    "request_reengagement_support": "A short success may help bring focus back",
    "request_scaffolding": "More guidance may help",
    "none": "No extra help needed",
    "monitor": "Keep watching for a clearer pattern",
}
MODE_NAMES = {
    "baseline_fixed_order": "The fixed order",
    "model1_reason_lead": "The likely reason guided the choice",
    "learned_post_withdrawal_preference": "This child's past results guided the choice",
    "model1_reason_lead_unrenderable_fallback": "The first available help was used",
    "learning_state_lead": "How the child seemed during this game guided the choice",
}
EXCLUSIONS = {
    "early_exit": "The child left before finishing",
    "EARLY_EXIT": "The child left before finishing",
    "support_not_withdrawn": "Help had not been fully removed",
    "probe_exposed": "The fresh question had already been seen",
    "parallel_family_mismatch": "The questions did not test the same skill",
    "answer_leakage": "An answer was visible before the fresh try",
}


def plain_status(value: object) -> str:
    if value is None:
        return "Waiting for the next step"
    return STATUS_NAMES.get(str(value), "This step needs a technical review")


def reason_name(code: object, subject: str = "MAT") -> str:
    """Readable names for chart labels and recorded mistake summaries."""
    text = str(code or "")
    named = {
        # The mistake matched no known pattern in the area's catalogue.
        "unknown_or_other": "Reason not identified",
        "wrong_direction": "Used the wrong direction",
        "origin_not_retained": "Forgot the starting place",
        "destination_ignored": "Missed the destination",
        "incorrect_arithmetic": "A calculation mistake",
        "incorrect_subtraction": "A subtraction mistake",
        "counted_labels_not_intervals": "Counted the marks instead of the spaces",
        "exchanged_ten_counted_as_one": "Counted an exchanged ten as one",
        "first_visible_digit_only": "Used only the first visible digit",
        "counts_places_from_wrong_direction": "Counted places from the wrong side",
        "borrow_not_applied": "Missed an exchange from the next column",
        "incorrect_conversion_factor": "Used the wrong number when changing units",
        "invalid_interaction": "The answer could not be checked",
    }
    if text in named:
        return named[text]
    if not text or text in {"None", "unknown", "other"}:
        return "Reason not identified"
    if "_vs_" in text:
        return "Mixed up " + text.removesuffix("_confusion").replace("_vs_", " and ").replace(
            "_", " "
        )
    words = (
        text.replace("_", " ")
        .replace("omitted", "missed")
        .replace("denominator", "bottom number")
        .replace("numerator", "top number")
        .replace("prerequisite", "earlier skill")
        .replace("semantic", "meaning")
        .replace("exemplar", "example")
    )
    return words[:1].upper() + words[1:]


EXCLUSIONS.update(
    {
        "SUPPORT_NOT_WITHDRAWN": "Help had not been fully removed",
        "WITHDRAWAL_NOT_VERIFIED": "Help removal could not be confirmed",
        "SCORING_VERSION_MISMATCH": "The questions used different scoring rules",
        "ASSISTANCE_CONTAMINATION": "Outside help affected an independent try",
        "AFTER_ITEM_NOT_UNSUPPORTED": "The fresh question still had help",
        "SKILL_MISMATCH": "The two questions tested different skills",
        "INCOMPATIBLE_PARALLEL_FAMILY": "The questions did not have a matching difficulty",
        "AFTER_ITEM_NOT_FRESH": "The fresh question had already been seen",
        "AFTER_ITEM_SEEN_DURING_SUPPORT": "The fresh question appeared during help",
        "PRIOR_PROBE_EXPOSURE": "The child had already seen the reserved fresh question",
        "CHILD_EXITED": "The child left before finishing",
        "EPISODE_EXITED": "The child left before finishing",
    }
)
STATUS_NAMES.update(
    {
        "request_tutor_support": "More guidance may help",
        "collect_more_evidence": "Waiting for a clearer pattern",
        "no_support_needed": "No extra help needed",
        "low_confusion": "Calm and focused",
        "high_confusion": "A bit confused",
        "low_disengagement": "Focused",
        "high_disengagement": "Losing focus",
    }
)

STATUS_NAMES.update(
    {
        "no_confusion": "Calm and focused",
        "transient_confusion": "A bit confused",
        "productive_confusion": "Working through a confusing idea",
        "intervention_worthy_confusion": "Needs more guidance",
        "recovering_from_confusion": "Becoming clearer",
        "persistent_disengagement": "Losing focus",
        "transient_disengagement": "Briefly distracted",
        "recovering_engagement": "Becoming focused again",
    }
)
