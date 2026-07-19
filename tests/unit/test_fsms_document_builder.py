from datetime import datetime, timezone

import pytest

from gen_ai_fsms.schemas.fsms_document import FSMSDocumentSection
from gen_ai_fsms.services.fsms_document_transformer import (
    build_fsms_document,
)


STRUCTURE_CONFIG = {
    "document_title": "Food Safety Management System",
    "supported_section_count": 4,
    "planned_section_count": 10,
    "sections": [
        {
            "section_id": "food_safety_policy",
            "title": "Food Safety Policy",
            "display_order": 1,
            "implementation_status": "supported",
            "always_applicable": True,
            "counts_towards_business_completion": True,
            "introduction": "Policy introduction.",
        },
        {
            "section_id": "business_and_hazard_overview",
            "title": "Business and Hazard Overview",
            "display_order": 2,
            "implementation_status": "supported",
            "always_applicable": True,
            "counts_towards_business_completion": True,
            "introduction": "Business overview introduction.",
        },
        {
            "section_id": "temperature_control",
            "title": "Temperature Control",
            "display_order": 3,
            "implementation_status": "supported",
            "always_applicable": False,
            "counts_towards_business_completion": True,
            "introduction": "Temperature introduction.",
        },
        {
            "section_id": "cooking_and_reheating",
            "title": "Cooking and Reheating",
            "display_order": 4,
            "implementation_status": "supported",
            "always_applicable": False,
            "counts_towards_business_completion": True,
            "introduction": "Cooking introduction.",
        },
        {
            "section_id": "cross_contamination_control",
            "title": "Cross-Contamination Control",
            "display_order": 5,
            "implementation_status": "beyond_prototype_scope",
            "always_applicable": True,
            "counts_towards_business_completion": False,
            "introduction": "Planned section introduction.",
        },
    ],
    "appendices": [
        {
            "appendix_id": "monitoring_arrangements_and_records",
            "title": "Monitoring Arrangements and Records",
            "display_order": 1,
        },
        {
            "appendix_id": "source_references",
            "title": "Source References",
            "display_order": 2,
        },
    ],
}


BUSINESS_PROFILE = {
    "business_name": "Example Foods Ltd",
    "site_name": "Example Kitchen",
    "business_type": "Restaurant",
    "business_description": "A small restaurant serving cooked meals.",
}


def _section(
    section_id: str,
    title: str,
    display_order: int,
    status: str = "completed",
) -> FSMSDocumentSection:
    return FSMSDocumentSection(
        section_id=section_id,
        title=title,
        display_order=display_order,
        status=status,
        introduction="Section introduction.",
    )


def test_document_builder_assembles_controlled_document():
    generated_at = datetime(
        2026,
        7,
        19,
        12,
        0,
        tzinfo=timezone.utc,
    )

    document = build_fsms_document(
        structure_config=STRUCTURE_CONFIG,
        business_profile=BUSINESS_PROFILE,
        generated_at=generated_at,
        supported_sections=[
            _section(
                "temperature_control",
                "Temperature Control",
                3,
            )
        ],
    )

    assert document.document_title == (
        "Food Safety Management System"
    )
    assert document.business_name == "Example Foods Ltd"
    assert document.site_name == "Example Kitchen"
    assert document.business_type == "Restaurant"
    assert document.business_description == (
        "A small restaurant serving cooked meals."
    )
    assert document.generated_at == generated_at

    assert [
        section.section_id
        for section in document.sections
    ] == [
        "food_safety_policy",
        "business_and_hazard_overview",
        "temperature_control",
        "cross_contamination_control",
    ]

    assert document.sections[0].status == "not_completed"
    assert document.sections[0].completion_message == (
        "Not completed"
    )
    assert document.sections[1].status == "not_completed"
    assert document.sections[2].status == "completed"
    assert document.sections[3].status == (
        "beyond_prototype_scope"
    )

    assert document.progress.main_value == "1/3"
    assert document.progress.completion_percentage == 33
    assert document.progress.document_status == "in_progress"

    assert [
        appendix.appendix_id
        for appendix in document.appendices
    ] == [
        "monitoring_arrangements_and_records",
        "source_references",
    ]


def test_complete_always_applicable_sections_complete_document():
    document = build_fsms_document(
        structure_config=STRUCTURE_CONFIG,
        business_profile=BUSINESS_PROFILE,
        generated_at=datetime.now(timezone.utc),
        supported_sections=[
            _section(
                "food_safety_policy",
                "Food Safety Policy",
                1,
            ),
            _section(
                "business_and_hazard_overview",
                "Business and Hazard Overview",
                2,
            ),
        ],
    )

    assert document.progress.main_value == "2/2"
    assert document.progress.completion_percentage == 100
    assert document.progress.document_status == "completed"


def test_document_builder_rejects_missing_business_identity():
    incomplete_profile = {
        **BUSINESS_PROFILE,
        "business_name": " ",
    }

    with pytest.raises(
        ValueError,
        match="business_name",
    ):
        build_fsms_document(
            structure_config=STRUCTURE_CONFIG,
            business_profile=incomplete_profile,
            generated_at=datetime.now(timezone.utc),
            supported_sections=[],
        )


def test_document_builder_rejects_unconfigured_section():
    with pytest.raises(
        ValueError,
        match="is not configured",
    ):
        build_fsms_document(
            structure_config=STRUCTURE_CONFIG,
            business_profile=BUSINESS_PROFILE,
            generated_at=datetime.now(timezone.utc),
            supported_sections=[
                _section(
                    "unknown_section",
                    "Unknown Section",
                    11,
                )
            ],
        )


def test_document_builder_rejects_structure_mismatch():
    with pytest.raises(
        ValueError,
        match="does not match its controlled structure",
    ):
        build_fsms_document(
            structure_config=STRUCTURE_CONFIG,
            business_profile=BUSINESS_PROFILE,
            generated_at=datetime.now(timezone.utc),
            supported_sections=[
                _section(
                    "temperature_control",
                    "Wrong title",
                    3,
                )
            ],
        )
