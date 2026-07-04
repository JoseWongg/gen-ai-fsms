from typing import Literal

from pydantic import BaseModel, Field


OutOfRangeDuration = Literal["le_4h", "gt_4h", "uncertain"]
FoodDecision = Literal["discarded", "kept_moved_to_compliant_fridge"]
FridgeIssueType = Literal["transient", "maintenance"]
CorrectiveActionIssueKind = Literal["missing", "contradiction"]

FOOD_THRESHOLD_FISH_C = 5.0
FOOD_THRESHOLD_OTHER_C = 8.0
COMPLIANT_DESTINATION_FRIDGE_THRESHOLD_C = 5.0
COMPLIANT_FOLLOW_UP_FRIDGE_THRESHOLD_C = 5.0


class FridgeCorrectiveActionState(BaseModel):
    """
    Accumulated corrective-action facts.

    All fields are optional because the workflow collects information over
    several turns. The validator decides which fields are required based on the
    corrective-action facts already established.

    Canonical fridge food-risk model:
    - fish_present and non_fish_food_present describe the affected fridge
      contents.
    - food_temperature_c is one shared food probe temperature for the affected
      fridge incident.
    - out_of_range_duration is one shared duration for the affected fridge
      incident.
    - fish_decision and non_fish_decision are category-specific actions.
    - destination_fridge_temperature_c is optional.
    - food_returned_to_fridge is optional.
    - Optional details are only validated if the user volunteers them.
    """

    food_probed: bool | None = None

    fish_present: bool | None = None
    non_fish_food_present: bool | None = None
    food_temperature_c: float | None = None
    out_of_range_duration: OutOfRangeDuration | None = None
    fish_decision: FoodDecision | None = None
    non_fish_decision: FoodDecision | None = None

    destination_fridge_temperature_c: float | None = None

    fridge_issue_type: FridgeIssueType | None = None

    transient_issue_description: str | None = None
    corrective_action_taken: str | None = None
    follow_up_temperature_c: float | None = None

    food_returned_to_fridge: bool | None = None

    maintenance_logged: bool | None = None
    maintenance_reference: str | None = None


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
    - The food probe temperature is shared for the affected fridge incident.
    - The duration outside safe range is shared for the affected fridge incident.
    - Fish is safe at 5°C or below.
    - Non-fish chilled food is safe at 8°C or below.
    - If a category is outside its threshold, duration must be known.
    - If duration is uncertain or more than four hours, the out-of-range
      category must be discarded.
    - Destination fridge details are not required, but contradictory volunteered
      details are still flagged.
    - The faulty fridge itself must be either resolved as a temporary issue with
      a compliant follow-up temperature, or logged for maintenance/repair.
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

    def requires_discard(decision: str | None) -> bool:
        return (
            state.out_of_range_duration in ("gt_4h", "uncertain")
            and decision == "kept_moved_to_compliant_fridge"
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

    # 2. Food presence and probe temperature are needed before food risk can be
    # assessed.
    if state.fish_present is None:
        missing(
            "fish_present",
            "Confirm whether there was any fish in the affected fridge.",
        )

    if state.non_fish_food_present is None:
        missing(
            "non_fish_food_present",
            "Confirm whether there was any other chilled food in the affected fridge.",
        )

    if state.food_temperature_c is None:
        missing(
            "food_temperature_c",
            "Provide the temperature recorded when the food was probed.",
        )

    if issues:
        return FridgeCorrectiveActionValidationResult(issues=issues)

    fish_out_of_range = (
        state.fish_present is True
        and state.food_temperature_c is not None
        and state.food_temperature_c > FOOD_THRESHOLD_FISH_C
    )
    non_fish_out_of_range = (
        state.non_fish_food_present is True
        and state.food_temperature_c is not None
        and state.food_temperature_c > FOOD_THRESHOLD_OTHER_C
    )

    any_food_out_of_range = fish_out_of_range or non_fish_out_of_range

    # 3. If no relevant category is outside its threshold, no duration or food
    # decision is required.
    if any_food_out_of_range:
        if state.out_of_range_duration is None:
            missing(
                "out_of_range_duration",
                "Confirm whether the food was outside the safe range for no more than four hours, more than four hours, or whether the duration was uncertain.",
            )

        if fish_out_of_range:
            if state.fish_decision is None:
                missing(
                    "fish_decision",
                    "Confirm whether the fish was discarded or moved to another compliant fridge.",
                )
            elif requires_discard(state.fish_decision):
                contradiction(
                    "fish_decision",
                    "Fish that was outside the safe range for more than four hours, or where the duration is uncertain, cannot be kept. It must be discarded.",
                )

        if non_fish_out_of_range:
            if state.non_fish_decision is None:
                missing(
                    "non_fish_decision",
                    "Confirm whether the other chilled food was discarded or moved to another compliant fridge.",
                )
            elif requires_discard(state.non_fish_decision):
                contradiction(
                    "non_fish_decision",
                    "Other chilled food that was outside the safe range for more than four hours, or where the duration is uncertain, cannot be kept. It must be discarded.",
                )

    moved_to_another_fridge = (
        state.fish_decision == "kept_moved_to_compliant_fridge"
        or state.non_fish_decision == "kept_moved_to_compliant_fridge"
    )

    # Optional volunteered detail only.
    # Do not require the destination fridge temperature.
    # But if the user states it and it is not compliant, flag it.
    if (
        moved_to_another_fridge
        and state.destination_fridge_temperature_c is not None
        and state.destination_fridge_temperature_c > COMPLIANT_DESTINATION_FRIDGE_THRESHOLD_C
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
