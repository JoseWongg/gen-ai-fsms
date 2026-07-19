from datetime import datetime, timezone
import re

from reportlab.platypus import PageBreak, Table

from gen_ai_fsms.schemas.fsms_document import (
    FSMSDocument,
    FSMSDocumentAppendix,
    FSMSDocumentArrangement,
    FSMSDocumentProgress,
    FSMSDocumentRule,
    FSMSDocumentSection,
    FSMSDocumentSubsection,
)
from gen_ai_fsms.services.fsms_document_pdf import (
    _build_story,
    _build_styles,
    _normalise_text,
    render_fsms_document_pdf,
)


def _document():
    return FSMSDocument(
        document_title="Food Safety Management System",
        business_name="Example Foods Ltd",
        site_name="Example Kitchen",
        business_type="Restaurant",
        business_description=(
            "A small restaurant serving cooked meals."
        ),
        generated_at=datetime(
            2026,
            7,
            19,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        progress=FSMSDocumentProgress(
            completed_applicable_section_count=1,
            applicable_supported_section_count=2,
            completion_percentage=50,
            supported_section_count=4,
            planned_section_count=10,
            document_status="in_progress",
            main_value="1/2",
            completion_caption=(
                "Applicable prototype sections completed"
            ),
            coverage_caption=(
                "4 of 10 planned FSMS sections supported"
            ),
        ),
        sections=[
            FSMSDocumentSection(
                section_id="temperature_control",
                title="Temperature Control",
                display_order=3,
                status="completed",
                introduction=(
                    "This section records temperature controls."
                ),
                applicable_safety_point_count=1,
                approved_safety_point_count=1,
                outstanding_safety_point_count=0,
                subsections=[
                    FSMSDocumentSubsection(
                        safe_method_id="4.1",
                        title="Chilled Storage",
                        introduction=(
                            "This subsection records chilled storage."
                        ),
                        status="completed",
                        approved_rules=[
                            FSMSDocumentRule(
                                safety_point_id="4.1.1.1",
                                instruction=(
                                    "Chilled food is kept cold."
                                ),
                                source_references=[
                                    (
                                        "SFBB Pack > Chilling > "
                                        "Chilled Storage"
                                    )
                                ],
                            )
                        ],
                        business_specific_arrangements=[
                            FSMSDocumentArrangement(
                                arrangement_type=(
                                    "chilling_equipment_table"
                                ),
                                title=(
                                    "Chilling equipment and "
                                    "temperature checks"
                                ),
                                table_headers=[
                                    "Asset code",
                                    "Equipment",
                                    "Type",
                                    "Use",
                                    (
                                        "Temperature check "
                                        "method"
                                    ),
                                ],
                                table_rows=[
                                    [
                                        "CHILL-001",
                                        "Fridge 1",
                                        "Fridge",
                                        "Storage",
                                        "Digital/dial display",
                                    ]
                                ],
                                source_safety_point_id=(
                                    "4.1.1.1"
                                ),
                                source_question_key=(
                                    "chilling_equipment_"
                                    "temperature_checks"
                                ),
                            )
                        ],
                        source_references=[
                            (
                                "SFBB Pack > Chilling > "
                                "Chilled Storage"
                            )
                        ],
                    )
                ],
            ),
            FSMSDocumentSection(
                section_id="allergen_management",
                title="Allergen Management",
                display_order=7,
                status="beyond_prototype_scope",
                introduction=(
                    "This planned section will record allergen "
                    "controls."
                ),
                completion_message="Beyond prototype scope",
            ),
        ],
        appendices=[
            FSMSDocumentAppendix(
                appendix_id="source_references",
                title="Source References",
                display_order=1,
                source_references=[
                    (
                        "SFBB Pack > Chilling > "
                        "Chilled Storage"
                    )
                ],
            )
        ],
    )


def test_render_fsms_document_pdf_returns_valid_pdf_bytes():
    pdf_bytes = render_fsms_document_pdf(_document())

    assert pdf_bytes.startswith(b"%PDF-")
    assert pdf_bytes.rstrip().endswith(b"%%EOF")
    assert len(pdf_bytes) > 3000
    assert len(
        re.findall(rb"/Type\s*/Page\b", pdf_bytes)
    ) >= 2


def test_story_contains_tables_and_page_breaks():
    story = _build_story(
        document=_document(),
        styles=_build_styles(),
    )

    assert any(
        isinstance(flowable, Table)
        for flowable in story
    )
    assert any(
        isinstance(flowable, PageBreak)
        for flowable in story
    )


def test_normalise_text_replaces_unsupported_punctuation():
    assert _normalise_text(
        "Cold–food — manager’s “check”"
    ) == 'Cold-food - manager\'s "check"'


def test_renderer_handles_empty_appendix_content():
    document = _document()
    document.appendices[0].source_references = []

    pdf_bytes = render_fsms_document_pdf(document)

    assert pdf_bytes.startswith(b"%PDF-")
    assert pdf_bytes.rstrip().endswith(b"%%EOF")
