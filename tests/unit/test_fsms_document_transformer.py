import json
from pathlib import Path

import pytest

from gen_ai_fsms.services.fsms_document_transformer import (
    ADDITIONAL_RESPONSE_TITLES,
    CHILLING_EQUIPMENT_QUESTION_KEY,
    transform_additional_response,
)


SOURCE_PATH = Path("data/sfbb_chilling_cooking.json")


def _source_question_keys() -> set[str]:
    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    question_keys = set()

    for section in source["sections"]:
        for safe_method in section["safe_methods"]:
            for safety_point in safe_method["safety_points"]:
                for question in safety_point.get(
                    "additional_questions",
                    [],
                ):
                    question_keys.add(question["question_key"])

    return question_keys


def test_transformer_covers_every_configured_additional_question():
    assert set(ADDITIONAL_RESPONSE_TITLES) == (
        _source_question_keys()
    )


def test_normal_response_uses_document_text_unchanged():
    document_text = (
        "Fish fillets are defrosted under cold running water "
        "when refrigerator space is unavailable.\n"
        "The food remains in a sealed container."
    )

    arrangement = transform_additional_response(
        safety_point_id="4.3.1.1",
        response={
            "question_key": (
                "foods_defrosted_under_cold_running_water"
            ),
            "document_response_text": document_text,
        },
    )

    assert arrangement.arrangement_type == (
        "additional_question_response"
    )
    assert arrangement.title == (
        "Foods defrosted under cold running water"
    )
    assert arrangement.statements == [document_text]
    assert arrangement.source_safety_point_id == "4.3.1.1"
    assert arrangement.source_question_key == (
        "foods_defrosted_under_cold_running_water"
    )


def test_unknown_question_key_is_rejected():
    with pytest.raises(
        ValueError,
        match="Unsupported FSMS document question key",
    ):
        transform_additional_response(
            safety_point_id="4.3.1.1",
            response={
                "question_key": "unknown_question",
                "document_response_text": "Test statement.",
            },
        )


def test_missing_document_response_is_rejected():
    with pytest.raises(
        ValueError,
        match="Missing document response text",
    ):
        transform_additional_response(
            safety_point_id="5.2.1.1",
            response={
                "question_key": "dishes_containing_eggs",
                "document_response_text": None,
            },
        )


def test_chilling_equipment_table_preserves_supplied_order():
    arrangement = transform_additional_response(
        safety_point_id="4.1.1.3",
        response={
            "question_key": CHILLING_EQUIPMENT_QUESTION_KEY,
            "document_response_text": None,
            "current_chilling_equipment": [
                {
                    "equipment_asset_code": "CHILL-002",
                    "equipment_name": "Freezer 1",
                    "equipment_type": "Upright freezer",
                    "equipment_use": "Frozen food storage",
                    "temperature_check_method": "Digital display",
                },
                {
                    "equipment_asset_code": "CHILL-001",
                    "equipment_name": "Fridge 1",
                    "equipment_type": "Upright refrigerator",
                    "equipment_use": "Chilled food storage",
                    "temperature_check_method": (
                        "Digital display and probe thermometer"
                    ),
                },
            ],
        },
    )

    assert arrangement.arrangement_type == (
        "chilling_equipment_table"
    )
    assert arrangement.table_headers == [
        "Asset code",
        "Equipment",
        "Type",
        "Use",
        "Temperature check method",
    ]
    assert arrangement.table_rows == [
        [
            "CHILL-002",
            "Freezer 1",
            "Upright freezer",
            "Frozen food storage",
            "Digital display",
        ],
        [
            "CHILL-001",
            "Fridge 1",
            "Upright refrigerator",
            "Chilled food storage",
            "Digital display and probe thermometer",
        ],
    ]


def test_no_active_chilling_equipment_returns_statement():
    arrangement = transform_additional_response(
        safety_point_id="4.1.1.3",
        response={
            "question_key": CHILLING_EQUIPMENT_QUESTION_KEY,
            "document_response_text": None,
            "current_chilling_equipment": [],
        },
    )

    assert arrangement.table_rows == []
    assert arrangement.statements == [
        "No active chilling equipment is currently recorded."
    ]
