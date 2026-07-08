import json

from gen_ai_fsms.services.context_relevance_service import (
    build_relevant_prompt_context,
    filter_relevant_fact_texts,
    filter_relevant_facts,
    get_relevant_fact_types_for_safety_point,
    normalise_identifier,
)


def test_normalise_identifier_handles_none_and_spacing():
    assert normalise_identifier(None) == ""
    assert normalise_identifier(" Chilling ") == "chilling"


def test_get_relevant_fact_types_for_chilling_safety_point():
    fact_types = get_relevant_fact_types_for_safety_point(
        {
            "section_id": "chilling",
            "section_name": "Chilling",
            "safe_method_id": "chilled_storage",
            "safe_method_name": "Chilled storage",
        }
    )

    assert "temperature_control_practice" in fact_types
    assert "storage_practice" in fact_types
    assert "food_type_or_ingredient" in fact_types
    assert "equipment_used" in fact_types
    assert "monitoring_or_recording_practice" in fact_types
    assert "cooking_or_reheating_practice" not in fact_types
    assert "cleaning_practice" not in fact_types


def test_get_relevant_fact_types_for_cooking_safety_point():
    fact_types = get_relevant_fact_types_for_safety_point(
        {
            "section_id": "cooking",
            "section_name": "Cooking",
            "safe_method_id": "cooking",
            "safe_method_name": "Cooking safely",
        }
    )

    assert "cooking_or_reheating_practice" in fact_types
    assert "equipment_used" in fact_types
    assert "monitoring_or_recording_practice" in fact_types
    assert "food_type_or_ingredient" in fact_types
    assert "storage_practice" not in fact_types
    assert "cleaning_practice" not in fact_types


def test_filter_relevant_facts_keeps_only_matching_fact_types():
    facts = [
        {
            "fact_type": "temperature_control_practice",
            "fact_text": "The business checks fridge temperatures daily.",
        },
        {
            "fact_type": "cleaning_practice",
            "fact_text": "The business sanitises worktops every hour.",
        },
        {
            "fact_type": "equipment_used",
            "fact_text": "The business uses upright fridges.",
        },
    ]

    result = filter_relevant_facts(
        facts,
        {
            "temperature_control_practice",
            "equipment_used",
        },
    )

    assert result == [
        {
            "fact_type": "temperature_control_practice",
            "fact_text": "The business checks fridge temperatures daily.",
        },
        {
            "fact_type": "equipment_used",
            "fact_text": "The business uses upright fridges.",
        },
    ]


def test_filter_relevant_fact_texts_returns_matching_text_only():
    facts = [
        {
            "fact_type": "temperature_control_practice",
            "fact_text": "The business checks fridge temperatures daily.",
        },
        {
            "fact_type": "cleaning_practice",
            "fact_text": "The business sanitises worktops every hour.",
        },
    ]

    result = filter_relevant_fact_texts(
        facts,
        {"temperature_control_practice"},
    )

    assert result == ["The business checks fridge temperatures daily."]


def test_build_relevant_prompt_context_filters_context_without_mutating_source():
    business_context = {
        "business_name": "Test Bakery",
        "business_type_label": "Bakery",
        "relevant_facts": [
            {
                "fact_type": "temperature_control_practice",
                "fact_text": "The business checks fridge temperatures daily.",
            },
            {
                "fact_type": "cleaning_practice",
                "fact_text": "The business sanitises worktops every hour.",
            },
            {
                "fact_type": "equipment_used",
                "fact_text": "The business uses upright fridges.",
            },
        ],
        "relevant_fact_texts": [
            "The business checks fridge temperatures daily.",
            "The business sanitises worktops every hour.",
            "The business uses upright fridges.",
        ],
    }

    result = build_relevant_prompt_context(
        business_context,
        {
            "section_id": "chilling",
            "safe_method_id": "chilled_storage",
        },
    )

    assert result["business_name"] == "Test Bakery"
    assert result["business_type_label"] == "Bakery"
    assert result["relevant_facts"] == [
        {
            "fact_type": "temperature_control_practice",
            "fact_text": "The business checks fridge temperatures daily.",
        },
        {
            "fact_type": "equipment_used",
            "fact_text": "The business uses upright fridges.",
        },
    ]
    assert result["relevant_fact_texts"] == [
        "The business checks fridge temperatures daily.",
        "The business uses upright fridges.",
    ]
    assert "temperature_control_practice" in result["relevant_fact_types"]

    assert business_context["relevant_facts"] == [
        {
            "fact_type": "temperature_control_practice",
            "fact_text": "The business checks fridge temperatures daily.",
        },
        {
            "fact_type": "cleaning_practice",
            "fact_text": "The business sanitises worktops every hour.",
        },
        {
            "fact_type": "equipment_used",
            "fact_text": "The business uses upright fridges.",
        },
    ]

    json.dumps(result)


def test_build_relevant_prompt_context_handles_empty_context():
    result = build_relevant_prompt_context(None, None)

    assert result["relevant_facts"] == []
    assert result["relevant_fact_texts"] == []
    assert "business_activity" in result["relevant_fact_types"]

    json.dumps(result)
