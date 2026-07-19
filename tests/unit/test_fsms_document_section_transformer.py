import pytest

from gen_ai_fsms.services.fsms_document_transformer import (
    build_supported_control_section,
)


SAFE_METHOD_INTRODUCTIONS = {
    "4.3": {
        "title": "Defrosting",
        "source_section_id": "chilling",
        "introduction": (
            "This subsection records how food is defrosted safely."
        ),
    },
    "5.1": {
        "title": "Cooking Safely",
        "source_section_id": "cooking",
        "introduction": (
            "This subsection records how food is cooked safely."
        ),
    },
}


def _section_config(
    *,
    section_id="temperature_control",
    title="Temperature Control",
    display_order=3,
    source_section_id="chilling",
):
    return {
        "section_id": section_id,
        "title": title,
        "display_order": display_order,
        "implementation_status": "supported",
        "source_section_ids": [source_section_id],
        "introduction": "Section introduction.",
    }


def test_completed_section_contains_rules_and_arrangements():
    applicable_safety_points = [
        {
            "safety_point_id": "4.3.1.1",
            "section_id": "chilling",
            "safe_method_id": "4.3",
            "instruction": (
                "Food is thoroughly defrosted before cooking."
            ),
            "source_references": [
                "SFBB Pack > Chilling > Defrosting"
            ],
            "additional_source_references": [
                "SFBB Pack > Chilling > Defrosting > Check it"
            ],
        },
        {
            "safety_point_id": "4.3.1.2",
            "section_id": "chilling",
            "safe_method_id": "4.3",
            "instruction": (
                "Meat and poultry are kept separate while defrosting."
            ),
            "source_references": [
                "SFBB Pack > Chilling > Defrosting"
            ],
            "additional_source_references": [],
        },
    ]

    approved_safety_points = [
        {
            "safety_point_id": "4.3.1.1",
            "safety_point_text": "Original SFBB explanatory text.",
            "provenance_references": [
                "SFBB Pack > Chilling > Defrosting"
            ],
            "additional_responses": [
                {
                    "question_key": (
                        "foods_defrosted_in_microwave"
                    ),
                    "document_response_text": (
                        "Prepared sauces are defrosted in the "
                        "microwave immediately before use."
                    ),
                }
            ],
        },
        {
            "safety_point_id": "4.3.1.2",
            "safety_point_text": "Original explanatory text.",
            "provenance_references": [],
            "additional_responses": [],
        },
    ]

    section = build_supported_control_section(
        section_config=_section_config(),
        safe_method_introductions=SAFE_METHOD_INTRODUCTIONS,
        applicable_safety_points=applicable_safety_points,
        approved_safety_points=approved_safety_points,
    )

    assert section is not None
    assert section.status == "completed"
    assert section.applicable_safety_point_count == 2
    assert section.approved_safety_point_count == 2
    assert section.outstanding_safety_point_count == 0
    assert section.completion_message is None

    assert len(section.subsections) == 1
    subsection = section.subsections[0]

    assert subsection.safe_method_id == "4.3"
    assert subsection.status == "completed"
    assert len(subsection.approved_rules) == 2
    assert subsection.approved_rules[0].instruction == (
        "Food is thoroughly defrosted before cooking."
    )
    assert "Original SFBB explanatory text." not in (
        subsection.approved_rules[0].instruction
    )

    assert subsection.source_references == [
        "SFBB Pack > Chilling > Defrosting",
        "SFBB Pack > Chilling > Defrosting > Check it",
    ]

    assert len(subsection.business_specific_arrangements) == 1
    assert (
        subsection.business_specific_arrangements[0].statements
        == [
            "Prepared sauces are defrosted in the microwave "
            "immediately before use."
        ]
    )


def test_incomplete_section_counts_outstanding_safety_points():
    applicable_safety_points = [
        {
            "safety_point_id": "5.1.1.1",
            "section_id": "cooking",
            "safe_method_id": "5.1",
            "instruction": "Food is cooked properly.",
            "source_references": [
                "SFBB Pack > Cooking > Cooking Safely"
            ],
            "additional_source_references": [],
        },
        {
            "safety_point_id": "5.1.1.2",
            "section_id": "cooking",
            "safe_method_id": "5.1",
            "instruction": (
                "Manufacturer cooking instructions are followed."
            ),
            "source_references": [
                "SFBB Pack > Cooking > Cooking Safely"
            ],
            "additional_source_references": [],
        },
    ]

    section = build_supported_control_section(
        section_config=_section_config(
            section_id="cooking_and_reheating",
            title="Cooking and Reheating",
            display_order=4,
            source_section_id="cooking",
        ),
        safe_method_introductions=SAFE_METHOD_INTRODUCTIONS,
        applicable_safety_points=applicable_safety_points,
        approved_safety_points=[
            {
                "safety_point_id": "5.1.1.1",
                "provenance_references": [],
                "additional_responses": [],
            }
        ],
    )

    assert section is not None
    assert section.status == "not_completed"
    assert section.applicable_safety_point_count == 2
    assert section.approved_safety_point_count == 1
    assert section.outstanding_safety_point_count == 1
    assert section.completion_message == (
        "Not completed: 1 applicable safety point still "
        "requires approval."
    )

    assert section.subsections[0].status == "not_completed"
    assert len(section.subsections[0].approved_rules) == 1


def test_non_applicable_section_is_omitted():
    section = build_supported_control_section(
        section_config=_section_config(),
        safe_method_introductions=SAFE_METHOD_INTRODUCTIONS,
        applicable_safety_points=[
            {
                "safety_point_id": "5.1.1.1",
                "section_id": "cooking",
                "safe_method_id": "5.1",
                "instruction": "Food is cooked properly.",
            }
        ],
        approved_safety_points=[],
    )

    assert section is None


def test_missing_safe_method_configuration_is_rejected():
    with pytest.raises(
        ValueError,
        match="Missing FSMS document safe-method configuration",
    ):
        build_supported_control_section(
            section_config=_section_config(),
            safe_method_introductions=SAFE_METHOD_INTRODUCTIONS,
            applicable_safety_points=[
                {
                    "safety_point_id": "4.9.1.1",
                    "section_id": "chilling",
                    "safe_method_id": "4.9",
                    "instruction": "Test instruction.",
                }
            ],
            approved_safety_points=[],
        )
