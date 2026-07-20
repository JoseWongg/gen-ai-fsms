import sys
from pathlib import Path


ROOT_PATH = Path(__file__).resolve().parents[2]
FRONTEND_PATH = ROOT_PATH / "frontend"

if str(FRONTEND_PATH) not in sys.path:
    sys.path.insert(0, str(FRONTEND_PATH))

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


def test_load_fsms_document_uses_authenticated_endpoint(
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
            payload={"document_title": "Test FSMS"},
        )

    monkeypatch.setattr(
        fsms_document,
        "api_request",
        fake_api_request,
    )

    result = fsms_document.load_fsms_document(
        "test-token"
    )

    assert result == {"document_title": "Test FSMS"}
    assert calls == {
        "method": "GET",
        "endpoint": "/fsms-document",
        "token": "test-token",
    }


def test_load_fsms_document_reports_backend_error(
    monkeypatch,
):
    errors = []

    monkeypatch.setattr(
        fsms_document,
        "api_request",
        lambda *args, **kwargs: FakeResponse(
            status_code=500,
            payload={"detail": "Document generation failed."},
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
    assert errors == ["Document generation failed."]


def test_format_generated_at_formats_iso_datetime():
    assert fsms_document.format_generated_at(
        "2026-07-19T12:34:00Z"
    ) == "19 July 2026 at 12:34 UTC"


def test_arrangement_table_records_use_headers():
    records = fsms_document.arrangement_table_records(
        {
            "table_headers": [
                "Equipment",
                "Type",
                "Use",
            ],
            "table_rows": [
                ["Fridge 1", "Fridge", "Storage"],
                ["Freezer 1", "Freezer"],
            ],
        }
    )

    assert records == [
        {
            "Equipment": "Fridge 1",
            "Type": "Fridge",
            "Use": "Storage",
        },
        {
            "Equipment": "Freezer 1",
            "Type": "Freezer",
            "Use": "",
        },
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



def test_load_fsms_document_pdf_uses_authenticated_endpoint(
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

    result = fsms_document.load_fsms_document_pdf(
        "test-token"
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
            payload={"detail": "PDF generation failed."},
        ),
    )
    monkeypatch.setattr(
        fsms_document.st,
        "warning",
        warnings.append,
    )

    result = fsms_document.load_fsms_document_pdf(
        "test-token"
    )

    assert result is None
    assert warnings == ["PDF generation failed."]


def test_build_pdf_filename_uses_site_name():
    assert fsms_document.build_pdf_filename(
        {
            "business_name": "Example Foods Ltd",
            "site_name": "Example Kitchen & Bar",
        }
    ) == "example-kitchen-bar-fsms.pdf"
