from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from gen_ai_fsms.api.deps import get_current_user
from gen_ai_fsms.api.routes import fsms_document as route_module
from gen_ai_fsms.main import app
from gen_ai_fsms.schemas.fsms_document import FSMSDocument


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
