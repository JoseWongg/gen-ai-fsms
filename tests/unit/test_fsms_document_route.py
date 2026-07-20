from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.routing import APIRoute

from gen_ai_fsms.api.deps import get_current_user
from gen_ai_fsms.api.routes import (
    fsms_document as route_module,
)
from gen_ai_fsms.main import app
from gen_ai_fsms.schemas.fsms_policy_document import (
    FSMSPolicyDocument,
    FSMSPolicyDocumentProgress,
)


def _policy_document(
    *,
    document_status="draft",
):
    return FSMSPolicyDocument(
        document_title=(
            "Food Safety Management System"
        ),
        document_status=document_status,
        draft_notice=(
            "This document is incomplete."
            if document_status == "draft"
            else None
        ),
        business_name="Example Foods Ltd",
        site_name="Example Kitchen",
        business_type="Restaurant",
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
                            "Controlled policy text."
                        ),
                    },
                ],
            },
        ],
    )


def _policy_progress():
    return FSMSPolicyDocumentProgress(
        screening_complete=True,
        completed_applicable_section_count=3,
        applicable_supported_section_count=4,
        completion_percentage=75,
        supported_section_count=4,
        planned_section_count=10,
        document_status="in_progress",
        main_value="75%",
        completion_caption=(
            "3 of 4 current sections complete"
        ),
        coverage_caption=(
            "4 of 10 planned sections supported"
        ),
    )


def test_document_route_generates_policy_document(
    monkeypatch,
):
    db = object()
    current_user = SimpleNamespace(id=12)
    profile = SimpleNamespace(id=34)
    expected_document = _policy_document()
    calls = {}

    monkeypatch.setattr(
        route_module,
        "get_current_user_profile",
        lambda received_db, received_user: profile,
    )

    def fake_generate(
        *,
        db,
        business_profile_id,
    ):
        calls["db"] = db
        calls["business_profile_id"] = (
            business_profile_id
        )

        return expected_document

    monkeypatch.setattr(
        route_module,
        "generate_fsms_policy_document_for_profile",
        fake_generate,
    )

    result = route_module.get_current_fsms_document(
        db=db,
        current_user=current_user,
    )

    assert result is expected_document
    assert calls == {
        "db": db,
        "business_profile_id": 34,
    }


def test_document_route_rejects_missing_profile(
    monkeypatch,
):
    monkeypatch.setattr(
        route_module,
        "get_current_user_profile",
        lambda db, current_user: (
            _raise_missing_profile()
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        route_module.get_current_fsms_document(
            db=object(),
            current_user=SimpleNamespace(id=12),
        )

    assert exc_info.value.status_code == 404


def _raise_missing_profile():
    raise HTTPException(
        status_code=404,
        detail=(
            "No business profile is linked to the "
            "current user"
        ),
    )


def test_document_route_is_canonical_and_authenticated():
    route = _get_route("/fsms-document")

    assert route.methods == {"GET"}
    assert (
        route.response_model
        is FSMSPolicyDocument
    )
    assert get_current_user in {
        dependency.call
        for dependency
        in route.dependant.dependencies
    }


@pytest.mark.parametrize(
    (
        "document_status",
        "expected_notice",
    ),
    [
        (
            "draft",
            "This document is incomplete.",
        ),
        (
            "approved",
            None,
        ),
    ],
)
def test_document_route_serializes_policy_contract(
    monkeypatch,
    document_status,
    expected_notice,
):
    document = _policy_document(
        document_status=document_status
    )

    monkeypatch.setattr(
        route_module,
        "get_current_user_profile",
        lambda db, current_user: SimpleNamespace(
            id=34
        ),
    )
    monkeypatch.setattr(
        route_module,
        "generate_fsms_policy_document_for_profile",
        lambda **kwargs: document,
    )

    result = route_module.get_current_fsms_document(
        db=object(),
        current_user=SimpleNamespace(id=12),
    )
    payload = jsonable_encoder(result)

    assert payload["document_status"] == (
        document_status
    )
    assert payload["draft_notice"] == (
        expected_notice
    )
    assert payload["sections"][0][
        "content_blocks"
    ][0]["block_type"] == "text"


def test_pdf_route_returns_policy_pdf(
    monkeypatch,
):
    db = object()
    document = _policy_document()
    calls = {}

    monkeypatch.setattr(
        route_module,
        "get_current_user_profile",
        lambda received_db, received_user: (
            SimpleNamespace(id=34)
        ),
    )

    def fake_generate(
        *,
        db,
        business_profile_id,
    ):
        calls["db"] = db
        calls["business_profile_id"] = (
            business_profile_id
        )

        return document

    monkeypatch.setattr(
        route_module,
        "generate_fsms_policy_document_for_profile",
        fake_generate,
    )
    monkeypatch.setattr(
        route_module,
        "render_fsms_policy_document_pdf",
        lambda received_document: b"%PDF-policy",
    )

    response = (
        route_module
        .download_current_fsms_document_pdf(
            db=db,
            current_user=SimpleNamespace(id=12),
        )
    )

    assert response.body == b"%PDF-policy"
    assert response.media_type == (
        "application/pdf"
    )
    assert response.headers[
        "content-disposition"
    ] == (
        'attachment; '
        'filename="example-kitchen-fsms.pdf"'
    )
    assert calls == {
        "db": db,
        "business_profile_id": 34,
    }


def test_pdf_route_rejects_missing_profile(
    monkeypatch,
):
    monkeypatch.setattr(
        route_module,
        "get_current_user_profile",
        lambda db, current_user: (
            _raise_missing_profile()
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        (
            route_module
            .download_current_fsms_document_pdf(
                db=object(),
                current_user=SimpleNamespace(id=12),
            )
        )

    assert exc_info.value.status_code == 404


def test_pdf_route_is_canonical_and_authenticated():
    route = _get_route(
        "/fsms-document/pdf"
    )

    assert route.methods == {"GET"}
    assert get_current_user in {
        dependency.call
        for dependency
        in route.dependant.dependencies
    }


def test_progress_route_generates_progress(
    monkeypatch,
):
    db = object()
    expected_progress = _policy_progress()
    calls = {}

    monkeypatch.setattr(
        route_module,
        "get_current_user_profile",
        lambda received_db, received_user: (
            SimpleNamespace(id=34)
        ),
    )

    def fake_generate(
        *,
        db,
        business_profile_id,
    ):
        calls["db"] = db
        calls["business_profile_id"] = (
            business_profile_id
        )

        return expected_progress

    monkeypatch.setattr(
        route_module,
        (
            "generate_fsms_policy_document_"
            "progress_for_profile"
        ),
        fake_generate,
    )

    result = (
        route_module
        .get_current_fsms_document_progress(
            db=db,
            current_user=SimpleNamespace(id=12),
        )
    )

    assert result is expected_progress
    assert calls == {
        "db": db,
        "business_profile_id": 34,
    }


def test_progress_route_rejects_missing_profile(
    monkeypatch,
):
    monkeypatch.setattr(
        route_module,
        "get_current_user_profile",
        lambda db, current_user: (
            _raise_missing_profile()
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        (
            route_module
            .get_current_fsms_document_progress(
                db=object(),
                current_user=SimpleNamespace(id=12),
            )
        )

    assert exc_info.value.status_code == 404


def test_progress_route_is_canonical_and_authenticated():
    route = _get_route(
        "/fsms-document/progress"
    )

    assert route.methods == {"GET"}
    assert (
        route.response_model
        is FSMSPolicyDocumentProgress
    )
    assert get_current_user in {
        dependency.call
        for dependency
        in route.dependant.dependencies
    }


def test_progress_route_serializes_contract(
    monkeypatch,
):
    progress = _policy_progress()

    monkeypatch.setattr(
        route_module,
        "get_current_user_profile",
        lambda db, current_user: SimpleNamespace(
            id=34
        ),
    )
    monkeypatch.setattr(
        route_module,
        (
            "generate_fsms_policy_document_"
            "progress_for_profile"
        ),
        lambda **kwargs: progress,
    )

    result = (
        route_module
        .get_current_fsms_document_progress(
            db=object(),
            current_user=SimpleNamespace(id=12),
        )
    )

    assert jsonable_encoder(result) == {
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
    }


def test_temporary_policy_routes_are_removed():
    paths = {
        route.path
        for route in app.routes
        if isinstance(route, APIRoute)
    }

    assert "/fsms-document/policy" not in paths
    assert (
        "/fsms-document/policy/pdf"
        not in paths
    )
    assert (
        "/fsms-document/policy/progress"
        not in paths
    )


def _get_route(path):
    matching_routes = [
        route
        for route in app.routes
        if (
            isinstance(route, APIRoute)
            and route.path == path
        )
    ]

    assert len(matching_routes) == 1

    return matching_routes[0]
