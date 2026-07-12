import json

from gen_ai_fsms.services.context_relevance_service import (
    DEFAULT_RELEVANT_FACT_TYPES,
    build_relevant_prompt_context,
    filter_relevant_fact_texts,
    filter_relevant_facts,
    get_relevant_fact_types_for_safety_point,
    normalise_identifier,
)


def test_normalise_identifier_handles_none_and_spacing():
    assert normalise_identifier(None) == ""
    assert normalise_identifier(" Chilling ") == "chilling"


def test_get_relevant_fact_types_for_chilled_storage_safety_point():
    fact_types = get_relevant_fact_types_for_safety_point(
        {
            "safe_method_id": "4.1",
            "safe_method_name": "Chilled Storage and Displaying Chilled Food",
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
            "safe_method_id": "5.1",
            "safe_method_name": "Cooking Safely",
        }
    )

    assert "cooking_or_reheating_practice" in fact_types
    assert "equipment_used" in fact_types
    assert "monitoring_or_recording_practice" in fact_types
    assert "food_type_or_ingredient" in fact_types
    assert "storage_practice" not in fact_types
    assert "cleaning_practice" not in fact_types


def test_get_relevant_fact_types_for_hot_holding_safety_point():
    # Regression test: previously "hot_holding" was keyed as a descriptive
    # slug that never matched the real numeric safe_method_id ("5.5"), so
    # hot holding safety points silently only ever received the default
    # fact types. This proves the real id now matches.
    fact_types = get_relevant_fact_types_for_safety_point(
        {
            "safe_method_id": "5.5",
            "safe_method_name": "Hot Holding",
        }
    )

    assert "temperature_control_practice" in fact_types
    assert "equipment_used" in fact_types
    assert "monitoring_or_recording_practice" in fact_types
    assert "food_type_or_ingredient" in fact_types
    assert "cooking_or_reheating_practice" not in fact_types


def test_get_relevant_fact_types_falls_back_to_defaults_for_unknown_method():
    fact_types = get_relevant_fact_types_for_safety_point(
        {
            "safe_method_id": "9.9",
            "safe_method_name": "Not a real method",
        }
    )

    assert fact_types == DEFAULT_RELEVANT_FACT_TYPES


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
            "safe_method_id": "4.1",
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
