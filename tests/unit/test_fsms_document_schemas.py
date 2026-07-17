from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from gen_ai_fsms.schemas.fsms_document import (
    FSMSDocument,
    FSMSDocumentAppendix,
    FSMSDocumentArrangement,
    FSMSDocumentProgress,
    FSMSDocumentRule,
    FSMSDocumentSection,
    FSMSDocumentSubsection,
)


def build_sample_document() -> FSMSDocument:
    arrangement = FSMSDocumentArrangement(
        arrangement_type="food_list",
        title="Foods defrosted in the microwave",
        statements=["Prepared sauces"],
        source_safety_point_id="4.3.1.1",
        source_question_key="foods_defrosted_in_microwave",
    )

    rule = FSMSDocumentRule(
        safety_point_id="4.3.1.1",
        instruction="Food is thoroughly defrosted before cooking.",
        source_references=["SFBB Pack > Chilling > Defrosting"],
    )

    subsection = FSMSDocumentSubsection(
        safe_method_id="4.3",
        title="Defrosting",
        introduction="This subsection records safe defrosting methods.",
        status="completed",
        approved_rules=[rule],
        business_specific_arrangements=[arrangement],
        source_references=[
            "SFBB Pack > Chilling > Defrosting"
        ],
    )

    section = FSMSDocumentSection(
        section_id="temperature_control",
        title="Temperature Control",
        display_order=3,
        status="completed",
        introduction="This section records temperature controls.",
        applicable_safety_point_count=1,
        approved_safety_point_count=1,
        outstanding_safety_point_count=0,
        subsections=[subsection],
    )

    appendix = FSMSDocumentAppendix(
        appendix_id="source_references",
        title="Source References",
        display_order=2,
        source_references=[
            "SFBB Pack > Chilling > Defrosting"
        ],
    )

    progress = FSMSDocumentProgress(
        completed_applicable_section_count=4,
        applicable_supported_section_count=4,
        completion_percentage=100,
        supported_section_count=4,
        planned_section_count=10,
        document_status="completed",
        main_value="4/4",
        completion_caption=(
            "Applicable prototype sections completed"
        ),
        coverage_caption=(
            "4 of 10 planned FSMS sections supported"
        ),
    )

    return FSMSDocument(
        document_title="Food Safety Management System",
        business_name="Test Bakery",
        site_name="Main Site",
        business_type="Bakery",
        business_description="Celebration cakes and cupcakes.",
        generated_at=datetime(
            2026,
            7,
            17,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        progress=progress,
        sections=[section],
        appendices=[appendix],
    )


def test_complete_document_serialises_to_json():
    document = build_sample_document()

    payload = document.model_dump(mode="json")
    json_output = document.model_dump_json()

    assert payload["business_name"] == "Test Bakery"
    assert payload["progress"]["main_value"] == "4/4"
    assert (
        payload["sections"][0]["subsections"][0]
        ["approved_rules"][0]["safety_point_id"]
        == "4.3.1.1"
    )
    assert "Test Bakery" in json_output


@pytest.mark.parametrize(
    "missing_field",
    [
        "business_name",
        "site_name",
    ],
)
def test_document_requires_business_and_site_names(missing_field):
    payload = build_sample_document().model_dump()
    payload.pop(missing_field)

    with pytest.raises(ValidationError):
        FSMSDocument.model_validate(payload)



def test_empty_document_lists_serialise_correctly():
    progress = FSMSDocumentProgress(
        completed_applicable_section_count=0,
        applicable_supported_section_count=2,
        completion_percentage=0,
        supported_section_count=4,
        planned_section_count=10,
        document_status="not_started",
        main_value="0/2",
        completion_caption=(
            "Applicable prototype sections completed"
        ),
        coverage_caption=(
            "4 of 10 planned FSMS sections supported"
        ),
    )

    document = FSMSDocument(
        document_title="Food Safety Management System",
        business_name="Test Business",
        site_name="Main Site",
        generated_at=datetime.now(timezone.utc),
        progress=progress,
    )

    payload = document.model_dump(mode="json")

    assert payload["sections"] == []
    assert payload["appendices"] == []


@pytest.mark.parametrize(
    "invalid_status",
    [
        "not_applicable",
        "pending",
        "approved",
    ],
)
def test_section_rejects_invalid_status(invalid_status):
    with pytest.raises(ValidationError):
        FSMSDocumentSection(
            section_id="temperature_control",
            title="Temperature Control",
            display_order=3,
            status=invalid_status,
            introduction="Test introduction.",
        )


def test_progress_rejects_percentage_above_100():
    with pytest.raises(ValidationError):
        FSMSDocumentProgress(
            completed_applicable_section_count=4,
            applicable_supported_section_count=4,
            completion_percentage=101,
            supported_section_count=4,
            planned_section_count=10,
            document_status="completed",
            main_value="4/4",
            completion_caption="Completed",
            coverage_caption="4 of 10 supported",
        )
