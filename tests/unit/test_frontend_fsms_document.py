import sys
from pathlib import Path


ROOT_PATH = Path(__file__).resolve().parents[2]
FRONTEND_PATH = ROOT_PATH / "frontend"

if str(FRONTEND_PATH) not in sys.path:
    sys.path.insert(
        0,
        str(FRONTEND_PATH),
    )

from views import fsms_document


class FakeResponse:
    def __init__(
        self,
        *,
        status_code,
        payload=None,
        content=b"",
    ):
        self.status_code = status_code
        self.payload = payload or {}
        self.content = content

    def json(self):
        return self.payload


def test_load_fsms_document_uses_canonical_endpoint(
    monkeypatch,
):
    calls = {}

    def fake_api_request(
        method,
        endpoint,
        token=None,
    ):
        calls["method"] = method
        calls["endpoint"] = endpoint
        calls["token"] = token

        return FakeResponse(
            status_code=200,
            payload={
                "document_title": "Test FSMS",
            },
        )

    monkeypatch.setattr(
        fsms_document,
        "api_request",
        fake_api_request,
    )

    result = fsms_document.load_fsms_document(
        "test-token"
    )

    assert result == {
        "document_title": "Test FSMS",
    }
    assert calls == {
        "method": "GET",
        "endpoint": "/fsms-document",
        "token": "test-token",
    }


def test_load_fsms_document_reports_no_response(
    monkeypatch,
):
    errors = []

    monkeypatch.setattr(
        fsms_document,
        "api_request",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        fsms_document.st,
        "error",
        errors.append,
    )

    result = fsms_document.load_fsms_document(
        "test-token"
    )

    assert result is None
    assert errors == [
        (
            "Unable to load the Food Safety Management "
            "System document because the backend did not "
            "respond."
        )
    ]


def test_load_fsms_document_reports_backend_error(
    monkeypatch,
):
    errors = []

    monkeypatch.setattr(
        fsms_document,
        "api_request",
        lambda *args, **kwargs: FakeResponse(
            status_code=500,
            payload={
                "detail": (
                    "Document generation failed."
                ),
            },
        ),
    )
    monkeypatch.setattr(
        fsms_document.st,
        "error",
        errors.append,
    )

    result = fsms_document.load_fsms_document(
        "test-token"
    )

    assert result is None
    assert errors == [
        "Document generation failed.",
    ]


def test_load_fsms_document_pdf_uses_canonical_endpoint(
    monkeypatch,
):
    calls = {}

    def fake_api_request(
        method,
        endpoint,
        token=None,
    ):
        calls["method"] = method
        calls["endpoint"] = endpoint
        calls["token"] = token

        return FakeResponse(
            status_code=200,
            content=b"%PDF-test",
        )

    monkeypatch.setattr(
        fsms_document,
        "api_request",
        fake_api_request,
    )

    result = (
        fsms_document.load_fsms_document_pdf(
            "test-token"
        )
    )

    assert result == b"%PDF-test"
    assert calls == {
        "method": "GET",
        "endpoint": "/fsms-document/pdf",
        "token": "test-token",
    }


def test_load_fsms_document_pdf_failure_does_not_block_preview(
    monkeypatch,
):
    warnings = []

    monkeypatch.setattr(
        fsms_document,
        "api_request",
        lambda *args, **kwargs: FakeResponse(
            status_code=500,
            payload={
                "detail": "PDF generation failed.",
            },
        ),
    )
    monkeypatch.setattr(
        fsms_document.st,
        "warning",
        warnings.append,
    )

    result = (
        fsms_document.load_fsms_document_pdf(
            "test-token"
        )
    )

    assert result is None
    assert warnings == [
        "PDF generation failed.",
    ]


def test_build_pdf_filename_uses_site_name():
    assert fsms_document.build_pdf_filename(
        {
            "business_name": (
                "Example Foods Ltd"
            ),
            "site_name": (
                "Example Kitchen & Bar"
            ),
        }
    ) == "example-kitchen-bar-fsms.pdf"


def test_build_pdf_filename_uses_safe_fallback():
    assert fsms_document.build_pdf_filename(
        {
            "business_name": "***",
            "site_name": "",
        }
    ) == (
        "food-safety-management-system-fsms.pdf"
    )


def test_format_generated_at_formats_iso_datetime():
    assert fsms_document.format_generated_at(
        "2026-07-19T12:34:00Z"
    ) == "19 July 2026 at 12:34 UTC"


def test_table_records_use_headers_and_fill_missing_values():
    records = fsms_document.table_records(
        {
            "headers": [
                "Equipment",
                "Required limit",
                "AM temperature",
            ],
            "rows": [
                [
                    "Main fridge",
                    "8°C or below",
                    "",
                ],
                [
                    "Chest freezer",
                    "-18°C or below",
                ],
            ],
        }
    )

    assert records == [
        {
            "Equipment": "Main fridge",
            "Required limit": "8°C or below",
            "AM temperature": "",
        },
        {
            "Equipment": "Chest freezer",
            "Required limit": "-18°C or below",
            "AM temperature": "",
        },
    ]


def test_render_content_blocks_preserves_order_and_hides_sources(
    monkeypatch,
):
    events = []

    monkeypatch.setattr(
        fsms_document.st,
        "markdown",
        lambda value: events.append(
            ("markdown", value)
        ),
    )
    monkeypatch.setattr(
        fsms_document.st,
        "write",
        lambda value: events.append(
            ("write", value)
        ),
    )
    monkeypatch.setattr(
        fsms_document.st,
        "dataframe",
        lambda value, **kwargs: events.append(
            ("dataframe", value)
        ),
    )

    fsms_document.render_content_blocks(
        [
            {
                "block_type": "text",
                "role": "policy",
                "heading": "Policy",
                "text": "Controlled policy text.",
                "source": {
                    "source_references": [
                        "hidden.reference",
                    ],
                },
            },
            {
                "block_type": "list",
                "role": "procedure",
                "heading": "Procedure",
                "items": [
                    "First action.",
                    "Second action.",
                ],
                "source": {
                    "safety_point_ids": [
                        "hidden.id",
                    ],
                },
            },
            {
                "block_type": "table",
                "role": "monitoring",
                "heading": "Checks",
                "headers": [
                    "Equipment",
                    "Limit",
                ],
                "rows": [
                    [
                        "Main fridge",
                        "8°C or below",
                    ],
                ],
            },
        ]
    )

    assert events == [
        ("markdown", "**Policy**"),
        ("write", "Controlled policy text."),
        ("markdown", "**Procedure**"),
        ("markdown", "- First action."),
        ("markdown", "- Second action."),
        ("markdown", "**Checks**"),
        (
            "dataframe",
            [
                {
                    "Equipment": "Main fridge",
                    "Limit": "8°C or below",
                }
            ],
        ),
    ]

    rendered_values = str(events)

    assert "hidden.reference" not in rendered_values
    assert "hidden.id" not in rendered_values


def test_render_ordered_list_uses_numbered_items(
    monkeypatch,
):
    markdown_values = []

    monkeypatch.setattr(
        fsms_document.st,
        "markdown",
        markdown_values.append,
    )

    fsms_document.render_list_block(
        {
            "block_type": "list",
            "ordered": True,
            "items": [
                "Complete the first check.",
                "Complete the second check.",
            ],
        }
    )

    assert markdown_values == [
        "1. Complete the first check.",
        "2. Complete the second check.",
    ]


def test_render_section_preserves_section_and_subsection_order(
    monkeypatch,
):
    events = []

    monkeypatch.setattr(
        fsms_document.st,
        "header",
        lambda value: events.append(
            ("header", value)
        ),
    )
    monkeypatch.setattr(
        fsms_document.st,
        "subheader",
        lambda value: events.append(
            ("subheader", value)
        ),
    )
    monkeypatch.setattr(
        fsms_document,
        "render_content_blocks",
        lambda blocks: events.append(
            ("blocks", blocks)
        ),
    )

    section_blocks = [
        {
            "block_type": "text",
            "text": "Section policy.",
        }
    ]
    first_subsection_blocks = [
        {
            "block_type": "text",
            "text": "First procedure.",
        }
    ]
    second_subsection_blocks = [
        {
            "block_type": "text",
            "text": "Second procedure.",
        }
    ]

    fsms_document.render_section(
        {
            "section_number": "3",
            "title": (
                "Chilling and Temperature Control"
            ),
            "content_blocks": section_blocks,
            "subsections": [
                {
                    "subsection_number": "3.1",
                    "title": (
                        "Chilled Storage and Display"
                    ),
                    "content_blocks": (
                        first_subsection_blocks
                    ),
                },
                {
                    "subsection_number": "3.2",
                    "title": "Cooling Hot Food",
                    "content_blocks": (
                        second_subsection_blocks
                    ),
                },
            ],
        }
    )

    assert events == [
        (
            "header",
            (
                "3. Chilling and Temperature "
                "Control"
            ),
        ),
        ("blocks", section_blocks),
        (
            "subheader",
            "3.1 Chilled Storage and Display",
        ),
        ("blocks", first_subsection_blocks),
        (
            "subheader",
            "3.2 Cooling Hot Food",
        ),
        ("blocks", second_subsection_blocks),
    ]


def test_render_draft_notice_only_for_draft(
    monkeypatch,
):
    warnings = []

    monkeypatch.setattr(
        fsms_document.st,
        "warning",
        warnings.append,
    )

    fsms_document.render_draft_notice(
        {
            "document_status": "draft",
            "draft_notice": (
                "This document is incomplete."
            ),
        }
    )
    fsms_document.render_draft_notice(
        {
            "document_status": "approved",
            "draft_notice": None,
        }
    )

    assert warnings == [
        "This document is incomplete.",
    ]


def test_show_renders_policy_document_and_download(
    monkeypatch,
):
    document = {
        "document_title": (
            "Food Safety Management System"
        ),
        "document_status": "draft",
        "draft_notice": (
            "This document is incomplete."
        ),
        "business_name": "Example Foods Ltd",
        "site_name": "Example Kitchen",
        "sections": [
            {
                "section_number": "1",
                "title": "Food Safety Policy",
            },
            {
                "section_number": "2",
                "title": "Business Scope",
            },
        ],
    }
    events = []

    monkeypatch.setattr(
        fsms_document.st,
        "session_state",
        {
            "token": "test-token",
        },
        raising=False,
    )
    monkeypatch.setattr(
        fsms_document,
        "load_fsms_document",
        lambda token: document,
    )
    monkeypatch.setattr(
        fsms_document,
        "load_fsms_document_pdf",
        lambda token: b"%PDF-test",
    )
    monkeypatch.setattr(
        fsms_document.st,
        "title",
        lambda value: events.append(
            ("title", value)
        ),
    )
    monkeypatch.setattr(
        fsms_document.st,
        "caption",
        lambda value: events.append(
            ("caption", value)
        ),
    )
    monkeypatch.setattr(
        fsms_document.st,
        "download_button",
        lambda label, **kwargs: events.append(
            (
                "download",
                label,
                kwargs,
            )
        ),
    )
    monkeypatch.setattr(
        fsms_document,
        "render_document_details",
        lambda value: events.append(
            ("details", value)
        ),
    )
    monkeypatch.setattr(
        fsms_document,
        "render_draft_notice",
        lambda value: events.append(
            ("notice", value)
        ),
    )
    monkeypatch.setattr(
        fsms_document,
        "render_section",
        lambda value: events.append(
            ("section", value)
        ),
    )

    fsms_document.show()

    assert events[0] == (
        "title",
        "Food Safety Management System",
    )
    assert events[2] == (
        "details",
        document,
    )
    assert events[3] == (
        "notice",
        document,
    )
    assert events[4][0:2] == (
        "download",
        "Download PDF",
    )
    assert events[4][2] == {
        "data": b"%PDF-test",
        "file_name": (
            "example-kitchen-fsms.pdf"
        ),
        "mime": "application/pdf",
    }
    assert [
        event
        for event in events
        if event[0] == "section"
    ] == [
        ("section", document["sections"][0]),
        ("section", document["sections"][1]),
    ]


def test_frontend_navigation_registers_fsms_document():
    app_text = (
        FRONTEND_PATH / "app.py"
    ).read_text(encoding="utf-8")

    assert (
        "from views.fsms_document import "
        "show as fsms_document_page"
        in app_text
    )
    assert '"food_safety_fsms_document"' in app_text
    assert (
        '"FSMS Document": '
        '"food_safety_fsms_document"'
        in app_text
    )
    assert 'sac.MenuItem("FSMS Document")' in app_text
