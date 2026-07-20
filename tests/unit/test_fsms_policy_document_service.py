from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import gen_ai_fsms.services.fsms_policy_document_service as service
from gen_ai_fsms.db.models.business_profile import (
    BusinessProfile,
)


class FakeQuery:
    def __init__(self, profile):
        self.profile = profile

    def filter(self, *args):
        return self

    def first(self):
        return self.profile


class FakeSession:
    def __init__(self, profile):
        self.profile = profile

    def query(self, model):
        assert model is BusinessProfile
        return FakeQuery(self.profile)


def _profile(**overrides):
    values = {
        "id": 1,
        "business_name": "Example Foods Ltd",
        "site_name": "Example Kitchen",
        "business_type": "bakery",
        "business_description": (
            "A bakery making chilled desserts."
        ),
    }
    values.update(overrides)

    return SimpleNamespace(**values)


def _safety_point(
    safety_point_id,
    section_id,
    safe_method_id,
):
    return {
        "safety_point_id": safety_point_id,
        "section_id": section_id,
        "safe_method_id": safe_method_id,
    }


def _patch_sources(
    monkeypatch,
    *,
    screening_complete=True,
    applicable_safety_points=None,
    approved_safety_point_ids=None,
):
    monkeypatch.setattr(
        service,
        "get_screening_completion_status",
        lambda **kwargs: {
            "is_complete": screening_complete,
        },
    )
    monkeypatch.setattr(
        service,
        "get_relevant_safety_points_for_profile",
        lambda **kwargs: (
            applicable_safety_points
            if applicable_safety_points is not None
            else []
        ),
    )
    monkeypatch.setattr(
        service,
        "get_approved_methods_for_profile",
        lambda **kwargs: {
            "approved_safety_points": [
                {
                    "safety_point_id": safety_point_id,
                }
                for safety_point_id
                in (
                    approved_safety_point_ids
                    if approved_safety_point_ids
                    is not None
                    else []
                )
            ]
        },
    )


def test_partial_approval_builds_draft_shell(
    monkeypatch,
):
    applicable = [
        _safety_point(
            "4.1.1.1",
            "chilling",
            "4.1",
        ),
        _safety_point(
            "5.1.1.1",
            "cooking",
            "5.1",
        ),
    ]
    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_point_ids=[
            "4.1.1.1",
        ],
    )
    generated_at = datetime(
        2026,
        7,
        20,
        12,
        0,
        tzinfo=timezone.utc,
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
            generated_at=generated_at,
        )
    )

    assert document.document_status == "draft"
    assert document.draft_notice == (
        "This document is incomplete and must not be "
        "treated as the final approved Food Safety "
        "Management System."
    )
    assert document.document_title == (
        "Food Safety Management System"
    )
    assert document.business_name == (
        "Example Foods Ltd"
    )
    assert document.site_name == "Example Kitchen"
    assert document.business_type == "Bakery"
    assert document.generated_at == generated_at

    assert [
        section.section_number
        for section in document.sections
    ] == [
        "1",
        "2",
        "3",
    ]

    assert [
        subsection.subsection_number
        for subsection
        in document.sections[2].subsections
    ] == ["3.1"]

    payload = document.model_dump()

    assert "progress" not in payload
    assert "appendices" not in payload
    assert "business_description" not in payload


def test_complete_profile_builds_approved_shell(
    monkeypatch,
):
    applicable = [
        _safety_point(
            "4.1.1.1",
            "chilling",
            "4.1",
        ),
        _safety_point(
            "5.1.1.1",
            "cooking",
            "5.1",
        ),
    ]
    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_point_ids=[
            "4.1.1.1",
            "5.1.1.1",
        ],
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )

    assert document.document_status == "approved"
    assert document.draft_notice is None

    assert [
        section.section_number
        for section in document.sections
    ] == [
        "1",
        "2",
        "3",
        "4",
    ]

    assert [
        subsection.subsection_number
        for subsection
        in document.sections[2].subsections
    ] == ["3.1"]

    assert [
        subsection.subsection_number
        for subsection
        in document.sections[3].subsections
    ] == ["4.1"]


@pytest.mark.parametrize(
    (
        "profile_overrides",
        "screening_complete",
    ),
    [
        (
            {
                "business_description": None,
            },
            True,
        ),
        (
            {},
            False,
        ),
    ],
)
def test_incomplete_foundation_keeps_document_draft(
    monkeypatch,
    profile_overrides,
    screening_complete,
):
    _patch_sources(
        monkeypatch,
        screening_complete=screening_complete,
        applicable_safety_points=[],
        approved_safety_point_ids=[],
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(
                _profile(**profile_overrides)
            ),
            business_profile_id=1,
        )
    )

    assert document.document_status == "draft"
    assert document.draft_notice is not None
    assert [
        section.section_number
        for section in document.sections
    ] == [
        "1",
        "2",
    ]


def test_stale_approval_is_ignored(
    monkeypatch,
):
    applicable = [
        _safety_point(
            "5.1.1.1",
            "cooking",
            "5.1",
        )
    ]
    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_point_ids=[
            "4.1.1.1",
        ],
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )

    assert document.document_status == "draft"
    assert [
        section.section_number
        for section in document.sections
    ] == [
        "1",
        "2",
    ]


def test_operational_subsections_follow_approved_methods(
    monkeypatch,
):
    applicable = [
        _safety_point(
            "4.1.1.1",
            "chilling",
            "4.1",
        ),
        _safety_point(
            "4.2.1.1",
            "chilling",
            "4.2",
        ),
        _safety_point(
            "5.4.1.1",
            "cooking",
            "5.4",
        ),
    ]
    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_point_ids=[
            "4.2.1.1",
            "5.4.1.1",
        ],
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )

    assert document.document_status == "draft"

    assert [
        subsection.subsection_number
        for subsection
        in document.sections[2].subsections
    ] == ["3.2"]

    assert [
        subsection.subsection_number
        for subsection
        in document.sections[3].subsections
    ] == ["4.2"]


def test_missing_business_profile_is_rejected():
    with pytest.raises(
        ValueError,
        match="Business profile not found",
    ):
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(None),
            business_profile_id=999,
        )


def test_structure_loader_reads_new_policy_file():
    structure = (
        service.load_fsms_policy_document_structure()
    )

    assert structure["schema_version"] == "2.0"
    assert [
        section["section_number"]
        for section in structure["sections"]
    ] == [
        "1",
        "2",
        "3",
        "4",
    ]
