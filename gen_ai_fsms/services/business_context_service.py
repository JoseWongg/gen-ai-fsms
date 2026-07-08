from typing import Any, Optional

from sqlalchemy.orm import Session

from gen_ai_fsms.db.models.auth.user import User
from gen_ai_fsms.db.models.business_profile import BusinessProfile
from gen_ai_fsms.db.models.condition_value import ConditionValue
from gen_ai_fsms.services.business_context_fact_service import (
    list_business_context_facts_for_profile,
)
from gen_ai_fsms.services.screening_questions import screening_questions


BUSINESS_TYPE_LABELS = {
    "restaurant": "Restaurant",
    "cafe": "Cafe",
    "bakery": "Bakery",
    "takeaway": "Takeaway",
    "sandwich_shop": "Sandwich shop",
    "pub_or_bar": "Pub or bar",
    "mobile_caterer": "Mobile caterer",
    "care_home_kitchen": "Care home kitchen",
    "school_or_college_kitchen": "School or college kitchen",
    "hotel_or_guesthouse": "Hotel or guesthouse",
    "retail_food_shop": "Retail food shop",
    "other": "Other food business",
}


SCREENING_ACTIVITY_LABELS = {
    "chills_food": "uses chilled storage",
    "chills_hot_food": "cools hot cooked food for later use or storage",
    "defrosts_food": "defrosts frozen food before use",
    "freezes_food": "freezes or stores frozen food",
    "cooks_food": "prepares or cooks food on site",
    "reheats_food": "reheats previously cooked food",
    "hot_holds_food": "keeps food hot before serving",
    "handles_ready_to_eat_food": "prepares ready-to-eat food",
    "delivers_food": "delivers food or prepares food for collection",
    "handles_raw_meat_or_poultry": "handles raw meat or poultry",
    "cooks_rice": "cooks rice",
    "handles_eggs": "uses eggs or foods containing eggs",
    "cooks_dried_pulses": "cooks dried pulses",
    "handles_raw_fish": "handles or cooks fish",
    "handles_raw_molluscs_or_crustaceans": "handles or cooks shellfish",
    "handles_bread_bakery_or_potatoes": (
        "handles bread, bakery products, chips, fries, or similar potato products"
    ),
    "uses_sink_to_defrost_food": "uses a sink to defrost food",
    "buys_frozen_food": "buys food that arrives frozen",
    "stores_food_that_must_be_kept_frozen": (
        "stores food that must remain frozen"
    ),
    "uses_microwave_reheating": "uses a microwave to reheat food",
    "displays_hot_food": "displays hot food",
    "uses_slicer": "uses a slicer for cooked meat or ready-to-eat food",
    "displays_chilled_food": "displays chilled food",
    "stores_or_displays_chilled_food": "stores or displays chilled food",
}


def normalise_text(value: Optional[str]) -> str:
    return " ".join((value or "").split())


def get_business_type_label(business_type: Optional[str]) -> str:
    clean_business_type = normalise_text(business_type)

    if not clean_business_type:
        return ""

    return BUSINESS_TYPE_LABELS.get(
        clean_business_type,
        clean_business_type.replace("_", " ").title(),
    )


def get_screening_activities(condition_values: dict[str, str]) -> list[str]:
    activities: list[str] = []
    added_condition_ids: set[str] = set()

    for question in screening_questions:
        for condition_id in question.get("sets_conditions", []):
            if condition_values.get(condition_id) == "true":
                label = SCREENING_ACTIVITY_LABELS.get(
                    condition_id,
                    condition_id.replace("_", " "),
                )
                if condition_id not in added_condition_ids:
                    activities.append(label)
                    added_condition_ids.add(condition_id)

    for condition_id, value in sorted(condition_values.items()):
        if value == "true" and condition_id not in added_condition_ids:
            activities.append(
                SCREENING_ACTIVITY_LABELS.get(
                    condition_id,
                    condition_id.replace("_", " "),
                )
            )
            added_condition_ids.add(condition_id)

    return activities


def get_business_context(
    db: Session,
    business_profile_id: int,
    user_id: Optional[int] = None,
    relevant_fact_types: Optional[set[str]] = None,
    fact_limit: int = 20,
) -> dict[str, Any]:
    business_profile = (
        db.query(BusinessProfile)
        .filter(BusinessProfile.id == business_profile_id)
        .first()
    )

    if business_profile is None:
        raise ValueError(
            f"Business profile not found: {business_profile_id}"
        )

    user = None
    if user_id is not None:
        user = (
            db.query(User)
            .filter(
                User.id == user_id,
                User.business_profile_id == business_profile_id,
            )
            .first()
        )

    condition_rows = (
        db.query(ConditionValue)
        .filter(ConditionValue.business_profile_id == business_profile_id)
        .order_by(ConditionValue.id.asc())
        .all()
    )

    condition_values = {
        condition.condition_id: condition.value
        for condition in condition_rows
    }

    facts = list_business_context_facts_for_profile(
        db=db,
        business_profile_id=business_profile_id,
        fact_types=relevant_fact_types,
        limit=fact_limit,
    )

    relevant_facts = [
        {
            "fact_type": fact.fact_type,
            "fact_text": fact.fact_text,
            "normalised_fact": fact.normalised_fact,
            "confidence": fact.confidence,
        }
        for fact in facts
    ]

    return {
        "user_first_name": normalise_text(user.first_name if user else None),
        "business_name": normalise_text(business_profile.business_name),
        "site_name": normalise_text(business_profile.site_name),
        "business_type": normalise_text(business_profile.business_type),
        "business_type_label": get_business_type_label(
            business_profile.business_type
        ),
        "business_description": normalise_text(
            business_profile.business_description
        ),
        "condition_values": condition_values,
        "screening_activities": get_screening_activities(condition_values),
        "relevant_facts": relevant_facts,
        "relevant_fact_texts": [
            fact["fact_text"] for fact in relevant_facts
        ],
    }
