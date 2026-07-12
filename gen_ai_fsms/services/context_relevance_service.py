from typing import Any


DEFAULT_RELEVANT_FACT_TYPES = {
    "business_activity",
    "food_type_or_ingredient",
    "equipment_used",
    "monitoring_or_recording_practice",
    "other_business_operation",
}


# Keyed by the real safe_method_id values used in the SFBB data files
# (e.g. "4.1", "5.3"), not by descriptive slugs, because that is the only
# stable identifier present on every safety point at runtime.
SAFE_METHOD_RELEVANT_FACT_TYPES = {
    "4.1": {  # Chilled Storage and Displaying Chilled Food
        "temperature_control_practice",
        "storage_practice",
        "food_type_or_ingredient",
        "equipment_used",
        "monitoring_or_recording_practice",
    },
    "4.2": {  # Chilling Down Hot Food
        "temperature_control_practice",
        "cooking_or_reheating_practice",
        "equipment_used",
        "monitoring_or_recording_practice",
        "food_type_or_ingredient",
    },
    "4.3": {  # Defrosting
        "temperature_control_practice",
        "storage_practice",
        "equipment_used",
        "monitoring_or_recording_practice",
        "food_type_or_ingredient",
    },
    "4.4": {  # Freezing
        "temperature_control_practice",
        "storage_practice",
        "food_type_or_ingredient",
        "equipment_used",
        "monitoring_or_recording_practice",
    },
    "5.1": {  # Cooking Safely
        "cooking_or_reheating_practice",
        "equipment_used",
        "monitoring_or_recording_practice",
        "food_type_or_ingredient",
    },
    "5.2": {  # Foods That Need Extra Care
        "food_type_or_ingredient",
        "cooking_or_reheating_practice",
        "monitoring_or_recording_practice",
    },
    "5.3": {  # Reheating
        "cooking_or_reheating_practice",
        "equipment_used",
        "monitoring_or_recording_practice",
        "food_type_or_ingredient",
    },
    "5.4": {  # Acrylamide
        "cooking_or_reheating_practice",
        "food_type_or_ingredient",
        "equipment_used",
    },
    "5.5": {  # Hot Holding
        "temperature_control_practice",
        "equipment_used",
        "monitoring_or_recording_practice",
        "food_type_or_ingredient",
    },
    "5.6": {  # Ready-to-Eat Food
        "food_type_or_ingredient",
        "storage_practice",
        "monitoring_or_recording_practice",
    },
}


def normalise_identifier(value: Any) -> str:
    return str(value or "").strip().lower()


def get_relevant_fact_types_for_safety_point(
    safety_point: dict[str, Any] | None,
) -> set[str]:
    if not safety_point:
        return set(DEFAULT_RELEVANT_FACT_TYPES)

    safe_method_id = normalise_identifier(safety_point.get("safe_method_id"))

    relevant_fact_types = set(DEFAULT_RELEVANT_FACT_TYPES)

    if safe_method_id in SAFE_METHOD_RELEVANT_FACT_TYPES:
        relevant_fact_types.update(
            SAFE_METHOD_RELEVANT_FACT_TYPES[safe_method_id]
        )

    return relevant_fact_types


def filter_relevant_facts(
    facts: list[dict[str, Any]] | None,
    relevant_fact_types: set[str],
) -> list[dict[str, Any]]:
    if not facts:
        return []

    return [
        fact
        for fact in facts
        if normalise_identifier(fact.get("fact_type")) in relevant_fact_types
    ]


def filter_relevant_fact_texts(
    facts: list[dict[str, Any]] | None,
    relevant_fact_types: set[str],
) -> list[str]:
    return [
        str(fact.get("fact_text"))
        for fact in filter_relevant_facts(facts, relevant_fact_types)
        if fact.get("fact_text")
    ]


def build_relevant_prompt_context(
    business_context: dict[str, Any] | None,
    safety_point: dict[str, Any] | None,
) -> dict[str, Any]:
    source_context = dict(business_context or {})
    relevant_fact_types = get_relevant_fact_types_for_safety_point(
        safety_point
    )
    relevant_facts = filter_relevant_facts(
        source_context.get("relevant_facts"),
        relevant_fact_types,
    )

    source_context["relevant_fact_types"] = sorted(relevant_fact_types)
    source_context["relevant_facts"] = relevant_facts
    source_context["relevant_fact_texts"] = filter_relevant_fact_texts(
        relevant_facts,
        relevant_fact_types,
    )

    return source_context
