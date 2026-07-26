from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from gen_ai_fsms.schemas.fsms_policy_document import (
    FSMSContentSource,
    FSMSListBlock,
    FSMSPolicyDocument,
    FSMSPolicySection,
    FSMSPolicySubsection,
    FSMSTableBlock,
    FSMSTextBlock,
)


DRAFT_NOTICE = (
    "This document is incomplete and must not be "
    "treated as the final approved Food Safety "
    "Management System."
)


def build_sample_document(
    *,
    document_status="draft",
) -> FSMSPolicyDocument:
    source = FSMSContentSource(
        safety_point_ids=[
            "4.1.1.1",
            "4.1.1.3",
        ],
        condition_ids=["chills_food"],
        additional_question_keys=[
            "chilling_equipment_temperature_checks"
        ],
        source_references=[
            (
                "SFBB Pack > Chilling > "
                "Chilled Storage"
            )
        ],
    )

    importance = FSMSTextBlock(
        role="food_safety_importance",
        heading="Why chilled storage matters",
        text=(
            "Food requiring refrigeration must remain "
            "under effective temperature control."
        ),
        source=source,
    )

    procedures = FSMSListBlock(
        role="procedure",
        heading="Chilled-storage procedures",
        items=[
            "Fridges are operated at 5°C or below.",
            (
                "Food is covered, labelled and used "
                "within its established shelf life."
            ),
        ],
        source=source,
    )

    equipment = FSMSTableBlock(
        role="equipment",
        heading=(
            "Chilling equipment and monitoring"
        ),
        headers=[
            "Equipment",
            "Use",
            "Check method",
            "Required checks",
        ],
        rows=[
            [
                "Fridge 1",
                "Chilled storage",
                "Probe between packs",
                "AM and PM",
            ]
        ],
        source=source,
    )

    subsection = FSMSPolicySubsection(
        subsection_number="3.1",
        title="Chilled Storage and Display",
        content_blocks=[
            importance,
            procedures,
            equipment,
        ],
    )

    section = FSMSPolicySection(
        section_number="3",
        title="Chilling and Temperature Control",
        content_blocks=[
            FSMSTextBlock(
                role="introduction",
                text=(
                    "This section sets out the controls "
                    "used for chilled food."
                ),
            )
        ],
        subsections=[subsection],
    )

    return FSMSPolicyDocument(
        document_title=(
            "Food Safety Management System"
        ),
        document_status=document_status,
        draft_notice=(
            DRAFT_NOTICE
            if document_status == "draft"
            else None
        ),
        business_name="Test Bakery Ltd",
        site_name="Main Bakery",
        business_type="Bakery",
        generated_at=datetime(
            2026,
            7,
            20,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        sections=[section],
    )


def test_policy_document_serialises_finished_content():
    document = build_sample_document()

    payload = document.model_dump(mode="json")
    json_output = document.model_dump_json()

    assert payload["document_status"] == "draft"
    assert payload["draft_notice"] == DRAFT_NOTICE

    blocks = (
        payload["sections"][0]
        ["subsections"][0]
        ["content_blocks"]
    )

    assert [
        block["block_type"]
        for block in blocks
    ] == [
        "text",
        "list",
        "table",
    ]

    assert blocks[0]["source"]["safety_point_ids"] == [
        "4.1.1.1",
        "4.1.1.3",
    ]
    assert (
        blocks[2]["rows"][0][0]
        == "Fridge 1"
    )
    assert "Test Bakery Ltd" in json_output

    assert "progress" not in payload
    assert "appendices" not in payload
    assert "business_description" not in payload


def test_approved_document_has_no_draft_notice():
    document = build_sample_document(
        document_status="approved"
    )

    assert document.document_status == "approved"
    assert document.draft_notice is None


def test_draft_document_requires_notice():
    payload = build_sample_document().model_dump()
    payload["draft_notice"] = None

    with pytest.raises(
        ValidationError,
        match="must contain a draft notice",
    ):
        FSMSPolicyDocument.model_validate(payload)


def test_approved_document_rejects_draft_notice():
    payload = build_sample_document(
        document_status="approved"
    ).model_dump()
    payload["draft_notice"] = DRAFT_NOTICE

    with pytest.raises(
        ValidationError,
        match="must not contain a draft notice",
    ):
        FSMSPolicyDocument.model_validate(payload)


def test_policy_document_rejects_workflow_only_fields():
    payload = build_sample_document().model_dump()
    payload["progress"] = {
        "completion_percentage": 75,
    }

    with pytest.raises(ValidationError):
        FSMSPolicyDocument.model_validate(payload)


def test_table_rows_must_match_headers():
    with pytest.raises(
        ValidationError,
        match=(
            "same number of values as the headers"
        ),
    ):
        FSMSTableBlock(
            role="monitoring",
            headers=[
                "Equipment",
                "Check method",
            ],
            rows=[
                ["Fridge 1"],
            ],
        )


def test_content_blocks_reject_unknown_block_type():
    payload = build_sample_document().model_dump()
    payload["sections"][0]["content_blocks"] = [
        {
            "block_type": "approved_rule",
            "role": "policy",
            "text": "A workflow rule.",
        }
    ]

    with pytest.raises(ValidationError):
        FSMSPolicyDocument.model_validate(payload)

@pytest.mark.parametrize(
    "role",
    [
        "business_context",
        "food_safety_importance",
    ],
)
def test_list_blocks_support_overview_roles(role):
    block = FSMSListBlock(
        role=role,
        items=["A controlled document statement."],
    )

    assert block.role == role

def test_table_blocks_support_responsibilities_role():
    block = FSMSTableBlock(
        role="responsibilities",
        headers=[
            "Role",
            "Named person(s)",
            "Main responsibility",
        ],
        rows=[
            [
                "Responsible manager",
                "Not yet recorded",
                "Maintain the FSMS.",
            ],
        ],
    )

    assert block.role == "responsibilities"


def test_policy_identifiers_are_internal_only():
    subsection = FSMSPolicySubsection(
        subsection_id="configured_subsection",
        subsection_number="1.1",
        title="Configured Subsection",
    )
    section = FSMSPolicySection(
        section_id="configured_section",
        section_number="1",
        title="Configured Section",
        subsections=[subsection],
    )

    assert section.section_id == "configured_section"
    assert (
        section.subsections[0].subsection_id
        == "configured_subsection"
    )

    payload = section.model_dump()

    assert "section_id" not in payload
    assert (
        "subsection_id"
        not in payload["subsections"][0]
    )
