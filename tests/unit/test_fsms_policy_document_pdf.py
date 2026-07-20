from datetime import datetime, timezone
import re

from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    Table,
)

from gen_ai_fsms.schemas.fsms_policy_document import (
    FSMSPolicyDocument,
    FSMSPolicySubsection,
)
from gen_ai_fsms.services.fsms_policy_document_pdf import (
    CONTENT_WIDTH,
    _build_story,
    _build_styles,
    _normalise_text,
    _subsection_flowables,
    _table_cell_paragraph,
    _table_column_widths,
    render_fsms_policy_document_pdf,
)


DRAFT_NOTICE = (
    "This document is incomplete and must not be "
    "treated as the final approved Food Safety "
    "Management System."
)


def _document(
    *,
    document_status="draft",
):
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
        business_name="Example Foods Ltd",
        site_name="Example Kitchen",
        business_type="Bakery",
        generated_at=datetime(
            2026,
            7,
            20,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        sections=[
            {
                "section_number": "1",
                "title": "Food Safety Policy",
                "content_blocks": [
                    {
                        "block_type": "text",
                        "role": "policy",
                        "text": (
                            "Controlled food safety policy."
                        ),
                        "source": {
                            "source_references": [
                                "internal.policy.reference",
                            ],
                        },
                    },
                    {
                        "block_type": "list",
                        "role": "responsibilities",
                        "heading": "Responsibilities",
                        "items": [
                            "Staff follow approved controls.",
                            "Managers review records.",
                        ],
                    },
                ],
                "subsections": [
                    {
                        "subsection_number": "1.1",
                        "title": "Purpose and Scope",
                        "content_blocks": [
                            {
                                "block_type": "list",
                                "role": "procedure",
                                "ordered": True,
                                "items": [
                                    "Complete the first check.",
                                    "Complete the second check.",
                                ],
                            }
                        ],
                    }
                ],
            },
            {
                "section_number": "2",
                "title": (
                    "Business Scope and Food Safety "
                    "Overview"
                ),
                "content_blocks": [
                    {
                        "block_type": "text",
                        "role": "business_context",
                        "heading": (
                            "Business-specific arrangement"
                        ),
                        "text": (
                            "The bakery prepares food "
                            "on site."
                        ),
                    }
                ],
            },
            {
                "section_number": "3",
                "title": (
                    "Chilling and Temperature Control"
                ),
                "content_blocks": [
                    {
                        "block_type": "table",
                        "role": "equipment",
                        "heading": (
                            "Active chilling equipment"
                        ),
                        "headers": [
                            "Asset code",
                            "Equipment",
                            "Type",
                            "Use",
                            "Check method",
                            "Required limit",
                        ],
                        "rows": [
                            [
                                "FR-001",
                                "Main fridge",
                                "Fridge",
                                "Storage",
                                (
                                    "Digital or dial "
                                    "display"
                                ),
                                "8°C or below",
                            ],
                            [
                                "FZ-001",
                                "Chest freezer",
                                "Freezer",
                                "Storage",
                                "Probe between packs",
                                "−18°C or below",
                            ],
                        ],
                        "source": {
                            "safety_point_ids": [
                                "4.1.1.3",
                            ],
                        },
                    },
                    {
                        "block_type": "table",
                        "role": "checklist",
                        "heading": (
                            "Daily chilling temperature "
                            "checks"
                        ),
                        "headers": [
                            "Equipment",
                            "Required limit",
                            "AM temperature",
                            "PM temperature",
                            (
                                "Corrective action / "
                                "diary reference"
                            ),
                        ],
                        "rows": [
                            [
                                "Main fridge",
                                "8°C or below",
                                "",
                                "",
                                "",
                            ],
                        ],
                    },
                ],
            },
            {
                "section_number": "4",
                "title": "Cooking and Reheating",
                "content_blocks": [
                    {
                        "block_type": "table",
                        "role": "monitoring",
                        "heading": (
                            "Safe time and temperature "
                            "combinations"
                        ),
                        "headers": [
                            "Temperature",
                            "Minimum holding time",
                        ],
                        "rows": [
                            [
                                "80°C",
                                "6 seconds",
                            ],
                            [
                                "75°C",
                                "30 seconds",
                            ],
                        ],
                    }
                ],
            },
        ],
    )


def _flowable_text(flowable):
    if isinstance(flowable, Paragraph):
        return [
            flowable.getPlainText()
        ]

    if isinstance(flowable, Table):
        values = []

        for row in flowable._cellvalues:
            for cell in row:
                values.extend(
                    _flowable_text(cell)
                )

        return values

    if isinstance(flowable, (list, tuple)):
        values = []

        for item in flowable:
            values.extend(
                _flowable_text(item)
            )

        return values

    return []


def _story_text(document):
    story = _build_story(
        document=document,
        styles=_build_styles(),
    )

    values = []

    for flowable in story:
        values.extend(
            _flowable_text(flowable)
        )

    return "\n".join(values)


def test_render_policy_pdf_returns_valid_pdf_bytes():
    pdf_bytes = render_fsms_policy_document_pdf(
        _document()
    )

    assert pdf_bytes.startswith(b"%PDF-")
    assert pdf_bytes.rstrip().endswith(b"%%EOF")
    assert len(pdf_bytes) > 4000
    assert len(
        re.findall(
            rb"/Type\s*/Page\b",
            pdf_bytes,
        )
    ) >= 2


def test_policy_story_contains_cover_break_and_tables():
    story = _build_story(
        document=_document(),
        styles=_build_styles(),
    )

    assert any(
        isinstance(flowable, PageBreak)
        for flowable in story
    )
    assert len(
        [
            flowable
            for flowable in story
            if isinstance(flowable, Table)
        ]
    ) >= 5


def test_draft_notice_appears_once_and_metadata_is_hidden():
    text = _story_text(_document())

    assert text.count(DRAFT_NOTICE) == 1
    assert "internal.policy.reference" not in text
    assert "4.1.1.3" not in text
    assert "Prototype coverage" not in text
    assert "Approved controls" not in text
    assert "Not completed" not in text
    assert "Source references" not in text
    assert "Appendix" not in text


def test_approved_document_omits_draft_notice():
    text = _story_text(
        _document(document_status="approved")
    )

    assert DRAFT_NOTICE not in text
    assert "Document status" in text
    assert "Approved" in text


def test_content_block_order_is_preserved():
    text = _story_text(_document())

    expected_values = [
        "1. Food Safety Policy",
        "Controlled food safety policy.",
        "Responsibilities",
        "Staff follow approved controls.",
        "Managers review records.",
        "1.1 Purpose and Scope",
        "Complete the first check.",
        "Complete the second check.",
        (
            "2. Business Scope and Food Safety "
            "Overview"
        ),
    ]

    positions = [
        text.index(value)
        for value in expected_values
    ]

    assert positions == sorted(positions)


def test_normalise_text_replaces_unsupported_punctuation():
    assert _normalise_text(
        "−18°C – manager’s “check”"
    ) == '-18°C - manager\'s "check"'


def test_table_widths_fill_available_content_width():
    for column_count in [
        2,
        5,
        6,
        3,
    ]:
        widths = _table_column_widths(
            column_count
        )

        assert len(widths) == column_count
        assert abs(
            sum(widths) - CONTENT_WIDTH
        ) < 0.001

def test_checklist_subsection_keeps_heading_fields_and_table_together():
    subsection = FSMSPolicySubsection(
        subsection_number="3.6",
        title="Fridge Temperature Checklist",
        content_blocks=[
            {
                "block_type": "text",
                "role": "monitoring",
                "text": (
                    "Date: ____________________\n"
                    "Shift / service: ____________________\n"
                    "Person in charge: ____________________"
                ),
            },
            {
                "block_type": "table",
                "role": "checklist",
                "heading": (
                    "Daily chilling temperature checks"
                ),
                "headers": [
                    "Equipment",
                    "Required limit",
                    "AM temperature",
                    "PM temperature",
                    (
                        "Corrective action / "
                        "diary reference"
                    ),
                ],
                "rows": [
                    [
                        "Fridge 1",
                        "8°C or below",
                        "",
                        "",
                        "",
                    ],
                ],
            },
            {
                "block_type": "text",
                "role": "monitoring",
                "text": (
                    "Record the actual temperature "
                    "shown or measured."
                ),
            },
        ],
    )

    flowables = _subsection_flowables(
        subsection=subsection,
        styles=_build_styles(),
    )

    assert isinstance(flowables[0], KeepTogether)

    grouped_text = "\n".join(
        _flowable_text(
            flowables[0]._content
        )
    )
    trailing_text = "\n".join(
        _flowable_text(flowables[1:])
    )

    assert (
        "3.6 Fridge Temperature Checklist"
        in grouped_text
    )
    assert "Date:" in grouped_text
    assert "Shift / service:" in grouped_text
    assert "Person in charge:" in grouped_text
    assert (
        "Daily chilling temperature checks"
        in grouped_text
    )
    assert "Fridge 1" in grouped_text
    assert (
        "Record the actual temperature"
        not in grouped_text
    )
    assert (
        "Record the actual temperature"
        in trailing_text
    )


def test_six_column_asset_code_remains_on_one_line():
    styles = _build_styles()
    widths = _table_column_widths(6)
    paragraph = _table_cell_paragraph(
        "CHILL-20260622-0010",
        styles=styles,
    )

    _, height = paragraph.wrap(
        widths[0] - 8,
        100,
    )

    assert height == styles["table_body"].leading
