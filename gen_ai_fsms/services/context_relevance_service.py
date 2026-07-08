from typing import Any


DEFAULT_RELEVANT_FACT_TYPES = {
    "business_activity",
    "food_type_or_ingredient",
    "equipment_used",
    "monitoring_or_recording_practice",
    "other_business_operation",
}


SECTION_RELEVANT_FACT_TYPES = {
    "chilling": {
        "temperature_control_practice",
        "storage_practice",
        "food_type_or_ingredient",
        "equipment_used",
        "monitoring_or_recording_practice",
    },
    "cooking": {
        "cooking_or_reheating_practice",
        "equipment_used",
        "monitoring_or_recording_practice",
        "food_type_or_ingredient",
    },
    "cleaning": {
        "cleaning_practice",
        "staff_training_practice",
        "equipment_used",
        "monitoring_or_recording_practice",
    },
}


SAFE_METHOD_RELEVANT_FACT_TYPES = {
    "chilled_storage": {
        "temperature_control_practice",
        "storage_practice",
        "food_type_or_ingredient",
        "equipment_used",
        "monitoring_or_recording_practice",
    },
    "chilled_display": {
        "temperature_control_practice",
        "storage_practice",
        "food_type_or_ingredient",
        "equipment_used",
        "monitoring_or_recording_practice",
    },
    "freezing": {
        "temperature_control_practice",
        "storage_practice",
        "food_type_or_ingredient",
        "equipment_used",
        "monitoring_or_recording_practice",
    },
    "cooking": {
        "cooking_or_reheating_practice",
        "equipment_used",
        "monitoring_or_recording_practice",
        "food_type_or_ingredient",
    },
    "reheating": {
        "cooking_or_reheating_practice",
        "equipment_used",
        "monitoring_or_recording_practice",
        "food_type_or_ingredient",
    },
    "hot_holding": {
        "temperature_control_practice",
        "equipment_used",
        "monitoring_or_recording_practice",
        "food_type_or_ingredient",
    },
}


def normalise_identifier(value: Any) -> str:
    return str(value or "").strip().lower()


def get_relevant_fact_types_for_safety_point(
    safety_point: dict[str, Any] | None,
) -> set[str]:
    if not safety_point:
        return set(DEFAULT_RELEVANT_FACT_TYPES)

    section_id = normalise_identifier(safety_point.get("section_id"))
    section_name = normalise_identifier(safety_point.get("section_name"))
    safe_method_id = normalise_identifier(safety_point.get("safe_method_id"))
    safe_method_name = normalise_identifier(
        safety_point.get("safe_method_name")
    )

    relevant_fact_types = set(DEFAULT_RELEVANT_FACT_TYPES)

    for section_value in (section_id, section_name):
        if section_value in SECTION_RELEVANT_FACT_TYPES:
            relevant_fact_types.update(
                SECTION_RELEVANT_FACT_TYPES[section_value]
            )

    for safe_method_value in (safe_method_id, safe_method_name):
        if safe_method_value in SAFE_METHOD_RELEVANT_FACT_TYPES:
            relevant_fact_types.update(
                SAFE_METHOD_RELEVANT_FACT_TYPES[safe_method_value]
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
