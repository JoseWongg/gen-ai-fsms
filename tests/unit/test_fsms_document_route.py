from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.routing import APIRoute

from gen_ai_fsms.api.deps import get_current_user
from gen_ai_fsms.api.routes import fsms_document as route_module
from gen_ai_fsms.main import app
from gen_ai_fsms.schemas.fsms_document import FSMSDocument
from gen_ai_fsms.schemas.fsms_policy_document import (
    FSMSPolicyDocument,
    FSMSPolicyDocumentProgress,
)


def test_route_generates_document_for_linked_profile(
    monkeypatch,
):
    db = object()
    current_user = SimpleNamespace(id=12)
    profile = SimpleNamespace(id=34)
    expected_document = object()
    calls = {}

    def fake_get_current_user_profile(
        received_db,
        received_user,
    ):
        calls["profile_db"] = received_db
        calls["current_user"] = received_user
        return profile

    def fake_generate_fsms_document_for_profile(
        *,
        db,
        business_profile_id,
    ):
        calls["service_db"] = db
        calls["business_profile_id"] = business_profile_id
        return expected_document

    monkeypatch.setattr(
        route_module,
        "get_current_user_profile",
        fake_get_current_user_profile,
    )
    monkeypatch.setattr(
        route_module,
        "generate_fsms_document_for_profile",
        fake_generate_fsms_document_for_profile,
    )

    result = route_module.get_current_fsms_document(
        db=db,
        current_user=current_user,
    )

    assert result is expected_document
    assert calls == {
        "profile_db": db,
        "current_user": current_user,
        "service_db": db,
        "business_profile_id": 34,
    }


def test_route_does_not_generate_document_without_profile(
    monkeypatch,
):
    def reject_missing_profile(db, current_user):
        raise HTTPException(
            status_code=404,
            detail=(
                "No business profile is linked to the current user"
            ),
        )

    def fail_if_service_called(**kwargs):
        raise AssertionError(
            "Document service must not run without a profile."
        )

    monkeypatch.setattr(
        route_module,
        "get_current_user_profile",
        reject_missing_profile,
    )
    monkeypatch.setattr(
        route_module,
        "generate_fsms_document_for_profile",
        fail_if_service_called,
    )

    with pytest.raises(HTTPException) as exc_info:
        route_module.get_current_fsms_document(
            db=object(),
            current_user=SimpleNamespace(id=12),
        )

    assert exc_info.value.status_code == 404


def test_fsms_document_route_is_registered_and_authenticated():
    matching_routes = [
        route
        for route in app.routes
        if (
            isinstance(route, APIRoute)
            and route.path == "/fsms-document"
        )
    ]

    assert len(matching_routes) == 1

    route = matching_routes[0]

    assert route.methods == {"GET"}
    assert route.response_model is FSMSDocument

    dependency_calls = {
        dependency.call
        for dependency in route.dependant.dependencies
    }

    assert get_current_user in dependency_calls



def test_pdf_route_returns_downloadable_pdf(
    monkeypatch,
):
    db = object()
    current_user = SimpleNamespace(id=12)
    profile = SimpleNamespace(id=34)
    document = SimpleNamespace(
        business_name="Example Foods Ltd",
        site_name="Example Kitchen",
    )
    calls = {}

    monkeypatch.setattr(
        route_module,
        "get_current_user_profile",
        lambda received_db, received_user: profile,
    )

    def fake_generate_fsms_document_for_profile(
        *,
        db,
        business_profile_id,
    ):
        calls["db"] = db
        calls["business_profile_id"] = business_profile_id
        return document

    monkeypatch.setattr(
        route_module,
        "generate_fsms_document_for_profile",
        fake_generate_fsms_document_for_profile,
    )
    monkeypatch.setattr(
        route_module,
        "render_fsms_document_pdf",
        lambda received_document: b"%PDF-test",
    )

    response = (
        route_module.download_current_fsms_document_pdf(
            db=db,
            current_user=current_user,
        )
    )

    assert response.body == b"%PDF-test"
    assert response.media_type == "application/pdf"
    assert response.headers["content-disposition"] == (
        'attachment; filename="example-kitchen-fsms.pdf"'
    )
    assert calls == {
        "db": db,
        "business_profile_id": 34,
    }


def test_fsms_document_pdf_route_is_registered_and_authenticated():
    matching_routes = [
        route
        for route in app.routes
        if (
            isinstance(route, APIRoute)
            and route.path == "/fsms-document/pdf"
        )
    ]

    assert len(matching_routes) == 1

    route = matching_routes[0]

    assert route.methods == {"GET"}

    dependency_calls = {
        dependency.call
        for dependency in route.dependant.dependencies
    }

    assert get_current_user in dependency_calls

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
                            "Controlled policy text."
                        ),
                        "source": {
                            "source_references": [
                                "controlled.policy",
                            ],
                        },
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
                        "block_type": "list",
                        "role": "business_context",
                        "items": [
                            "Preparing food on site.",
                        ],
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
                        "role": "monitoring",
                        "headers": [
                            "Equipment",
                            "Required limit",
                        ],
                        "rows": [
                            [
                                "Main fridge",
                                "8°C or below",
                            ],
                        ],
                    }
                ],
            },
            {
                "section_number": "4",
                "title": "Cooking and Reheating",
            },
        ],
    )


def test_policy_route_generates_document_for_linked_profile(
    monkeypatch,
):
    db = object()
    current_user = SimpleNamespace(id=12)
    profile = SimpleNamespace(id=34)
    expected_document = _policy_document()
    calls = {}

    def fake_get_current_user_profile(
        received_db,
        received_user,
    ):
        calls["profile_db"] = received_db
        calls["current_user"] = received_user

        return profile

    def fake_generate_fsms_policy_document_for_profile(
        *,
        db,
        business_profile_id,
    ):
        calls["service_db"] = db
        calls["business_profile_id"] = (
            business_profile_id
        )

        return expected_document

    monkeypatch.setattr(
        route_module,
        "get_current_user_profile",
        fake_get_current_user_profile,
    )
    monkeypatch.setattr(
        route_module,
        "generate_fsms_policy_document_for_profile",
        (
            fake_generate_fsms_policy_document_for_profile
        ),
    )

    result = (
        route_module.get_current_fsms_policy_document(
            db=db,
            current_user=current_user,
        )
    )

    assert result is expected_document
    assert calls == {
        "profile_db": db,
        "current_user": current_user,
        "service_db": db,
        "business_profile_id": 34,
    }


def test_policy_route_does_not_generate_without_profile(
    monkeypatch,
):
    def reject_missing_profile(db, current_user):
        raise HTTPException(
            status_code=404,
            detail=(
                "No business profile is linked to the "
                "current user"
            ),
        )

    def fail_if_service_called(**kwargs):
        raise AssertionError(
            "Policy document service must not run "
            "without a profile."
        )

    monkeypatch.setattr(
        route_module,
        "get_current_user_profile",
        reject_missing_profile,
    )
    monkeypatch.setattr(
        route_module,
        "generate_fsms_policy_document_for_profile",
        fail_if_service_called,
    )

    with pytest.raises(HTTPException) as exc_info:
        (
            route_module
            .get_current_fsms_policy_document(
                db=object(),
                current_user=SimpleNamespace(id=12),
            )
        )

    assert exc_info.value.status_code == 404


def test_fsms_policy_route_is_registered_and_authenticated():
    matching_routes = [
        route
        for route in app.routes
        if (
            isinstance(route, APIRoute)
            and route.path
            == "/fsms-document/policy"
        )
    ]

    assert len(matching_routes) == 1

    route = matching_routes[0]

    assert route.methods == {"GET"}
    assert route.response_model is FSMSPolicyDocument

    dependency_calls = {
        dependency.call
        for dependency in route.dependant.dependencies
    }

    assert get_current_user in dependency_calls


@pytest.mark.parametrize(
    ("document_status", "expected_notice"),
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
def test_policy_route_serializes_complete_contract(
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

    result = (
        route_module.get_current_fsms_policy_document(
            db=object(),
            current_user=SimpleNamespace(id=12),
        )
    )
    payload = jsonable_encoder(result)

    assert payload["document_status"] == (
        document_status
    )
    assert payload["draft_notice"] == expected_notice
    assert [
        section["section_number"]
        for section in payload["sections"]
    ] == [
        "1",
        "2",
        "3",
        "4",
    ]
    assert (
        payload["sections"][0]
        ["content_blocks"][0]
        ["block_type"]
        == "text"
    )
    assert (
        payload["sections"][1]
        ["content_blocks"][0]
        ["block_type"]
        == "list"
    )
    assert (
        payload["sections"][2]
        ["content_blocks"][0]
        ["block_type"]
        == "table"
    )
    assert (
        payload["sections"][0]
        ["content_blocks"][0]
        ["source"]["source_references"]
        == [
            "controlled.policy",
        ]
    )

def test_policy_pdf_route_returns_downloadable_pdf(
    monkeypatch,
):
    db = object()
    current_user = SimpleNamespace(id=12)
    profile = SimpleNamespace(id=34)
    document = _policy_document()
    calls = {}

    monkeypatch.setattr(
        route_module,
        "get_current_user_profile",
        lambda received_db, received_user: profile,
    )

    def fake_generate_policy_document(
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
        fake_generate_policy_document,
    )
    monkeypatch.setattr(
        route_module,
        "render_fsms_policy_document_pdf",
        lambda received_document: b"%PDF-policy-test",
    )

    response = (
        route_module
        .download_current_fsms_policy_document_pdf(
            db=db,
            current_user=current_user,
        )
    )

    assert response.body == b"%PDF-policy-test"
    assert response.media_type == "application/pdf"
    assert (
        response.headers["content-disposition"]
        == (
            'attachment; '
            'filename="example-kitchen-fsms.pdf"'
        )
    )
    assert calls == {
        "db": db,
        "business_profile_id": 34,
    }


def test_policy_pdf_route_does_not_generate_without_profile(
    monkeypatch,
):
    def reject_missing_profile(db, current_user):
        raise HTTPException(
            status_code=404,
            detail=(
                "No business profile is linked to the "
                "current user"
            ),
        )

    def fail_if_service_called(**kwargs):
        raise AssertionError(
            "Policy document service must not run "
            "without a profile."
        )

    monkeypatch.setattr(
        route_module,
        "get_current_user_profile",
        reject_missing_profile,
    )
    monkeypatch.setattr(
        route_module,
        "generate_fsms_policy_document_for_profile",
        fail_if_service_called,
    )

    with pytest.raises(HTTPException) as exc_info:
        (
            route_module
            .download_current_fsms_policy_document_pdf(
                db=object(),
                current_user=SimpleNamespace(id=12),
            )
        )

    assert exc_info.value.status_code == 404


def test_policy_pdf_route_is_registered_and_authenticated():
    matching_routes = [
        route
        for route in app.routes
        if (
            isinstance(route, APIRoute)
            and route.path
            == "/fsms-document/policy/pdf"
        )
    ]

    assert len(matching_routes) == 1

    route = matching_routes[0]

    assert route.methods == {"GET"}

    dependency_calls = {
        dependency.call
        for dependency in route.dependant.dependencies
    }

    assert get_current_user in dependency_calls

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


def test_policy_progress_route_generates_progress_for_linked_profile(
    monkeypatch,
):
    db = object()
    current_user = SimpleNamespace(id=12)
    profile = SimpleNamespace(id=34)
    expected_progress = _policy_progress()
    calls = {}

    def fake_get_current_user_profile(
        received_db,
        received_user,
    ):
        calls["profile_db"] = received_db
        calls["current_user"] = received_user

        return profile

    def fake_generate_progress(
        *,
        db,
        business_profile_id,
    ):
        calls["service_db"] = db
        calls["business_profile_id"] = (
            business_profile_id
        )

        return expected_progress

    monkeypatch.setattr(
        route_module,
        "get_current_user_profile",
        fake_get_current_user_profile,
    )
    monkeypatch.setattr(
        route_module,
        (
            "generate_fsms_policy_document_"
            "progress_for_profile"
        ),
        fake_generate_progress,
    )

    result = (
        route_module
        .get_current_fsms_policy_document_progress(
            db=db,
            current_user=current_user,
        )
    )

    assert result is expected_progress
    assert calls == {
        "profile_db": db,
        "current_user": current_user,
        "service_db": db,
        "business_profile_id": 34,
    }


def test_policy_progress_route_does_not_generate_without_profile(
    monkeypatch,
):
    def reject_missing_profile(db, current_user):
        raise HTTPException(
            status_code=404,
            detail=(
                "No business profile is linked to the "
                "current user"
            ),
        )

    def fail_if_service_called(**kwargs):
        raise AssertionError(
            "Progress service must not run without "
            "a profile."
        )

    monkeypatch.setattr(
        route_module,
        "get_current_user_profile",
        reject_missing_profile,
    )
    monkeypatch.setattr(
        route_module,
        (
            "generate_fsms_policy_document_"
            "progress_for_profile"
        ),
        fail_if_service_called,
    )

    with pytest.raises(HTTPException) as exc_info:
        (
            route_module
            .get_current_fsms_policy_document_progress(
                db=object(),
                current_user=SimpleNamespace(id=12),
            )
        )

    assert exc_info.value.status_code == 404


def test_policy_progress_route_is_registered_and_authenticated():
    matching_routes = [
        route
        for route in app.routes
        if (
            isinstance(route, APIRoute)
            and route.path
            == "/fsms-document/policy/progress"
        )
    ]

    assert len(matching_routes) == 1

    route = matching_routes[0]

    assert route.methods == {"GET"}
    assert (
        route.response_model
        is FSMSPolicyDocumentProgress
    )

    dependency_calls = {
        dependency.call
        for dependency in route.dependant.dependencies
    }

    assert get_current_user in dependency_calls


def test_policy_progress_route_serializes_complete_contract(
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
        .get_current_fsms_policy_document_progress(
            db=object(),
            current_user=SimpleNamespace(id=12),
        )
    )
    payload = jsonable_encoder(result)

    assert payload == {
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
