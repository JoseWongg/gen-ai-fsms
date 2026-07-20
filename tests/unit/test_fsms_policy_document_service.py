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

def test_food_safety_policy_content_order_and_personalisation(
    monkeypatch,
):
    _patch_sources(monkeypatch)

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )

    policy_section = document.sections[0]

    assert policy_section.section_number == "1"
    assert [
        subsection.subsection_number
        for subsection in policy_section.subsections
    ] == [
        "1.1",
        "1.2",
        "1.3",
        "1.4",
    ]

    assert [
        [block.role for block in subsection.content_blocks]
        for subsection in policy_section.subsections
    ] == [
        ["introduction"],
        ["policy"],
        [
            "responsibilities",
            "responsibilities",
        ],
        [
            "monitoring",
            "corrective_action",
            "review",
        ],
    ]

    purpose = policy_section.subsections[0].content_blocks[0]

    assert purpose.text == (
        "This Food Safety Management System applies to "
        "Example Foods Ltd at Example Kitchen. The site "
        "operates as a bakery. It explains the food safety "
        "controls, responsibilities, monitoring and "
        "corrective actions used for the chilling, "
        "temperature-control, cooking and reheating "
        "activities that apply to the business. It must be "
        "followed by all staff whose work can affect food "
        "safety."
    )

    commitment = (
        policy_section.subsections[1].content_blocks[0]
    )

    assert commitment.text == (
        "Example Foods Ltd is committed to producing, "
        "handling and serving food safely at Example "
        "Kitchen. The business will provide suitable "
        "procedures, equipment, training and supervision; "
        "ensure that required checks and records are "
        "completed; and act promptly when a food safety "
        "control is not met. Food will not be served when "
        "its safety cannot be established."
    )

    rendered_content = str(
        policy_section.model_dump()
    )

    assert "{business_name}" not in rendered_content
    assert "{site_name}" not in rendered_content
    assert (
        "{business_type_with_article}"
        not in rendered_content
    )


def test_food_safety_policy_responsibilities_and_review(
    monkeypatch,
):
    _patch_sources(monkeypatch)

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )
    policy_section = document.sections[0]
    responsibilities = policy_section.subsections[2]
    monitoring_and_review = policy_section.subsections[3]

    assert responsibilities.content_blocks[0].text == (
        "Food safety is a shared responsibility. Everyone "
        "working for the business must understand and carry "
        "out the responsibilities relevant to their role."
    )

    assert responsibilities.content_blocks[1].items == [
        (
            "The business owner or responsible manager must "
            "maintain this FSMS, provide suitable resources, "
            "ensure staff are trained and supervised, and "
            "review the system when operations or risks "
            "change."
        ),
        (
            "The person in charge of each shift must ensure "
            "that required checks are completed, records are "
            "accurate, and problems are acted on or "
            "escalated."
        ),
        (
            "Food handlers must follow the approved "
            "procedures, complete assigned checks, report "
            "problems immediately and protect food from "
            "contamination or unsafe temperatures."
        ),
        (
            "No member of staff may serve or continue using "
            "food when its safety is uncertain. The matter "
            "must be referred to the person in charge."
        ),
    ]

    assert monitoring_and_review.content_blocks[0].text == (
        "Relevant food safety controls are monitored through "
        "routine operational checks and records. Checks must "
        "be completed at the time they are carried out and "
        "must identify the result, the person responsible and "
        "the date or time where required. Supervisors must "
        "review records and follow up omissions or repeated "
        "failures."
    )

    assert monitoring_and_review.content_blocks[1].text == (
        "When a required control is not met, staff must first "
        "protect customers by stopping the affected activity "
        "where necessary and isolating affected food. The "
        "problem, decision and action taken must be recorded "
        "and reported to the person in charge. Food must be "
        "discarded when it cannot be shown to be safe."
    )

    assert monitoring_and_review.content_blocks[2].text == (
        "This FSMS must be reviewed when the business changes "
        "its menu, processes, equipment or premises; after a "
        "food safety incident or repeated control failure; "
        "when relevant requirements or guidance change; and "
        "at suitable intervals to confirm that the controls "
        "remain effective."
    )


def test_policy_personalisation_sources_are_recorded(
    monkeypatch,
):
    _patch_sources(monkeypatch)

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )
    policy_section = document.sections[0]
    purpose = policy_section.subsections[0].content_blocks[0]
    commitment = (
        policy_section.subsections[1].content_blocks[0]
    )

    assert purpose.source.source_references == [
        "business_profile.business_name",
        "business_profile.site_name",
        "business_profile.business_type",
    ]

    assert commitment.source.source_references == [
        "business_profile.business_name",
        "business_profile.site_name",
    ]

    for subsection in policy_section.subsections[2:]:
        for block in subsection.content_blocks:
            assert block.source.source_references == []


@pytest.mark.parametrize(
    ("business_type", "expected_phrase"),
    [
        ("bakery", "The site operates as a bakery."),
        ("other", "The site operates as a food business."),
        (None, "The site operates as a food business."),
    ],
)
def test_policy_business_type_phrase_is_safe(
    monkeypatch,
    business_type,
    expected_phrase,
):
    _patch_sources(monkeypatch)

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(
                _profile(business_type=business_type)
            ),
            business_profile_id=1,
        )
    )

    purpose = (
        document.sections[0]
        .subsections[0]
        .content_blocks[0]
        .text
    )

    assert expected_phrase in purpose


def test_section_one_content_is_same_for_draft_and_approved(
    monkeypatch,
):
    applicable = [
        _safety_point(
            "4.1.1.1",
            "chilling",
            "4.1",
        )
    ]

    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_point_ids=[],
    )
    draft_document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )

    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_point_ids=[
            "4.1.1.1",
        ],
    )
    approved_document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )

    assert draft_document.document_status == "draft"
    assert approved_document.document_status == "approved"
    assert (
        draft_document.sections[0].model_dump()
        == approved_document.sections[0].model_dump()
    )
