from typing import Literal

from pydantic import BaseModel, Field


FoodType = Literal["fish", "other"]
OutOfRangeDuration = Literal["le_4h", "gt_4h", "uncertain"]
FoodDecision = Literal["discarded", "kept_moved_to_compliant_fridge"]
FridgeIssueType = Literal["transient", "maintenance"]
CorrectiveActionIssueKind = Literal["missing", "contradiction"]


FOOD_THRESHOLD_FISH_C = 4.0
FOOD_THRESHOLD_OTHER_C = 8.0
COMPLIANT_DESTINATION_FRIDGE_THRESHOLD_C = 5.0
COMPLIANT_FOLLOW_UP_FRIDGE_THRESHOLD_C = 5.0


class FridgeCorrectiveActionState(BaseModel):
    """
    Accumulated corrective-action facts.

    All fields are optional because the workflow collects information over
    several turns. The validator decides which fields are required based on the
    branch of the corrective-action narrative already established.

    Important:
    - destination_fridge_temperature_c is optional.
    - food_returned_to_fridge is optional.
    - Optional details are only validated if the user volunteers them.
    """

    food_probed: bool | None = None
    food_type: FoodType | None = None
    food_temperature_c: float | None = None

    out_of_range_duration: OutOfRangeDuration | None = None
    food_decision: FoodDecision | None = None
    destination_fridge_temperature_c: float | None = None

    fridge_issue_type: FridgeIssueType | None = None

    transient_issue_description: str | None = None
    corrective_action_taken: str | None = None
    follow_up_temperature_c: float | None = None

    food_returned_to_fridge: bool | None = None

    maintenance_logged: bool | None = None
    maintenance_reference: str | None = None

    @property
    def food_threshold_c(self) -> float | None:
        if self.food_type == "fish":
            return FOOD_THRESHOLD_FISH_C

        if self.food_type == "other":
            return FOOD_THRESHOLD_OTHER_C

        return None

    @property
    def food_in_safe_range(self) -> bool | None:
        if self.food_temperature_c is None or self.food_threshold_c is None:
            return None

        return self.food_temperature_c <= self.food_threshold_c


class FridgeCorrectiveActionIssue(BaseModel):
    kind: CorrectiveActionIssueKind
    field: str
    message: str


class FridgeCorrectiveActionValidationResult(BaseModel):
    issues: list[FridgeCorrectiveActionIssue] = Field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.issues) == 0


def validate_fridge_corrective_action_state(
    state: FridgeCorrectiveActionState,
) -> FridgeCorrectiveActionValidationResult:
    """
    Validate the current corrective-action state.

    Business logic:
    - Food must be probed.
    - If food is within the relevant food-temperature threshold, no discard/move
      decision is required.
    - If food is outside the relevant food-temperature threshold, the duration
      outside safe range must be known.
    - Food outside the safe range may only be kept if it was outside range for
      no more than four hours and moved to a compliant fridge.
    - Food outside range for more than four hours, or where the duration is
      uncertain, must be discarded.
    - Destination fridge details are not required, but contradictory volunteered
      details are still flagged.
    - For the faulty fridge itself, the issue must be either resolved as a
      temporary issue with a compliant follow-up temperature, or logged for
      maintenance/repair.
    """

    issues: list[FridgeCorrectiveActionIssue] = []

    def missing(field: str, message: str) -> None:
        issues.append(
            FridgeCorrectiveActionIssue(
                kind="missing",
                field=field,
                message=message,
            )
        )

    def contradiction(field: str, message: str) -> None:
        issues.append(
            FridgeCorrectiveActionIssue(
                kind="contradiction",
                field=field,
                message=message,
            )
        )

    # 1. Food probing is the first required branch.
    if state.food_probed is None:
        missing(
            "food_probed",
            "Confirm whether the food inside the fridge was probed with a thermometer.",
        )
        return FridgeCorrectiveActionValidationResult(issues=issues)

    if state.food_probed is False:
        contradiction(
            "food_probed",
            "The food must be probed with a thermometer before the corrective action can be recorded as complete.",
        )
        return FridgeCorrectiveActionValidationResult(issues=issues)

    # 2. Food type and probe temperature are needed to decide whether the food
    # was actually outside the relevant safe range.
    if state.food_type is None:
        missing(
            "food_type",
            "Confirm whether there was any fish in the affected fridge.",
        )

    if state.food_temperature_c is None:
        missing(
            "food_temperature_c",
            "Provide the temperature recorded when the food was probed.",
        )

    if state.food_type is None or state.food_temperature_c is None:
        return FridgeCorrectiveActionValidationResult(issues=issues)

    # 3. If food was outside its safe range, enforce the four-hour rule.
    if state.food_in_safe_range is False:
        if state.out_of_range_duration is None:
            missing(
                "out_of_range_duration",
                "Confirm whether the food was outside the safe range for no more than four hours, more than four hours, or whether the duration was uncertain.",
            )

        if state.food_decision is None:
            missing(
                "food_decision",
                "Confirm whether the food was discarded or moved to another compliant fridge.",
            )

        if (
            state.out_of_range_duration in ("gt_4h", "uncertain")
            and state.food_decision == "kept_moved_to_compliant_fridge"
        ):
            contradiction(
                "food_decision",
                "Food that was outside the safe range for more than four hours, or where the duration is uncertain, cannot be kept. It must be discarded.",
            )

        # Optional volunteered detail only.
        # Do not require the destination fridge temperature.
        # But if the user states it and it is not compliant, flag it.
        if (
            state.food_decision == "kept_moved_to_compliant_fridge"
            and state.destination_fridge_temperature_c is not None
            and state.destination_fridge_temperature_c
            > COMPLIANT_DESTINATION_FRIDGE_THRESHOLD_C
        ):
            contradiction(
                "destination_fridge_temperature_c",
                "The food was described as moved to a fridge above 5°C. Food can only be moved to a compliant fridge.",
            )

    # 4. The faulty fridge itself must have a resolution path.
    if state.fridge_issue_type is None:
        missing(
            "fridge_issue_type",
            "Confirm whether the fridge issue was corrected as a temporary issue or logged for maintenance/repair.",
        )
        return FridgeCorrectiveActionValidationResult(issues=issues)

    if state.fridge_issue_type == "transient":
        if state.corrective_action_taken is None:
            missing(
                "corrective_action_taken",
                "Describe the corrective action taken to correct the fridge issue.",
            )

        if state.follow_up_temperature_c is None:
            missing(
                "follow_up_temperature_c",
                "Provide the follow-up fridge temperature after the corrective action was taken.",
            )
        elif (
            state.follow_up_temperature_c
            > COMPLIANT_FOLLOW_UP_FRIDGE_THRESHOLD_C
        ):
            if state.food_returned_to_fridge is True:
                contradiction(
                    "food_returned_to_fridge",
                    "Food cannot be returned to the fridge because the follow-up temperature was still above 5°C.",
                )
            else:
                contradiction(
                    "fridge_issue_type",
                    "The fridge was still above 5°C after the follow-up check, so it cannot be recorded as corrected by a temporary action. Confirm whether it was logged for maintenance/repair.",
                )

    if state.fridge_issue_type == "maintenance":
        if state.maintenance_logged is None:
            missing(
                "maintenance_logged",
                "Confirm whether the fridge was logged for maintenance or repair.",
            )
        elif state.maintenance_logged is False:
            contradiction(
                "maintenance_logged",
                "A fridge issue classified as requiring maintenance or repair must be logged for maintenance or repair.",
            )

        if state.food_returned_to_fridge is True:
            contradiction(
                "food_returned_to_fridge",
                "Food cannot be returned to a fridge that has been logged for maintenance instead of being confirmed as compliant.",
            )

    return FridgeCorrectiveActionValidationResult(issues=issues)
