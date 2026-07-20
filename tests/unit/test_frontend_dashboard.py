import sys
from pathlib import Path


ROOT_PATH = Path(__file__).resolve().parents[2]
FRONTEND_PATH = ROOT_PATH / "frontend"

if str(FRONTEND_PATH) not in sys.path:
    sys.path.insert(
        0,
        str(FRONTEND_PATH),
    )

from views import dashboard


class FakeResponse:
    def __init__(
        self,
        *,
        status_code,
        payload=None,
    ):
        self.status_code = status_code
        self.payload = payload or {}

    def json(self):
        return self.payload


def test_load_fsms_document_progress_uses_policy_endpoint(
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
                "screening_complete": True,
                "completed_applicable_section_count": 3,
                "applicable_supported_section_count": 4,
                "completion_percentage": 75,
                "supported_section_count": 4,
                "planned_section_count": 10,
                "document_status": "in_progress",
                "main_value": "75%",
                "completion_caption": (
                    "3 of 4 current sections complete"
                ),
                "coverage_caption": (
                    "4 of 10 planned sections supported"
                ),
            },
        )

    monkeypatch.setattr(
        dashboard,
        "api_request",
        fake_api_request,
    )

    result = (
        dashboard
        .load_fsms_document_dashboard_progress(
            "test-token"
        )
    )

    assert calls == {
        "method": "GET",
        "endpoint": (
            "/fsms-document/policy/progress"
        ),
        "token": "test-token",
    }
    assert result == {
        "icon_label": "DOC",
        "title": "FSMS Document",
        "value": "75%",
        "caption": (
            "3/4 current · 4/10 supported"
        ),
        "colour_class": "",
    }


def test_completed_fsms_document_card_is_green(
    monkeypatch,
):
    monkeypatch.setattr(
        dashboard,
        "api_request",
        lambda *args, **kwargs: FakeResponse(
            status_code=200,
            payload={
                "screening_complete": True,
                "completed_applicable_section_count": 3,
                "applicable_supported_section_count": 3,
                "completion_percentage": 100,
                "supported_section_count": 4,
                "planned_section_count": 10,
            },
        ),
    )

    result = (
        dashboard
        .load_fsms_document_dashboard_progress(
            "test-token"
        )
    )

    assert result == {
        "icon_label": "DOC",
        "title": "FSMS Document",
        "value": "100%",
        "caption": (
            "3/3 current · 4/10 supported"
        ),
        "colour_class": "green",
    }



def test_incomplete_profile_uses_clear_document_caption(
    monkeypatch,
):
    monkeypatch.setattr(
        dashboard,
        "api_request",
        lambda *args, **kwargs: FakeResponse(
            status_code=200,
            payload={
                "screening_complete": False,
                "completed_applicable_section_count": 0,
                "applicable_supported_section_count": 2,
                "completion_percentage": 0,
                "supported_section_count": 4,
                "planned_section_count": 10,
                "document_status": "not_started",
                "main_value": "0%",
                "completion_caption": (
                    "Food Safety Profile not completed"
                ),
                "coverage_caption": (
                    "4 of 10 planned sections supported"
                ),
            },
        ),
    )

    result = (
        dashboard
        .load_fsms_document_dashboard_progress(
            "test-token"
        )
    )

    assert result == {
        "icon_label": "DOC",
        "title": "FSMS Document",
        "value": "0%",
        "caption": (
            "Food Safety Profile not completed · "
            "4/10 supported"
        ),
        "colour_class": "",
    }

def test_fsms_document_progress_without_token_is_unavailable(
    monkeypatch,
):
    def fail_if_called(*args, **kwargs):
        raise AssertionError(
            "The API must not be called without a token."
        )

    monkeypatch.setattr(
        dashboard,
        "api_request",
        fail_if_called,
    )

    result = (
        dashboard
        .load_fsms_document_dashboard_progress(
            None
        )
    )

    assert result == {
        "icon_label": "DOC",
        "title": "FSMS Document",
        "value": "0%",
        "caption": "Progress unavailable",
        "colour_class": "",
    }


def test_fsms_document_progress_handles_no_response(
    monkeypatch,
):
    monkeypatch.setattr(
        dashboard,
        "api_request",
        lambda *args, **kwargs: None,
    )

    result = (
        dashboard
        .load_fsms_document_dashboard_progress(
            "test-token"
        )
    )

    assert result["value"] == "0%"
    assert (
        result["caption"]
        == "Progress unavailable"
    )
    assert result["colour_class"] == ""


def test_fsms_document_progress_handles_error_response(
    monkeypatch,
):
    monkeypatch.setattr(
        dashboard,
        "api_request",
        lambda *args, **kwargs: FakeResponse(
            status_code=500,
        ),
    )

    result = (
        dashboard
        .load_fsms_document_dashboard_progress(
            "test-token"
        )
    )

    assert result["value"] == "0%"
    assert (
        result["caption"]
        == "Progress unavailable"
    )


def test_dashboard_replaces_documents_ready_dummy_card():
    dashboard_text = (
        FRONTEND_PATH / "views" / "dashboard.py"
    ).read_text(encoding="utf-8")

    assert (
        "load_fsms_document_dashboard_progress(token)"
        in dashboard_text
    )
    assert "{fsms_document_card}" in dashboard_text
    assert '"Documents Ready"' not in dashboard_text
    assert '"Inspection documents"' not in dashboard_text


def test_dashboard_uses_requested_status_card_order():
    dashboard_text = (
        FRONTEND_PATH / "views" / "dashboard.py"
    ).read_text(encoding="utf-8")

    block_start = dashboard_text.index(
        'status_cards_html = f"""'
    )
    block_end = dashboard_text.index(
        '"""',
        block_start + len('status_cards_html = f"""'),
    )
    card_block = dashboard_text[
        block_start:block_end
    ]

    document_position = card_block.index(
        "{fsms_document_card}"
    )
    fridge_position = card_block.index(
        "{fridge_temperature_card}"
    )
    staff_position = card_block.index(
        '{dummy_status_card_html('
        '"TRN", "Staff Trained"'
    )

    assert document_position < fridge_position
    assert fridge_position < staff_position
