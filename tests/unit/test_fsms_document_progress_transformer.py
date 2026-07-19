import pytest

from gen_ai_fsms.schemas.fsms_document import FSMSDocumentSection
from gen_ai_fsms.services.fsms_document_transformer import (
    build_beyond_scope_section,
    build_document_progress,
)


STRUCTURE_CONFIG = {
    "supported_section_count": 4,
    "planned_section_count": 10,
    "sections": [
        {
            "section_id": "food_safety_policy",
            "implementation_status": "supported",
            "always_applicable": True,
            "counts_towards_business_completion": True,
        },
        {
            "section_id": "business_and_hazard_overview",
            "implementation_status": "supported",
            "always_applicable": True,
            "counts_towards_business_completion": True,
        },
        {
            "section_id": "temperature_control",
            "implementation_status": "supported",
            "always_applicable": False,
            "counts_towards_business_completion": True,
        },
        {
            "section_id": "cooking_and_reheating",
            "implementation_status": "supported",
            "always_applicable": False,
            "counts_towards_business_completion": True,
        },
        {
            "section_id": "allergen_management",
            "implementation_status": "beyond_prototype_scope",
            "always_applicable": True,
            "counts_towards_business_completion": False,
        },
    ],
}


def _section(
    section_id: str,
    status: str,
    display_order: int,
) -> FSMSDocumentSection:
    return FSMSDocumentSection(
        section_id=section_id,
        title=section_id.replace("_", " ").title(),
        display_order=display_order,
        status=status,
        introduction="Test introduction.",
    )


def test_build_beyond_scope_section_uses_controlled_placeholder():
    section = build_beyond_scope_section(
        section_config={
            "section_id": "allergen_management",
            "title": "Allergen Management",
            "display_order": 7,
            "implementation_status": (
                "beyond_prototype_scope"
            ),
            "introduction": (
                "This planned section will record allergen controls."
            ),
        }
    )

    assert section.status == "beyond_prototype_scope"
    assert section.completion_message == "Beyond prototype scope"
    assert section.subsections == []
    assert section.applicable_safety_point_count == 0


def test_beyond_scope_builder_rejects_supported_section():
    with pytest.raises(
        ValueError,
        match="Only beyond-prototype-scope sections",
    ):
        build_beyond_scope_section(
            section_config={
                "section_id": "temperature_control",
                "title": "Temperature Control",
                "display_order": 3,
                "implementation_status": "supported",
                "introduction": "Test introduction.",
            }
        )


def test_progress_counts_only_applicable_supported_sections():
    sections = [
        _section("food_safety_policy", "completed", 1),
        _section(
            "business_and_hazard_overview",
            "not_completed",
            2,
        ),
        _section("temperature_control", "completed", 3),
        _section(
            "allergen_management",
            "beyond_prototype_scope",
            7,
        ),
    ]

    progress = build_document_progress(
        structure_config=STRUCTURE_CONFIG,
        sections=sections,
    )

    assert progress.completed_applicable_section_count == 2
    assert progress.applicable_supported_section_count == 3
    assert progress.completion_percentage == 67
    assert progress.document_status == "in_progress"
    assert progress.main_value == "2/3"
    assert progress.coverage_caption == (
        "4 of 10 planned FSMS sections supported"
    )


def test_missing_always_applicable_sections_remain_outstanding():
    progress = build_document_progress(
        structure_config=STRUCTURE_CONFIG,
        sections=[],
    )

    assert progress.completed_applicable_section_count == 0
    assert progress.applicable_supported_section_count == 2
    assert progress.completion_percentage == 0
    assert progress.document_status == "not_started"
    assert progress.main_value == "0/2"


def test_progress_is_complete_when_all_applicable_sections_complete():
    sections = [
        _section("food_safety_policy", "completed", 1),
        _section(
            "business_and_hazard_overview",
            "completed",
            2,
        ),
        _section("temperature_control", "completed", 3),
        _section("cooking_and_reheating", "completed", 4),
    ]

    progress = build_document_progress(
        structure_config=STRUCTURE_CONFIG,
        sections=sections,
    )

    assert progress.completed_applicable_section_count == 4
    assert progress.applicable_supported_section_count == 4
    assert progress.completion_percentage == 100
    assert progress.document_status == "completed"
    assert progress.main_value == "4/4"


def test_duplicate_built_section_is_rejected():
    duplicate_section = _section(
        "food_safety_policy",
        "completed",
        1,
    )

    with pytest.raises(
        ValueError,
        match="Duplicate built FSMS document section",
    ):
        build_document_progress(
            structure_config=STRUCTURE_CONFIG,
            sections=[
                duplicate_section,
                duplicate_section,
            ],
        )


def test_unconfigured_built_section_is_rejected():
    with pytest.raises(
        ValueError,
        match="Built FSMS document section is not configured",
    ):
        build_document_progress(
            structure_config=STRUCTURE_CONFIG,
            sections=[
                _section("unknown_section", "completed", 11)
            ],
        )
