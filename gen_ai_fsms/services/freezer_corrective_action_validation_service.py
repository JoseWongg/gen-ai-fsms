from typing import Literal

from pydantic import BaseModel, Field


FreezerFoodDecision = Literal[
    "discarded",
    "moved_to_compliant_freezer",
]

FreezerIssueType = Literal[
    "transient",
    "maintenance",
]

CorrectiveActionIssueKind = Literal[
    "missing",
    "contradiction",
]


COMPLIANT_FREEZER_THRESHOLD_C = -18.0


class FreezerCorrectiveActionState(BaseModel):
    """
    Accumulated freezer corrective-action facts.

    All fields are optional because the workflow collects information over
    several turns. The validator decides which fields are required based on
    the branch of the corrective-action narrative already established.

    Important:
    - destination_freezer_temperature_c is optional.
    - food_returned_to_freezer is optional.
    - Optional details are only validated if the user volunteers them.
    """

    food_checked_for_thawing_signs: bool | None = None
    thawing_signs_present: bool | None = None
    food_decision: FreezerFoodDecision | None = None

    destination_freezer_temperature_c: float | None = None

    freezer_issue_type: FreezerIssueType | None = None
    transient_issue_description: str | None = None
    corrective_action_taken: str | None = None
    follow_up_temperature_c: float | None = None

    food_returned_to_freezer: bool | None = None

    maintenance_logged: bool | None = None
    maintenance_reference: str | None = None


class FreezerCorrectiveActionIssue(BaseModel):
    kind: CorrectiveActionIssueKind
    field: str
    message: str


class FreezerCorrectiveActionValidationResult(BaseModel):
    issues: list[FreezerCorrectiveActionIssue] = Field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.issues) == 0


def validate_freezer_corrective_action_state(
    state: FreezerCorrectiveActionState,
) -> FreezerCorrectiveActionValidationResult:
    """
    Validate the current freezer corrective-action state.

    Business logic:
    - Frozen food affected by a freezer temperature incident must be checked
      for signs of thawing.
    - If food shows signs of thawing, it must be discarded.
    - If food does not show signs of thawing, it may be moved to compliant
      freezer equipment.
    - Destination freezer details are not required, but contradictory
      volunteered details are still flagged.
    - For the faulty freezer itself, the issue must either be resolved as a
      temporary issue with a compliant follow-up temperature, or logged for
      maintenance/repair.
    """

    issues: list[FreezerCorrectiveActionIssue] = []

    def missing(field: str, message: str) -> None:
        issues.append(
            FreezerCorrectiveActionIssue(
                kind="missing",
                field=field,
                message=message,
            )
        )

    def contradiction(field: str, message: str) -> None:
        issues.append(
            FreezerCorrectiveActionIssue(
                kind="contradiction",
                field=field,
                message=message,
            )
        )

    # 1. The first required branch is whether affected frozen food was checked.
    if state.food_checked_for_thawing_signs is None:
        missing(
            "food_checked_for_thawing_signs",
            "Confirm whether the food in the freezer was checked for signs of thawing.",
        )
        return FreezerCorrectiveActionValidationResult(issues=issues)

    if state.food_checked_for_thawing_signs is False:
        contradiction(
            "food_checked_for_thawing_signs",
            "Frozen food affected by a freezer temperature incident must be checked for signs of thawing before the corrective action can be recorded as complete.",
        )
        return FreezerCorrectiveActionValidationResult(issues=issues)

    # 2. Once checked, the thawing result is required.
    if state.thawing_signs_present is None:
        missing(
            "thawing_signs_present",
            "Confirm whether the frozen food showed signs of thawing.",
        )
        return FreezerCorrectiveActionValidationResult(issues=issues)

    # 3. The food decision is required once thawing status is known.
    if state.food_decision is None:
        missing(
            "food_decision",
            "Confirm whether the food was discarded or moved to compliant freezer equipment.",
        )

    if (
        state.thawing_signs_present is True
        and state.food_decision == "moved_to_compliant_freezer"
    ):
        contradiction(
            "food_decision",
            "Frozen food that shows signs of thawing must be discarded. It cannot be moved to another freezer and kept.",
        )

    # Optional volunteered detail only.
    # Do not require the destination freezer temperature.
    # But if the user states it and it is not compliant, flag it.
    if (
        state.food_decision == "moved_to_compliant_freezer"
        and state.destination_freezer_temperature_c is not None
        and state.destination_freezer_temperature_c > COMPLIANT_FREEZER_THRESHOLD_C
    ):
        contradiction(
            "destination_freezer_temperature_c",
            "The food was described as moved to a freezer warmer than -18°C. Food can only be moved to compliant freezer equipment.",
        )

    # 4. The faulty freezer itself must have a resolution path.
    if state.freezer_issue_type is None:
        missing(
            "freezer_issue_type",
            "Confirm whether the freezer issue was corrected as a temporary issue or logged for maintenance/repair.",
        )
        return FreezerCorrectiveActionValidationResult(issues=issues)

    if state.freezer_issue_type == "transient":
        if state.corrective_action_taken is None:
            missing(
                "corrective_action_taken",
                "Describe the corrective action taken to correct the freezer issue.",
            )

        if state.follow_up_temperature_c is None:
            missing(
                "follow_up_temperature_c",
                "Provide the follow-up freezer temperature after the corrective action was taken.",
            )
        elif state.follow_up_temperature_c > COMPLIANT_FREEZER_THRESHOLD_C:
            if state.food_returned_to_freezer is True:
                contradiction(
                    "food_returned_to_freezer",
                    "Food cannot be returned to the freezer because the follow-up temperature was still warmer than -18°C.",
                )
            else:
                contradiction(
                    "freezer_issue_type",
                    "The freezer was still warmer than -18°C after the follow-up check, so it cannot be recorded as corrected by a temporary action. Confirm whether it was logged for maintenance/repair.",
                )

    if state.freezer_issue_type == "maintenance":
        if state.maintenance_logged is None:
            missing(
                "maintenance_logged",
                "Confirm whether the freezer was logged for maintenance or repair.",
            )
        elif state.maintenance_logged is False:
            contradiction(
                "maintenance_logged",
                "A freezer issue classified as requiring maintenance or repair must be logged for maintenance or repair.",
            )

        if state.food_returned_to_freezer is True:
            contradiction(
                "food_returned_to_freezer",
                "Food cannot be returned to a freezer that has been logged for maintenance instead of being confirmed as compliant.",
            )

    return FreezerCorrectiveActionValidationResult(issues=issues)
