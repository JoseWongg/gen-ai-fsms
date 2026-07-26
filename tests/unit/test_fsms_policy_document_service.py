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
    **overrides,
):
    values = {
        "safety_point_id": safety_point_id,
        "section_id": section_id,
        "safe_method_id": safe_method_id,
        "instruction": (
            f"Approved procedure for {safety_point_id}."
        ),
        "rationale": (
            f"Food safety reason for {safety_point_id}."
        ),
        "source_references": [
            f"Source for {safety_point_id}",
        ],
        "additional_source_references": [],
    }
    values.update(overrides)

    return values


def _patch_sources(
    monkeypatch,
    *,
    screening_complete=True,
    applicable_safety_points=None,
    approved_safety_point_ids=None,
    approved_safety_points=None,
    condition_values=None,
    active_chilling_equipment=None,
):
    monkeypatch.setattr(
        service,
        "get_screening_completion_status",
        lambda **kwargs: {
            "is_complete": screening_complete,
        },
    )
    resolved_condition_values = (
        condition_values
        if condition_values is not None
        else {}
    )
    monkeypatch.setattr(
        service,
        "get_condition_values_for_profile",
        lambda **kwargs: resolved_condition_values,
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
    resolved_approved_safety_points = (
        approved_safety_points
        if approved_safety_points is not None
        else [
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
    )
    resolved_active_chilling_equipment = (
        active_chilling_equipment
        if active_chilling_equipment is not None
        else []
    )
    monkeypatch.setattr(
        service,
        "_get_active_chilling_equipment",
        lambda **kwargs: (
            resolved_active_chilling_equipment
        ),
    )
    monkeypatch.setattr(
        service,
        "get_approved_methods_for_profile",
        lambda **kwargs: {
            "approved_safety_points": (
                resolved_approved_safety_points
            )
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
        "5",
        "6",
        "7",
        "8",
        "9",
        "10",
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
        "5",
        "6",
        "7",
        "8",
        "9",
        "10",
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
    ] == [
        "4.1",
        "4.6",
    ]


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
        "5",
        "6",
        "7",
        "8",
        "9",
        "10",
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
        "5",
        "6",
        "7",
        "8",
        "9",
        "10",
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
    ] == [
        "4.2",
        "4.6",
    ]


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
        "5",
        "6",
        "7",
        "8",
        "9",
        "10",
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

    pending_notice = responsibilities.content_blocks[2]

    assert pending_notice.block_type == "text"
    assert pending_notice.role == "responsibilities"
    assert pending_notice.heading == (
        "Pending feature — named responsibility "
        "assignments"
    )
    assert pending_notice.text == (
        "The current application does not yet capture "
        "the names of the people assigned to these "
        "roles. This table is included to show how "
        "named responsibilities will appear in the "
        "completed Food Safety Management System."
    )

    named_responsibilities = (
        responsibilities.content_blocks[3]
    )

    assert named_responsibilities.block_type == "table"
    assert (
        named_responsibilities.role
        == "responsibilities"
    )
    assert named_responsibilities.headers == [
        "Role",
        "Named person(s)",
        "Main responsibility",
    ]
    assert named_responsibilities.rows == [
        [
            (
                "Business owner or responsible "
                "manager"
            ),
            "Not yet recorded",
            (
                "Maintain the FSMS, provide suitable "
                "resources, ensure staff are trained "
                "and supervised, and review the system "
                "when operations or risks change."
            ),
        ],
        [
            "Person in charge of each shift",
            "Not yet recorded",
            (
                "Ensure required checks are completed, "
                "records are accurate, and food-safety "
                "problems are acted on or escalated."
            ),
        ],
        [
            "Food handlers",
            "Not yet recorded",
            (
                "Follow approved procedures, complete "
                "assigned checks, report problems "
                "immediately and protect food from "
                "contamination or unsafe temperatures."
            ),
        ],
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

def _scope_subsection(document, subsection_number):
    scope_section = document.sections[1]

    return next(
        subsection
        for subsection in scope_section.subsections
        if subsection.subsection_number
        == subsection_number
    )


def test_business_scope_operations_and_control_approach(
    monkeypatch,
):
    _patch_sources(monkeypatch)

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )

    operations = _scope_subsection(document, "2.1")

    assert [
        block.role
        for block in operations.content_blocks
    ] == [
        "business_context",
        "business_context",
    ]

    assert operations.content_blocks[0].text == (
        "Example Foods Ltd operates Example Kitchen as "
        "a bakery."
    )
    assert operations.content_blocks[1].text == (
        "The business describes its food operation as "
        "follows: A bakery making chilled desserts."
    )

    control_approach = _scope_subsection(
        document,
        "2.4",
    )

    assert control_approach.content_blocks[0].text == (
        "Food safety risks are managed through documented "
        "procedures, monitoring and corrective action. "
        "Where operational controls have been approved for "
        "Example Foods Ltd, they are set out in the relevant "
        "sections of this document. Staff must follow the "
        "controls relevant to their work, complete the "
        "required checks and report or correct failures "
        "promptly."
    )


def test_missing_description_omits_description_block(
    monkeypatch,
):
    _patch_sources(monkeypatch)

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(
                _profile(business_description=None)
            ),
            business_profile_id=1,
        )
    )

    operations = _scope_subsection(document, "2.1")

    assert len(operations.content_blocks) == 1
    assert operations.content_blocks[0].text == (
        "Example Foods Ltd operates Example Kitchen as "
        "a bakery."
    )


def test_activities_use_positive_supported_conditions(
    monkeypatch,
):
    _patch_sources(
        monkeypatch,
        condition_values={
            "cooks_food": "true",
            "handles_eggs": "true",
            "delivers_food": "true",
            "unknown_condition": "true",
            "chills_food": "false",
        },
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )

    activities = _scope_subsection(
        document,
        "2.2",
    )

    assert activities.content_blocks[0].text == (
        "The food activities within the current scope of "
        "this Food Safety Management System are:"
    )
    assert activities.content_blocks[1].items == [
        "Preparing or cooking food on site.",
        (
            "Using eggs or preparing foods containing "
            "eggs."
        ),
    ]
    assert (
        activities.content_blocks[1]
        .source.condition_ids
    ) == [
        "cooks_food",
        "handles_eggs",
    ]

    assert (
        activities.content_blocks[1]
        .source.condition_ids
    ) == [
        "cooks_food",
        "handles_eggs",
    ]


def test_activities_subsection_is_omitted_without_supported_activity(
    monkeypatch,
):
    _patch_sources(
        monkeypatch,
        condition_values={
            "delivers_food": "true",
            "unknown_condition": "true",
        },
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )

    scope_section = document.sections[1]

    assert "2.2" not in {
        subsection.subsection_number
        for subsection in scope_section.subsections
    }


def test_hazards_are_controlled_and_traceable(
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
        condition_values={
            "handles_raw_fish": "true",
            (
                "handles_bread_bakery_or_"
                "potatoes"
            ): "true",
        },
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )

    hazards = _scope_subsection(document, "2.3")
    hazard_list = hazards.content_blocks[1]

    assert hazard_list.items == [
        (
            "Harmful bacteria growing when chilled, "
            "cooling, reheated or hot-held food is not "
            "kept under suitable temperature control."
        ),
        (
            "Harmful bacteria surviving where food is "
            "not cooked or reheated thoroughly."
        ),
        (
            "Food becoming unsafe through unsuitable "
            "storage, poor date control, incorrect "
            "defrosting or loss of temperature control."
        ),
        (
            "Food-specific hazards, including parasites "
            "in fish, natural toxins in dried pulses and "
            "safety risks associated with shellfish."
        ),
        (
            "Increased acrylamide formation where bread, "
            "bakery or potato products are cooked too "
            "dark or at unsuitable temperatures."
        ),
    ]

    assert hazard_list.source.safety_point_ids == [
        "4.1.1.1",
        "5.1.1.1",
    ]
    assert hazard_list.source.condition_ids == [
        "handles_raw_fish",
        "handles_bread_bakery_or_potatoes",
    ]
    assert hazard_list.source.source_references == [
        "data/sfbb_chilling_cooking.json",
    ]


def test_hazards_subsection_is_omitted_without_applicable_category(
    monkeypatch,
):
    _patch_sources(
        monkeypatch,
        condition_values={
            "delivers_food": "true",
        },
        applicable_safety_points=[],
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )

    scope_section = document.sections[1]

    assert "2.3" not in {
        subsection.subsection_number
        for subsection in scope_section.subsections
    }

def _document_section(document, section_number):
    return next(
        section
        for section in document.sections
        if section.section_number == section_number
    )


def _document_subsection(
    document,
    subsection_number,
):
    section_number = subsection_number.split(".")[0]
    section = _document_section(
        document,
        section_number,
    )

    return next(
        subsection
        for subsection in section.subsections
        if subsection.subsection_number
        == subsection_number
    )


def test_chilling_section_content_is_personalised(
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
    section = _document_section(document, "3")

    assert [
        block.role
        for block in section.content_blocks
    ] == [
        "introduction",
        "policy",
    ]
    assert section.content_blocks[0].text == (
        "Example Foods Ltd controls chilled and frozen "
        "food at Example Kitchen to prevent harmful "
        "bacteria from growing and to ensure that food "
        "remains safe. Suitable equipment, approved "
        "working procedures, temperature checks and "
        "corrective actions are used for the activities "
        "carried out at the site."
    )


def test_chilled_storage_uses_approved_source_order(
    monkeypatch,
):
    applicable = [
        _safety_point(
            "4.1.1.1",
            "chilling",
            "4.1",
            instruction=(
                "Keep chilled food cold.\n"
                "Use it within its shelf life."
            ),
        ),
        _safety_point(
            "4.1.1.3",
            "chilling",
            "4.1",
            instruction=(
                "Check fridge temperatures daily."
            ),
        ),
    ]
    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_point_ids=[
            "4.1.1.3",
            "4.1.1.1",
        ],
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )
    subsection = _document_subsection(
        document,
        "3.1",
    )

    assert [
        block.role
        for block in subsection.content_blocks
    ] == [
        "food_safety_importance",
        "policy",
        "procedure",
        "monitoring",
        "corrective_action",
    ]
    assert subsection.content_blocks[2].items == [
        (
            "Keep chilled food cold. Use it within its "
            "shelf life."
        ),
        "Check fridge temperatures daily.",
    ]
    assert (
        subsection.content_blocks[2]
        .source.safety_point_ids
    ) == [
        "4.1.1.1",
        "4.1.1.3",
    ]


def test_chilled_storage_monitoring_requires_control(
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
    subsection = _document_subsection(
        document,
        "3.1",
    )

    assert [
        block.role
        for block in subsection.content_blocks
    ] == [
        "food_safety_importance",
        "policy",
        "procedure",
        "corrective_action",
    ]


def test_defrosting_uses_document_ready_response(
    monkeypatch,
):
    applicable = [
        _safety_point(
            "4.3.1.1",
            "chilling",
            "4.3",
        )
    ]
    approved = [
        {
            "safety_point_id": "4.3.1.1",
            "provenance_references": [
                "Approved source reference",
            ],
            "additional_responses": [
                {
                    "question_key": (
                        "foods_defrosted_under_"
                        "cold_running_water"
                    ),
                    "question_text": (
                        "Which foods are defrosted?"
                    ),
                    "response_text": (
                        "raw conversational answer"
                    ),
                    "document_response_text": (
                        "Chicken fillets are defrosted "
                        "under cold running water while "
                        "sealed in food-safe containers."
                    ),
                }
            ],
        }
    ]
    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_points=approved,
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )
    subsection = _document_subsection(
        document,
        "3.3",
    )
    arrangement = next(
        block
        for block in subsection.content_blocks
        if block.role == "business_context"
    )

    assert arrangement.heading == (
        "Business-specific arrangement"
    )
    assert arrangement.text == (
        "Chicken fillets are defrosted under cold "
        "running water while sealed in food-safe "
        "containers."
    )
    assert arrangement.source.safety_point_ids == [
        "4.3.1.1"
    ]
    assert (
        arrangement.source.additional_question_keys
    ) == [
        (
            "foods_defrosted_under_"
            "cold_running_water"
        )
    ]

    rendered = str(subsection.model_dump())

    assert "raw conversational answer" not in rendered
    assert "Which foods are defrosted?" not in rendered


def test_unapproved_chilling_point_is_not_documented(
    monkeypatch,
):
    applicable = [
        _safety_point(
            "4.2.1.1",
            "chilling",
            "4.2",
            instruction="First applicable procedure.",
        ),
        _safety_point(
            "4.2.1.2",
            "chilling",
            "4.2",
            instruction="Approved procedure.",
        ),
    ]
    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_point_ids=[
            "4.2.1.2",
        ],
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )
    subsection = _document_subsection(
        document,
        "3.2",
    )
    procedure = next(
        block
        for block in subsection.content_blocks
        if block.role == "procedure"
    )

    assert procedure.items == [
        "Approved procedure."
    ]
    assert procedure.source.safety_point_ids == [
        "4.2.1.2"
    ]


def test_equipment_response_is_not_rendered_as_text(
    monkeypatch,
):
    applicable = [
        _safety_point(
            "4.1.1.3",
            "chilling",
            "4.1",
        )
    ]
    approved = [
        {
            "safety_point_id": "4.1.1.3",
            "additional_responses": [
                {
                    "question_key": (
                        "chilling_equipment_"
                        "temperature_checks"
                    ),
                    "question_text": (
                        "List chilling equipment."
                    ),
                    "response_text": None,
                    "document_response_text": None,
                    "current_chilling_equipment": [
                        {
                            "equipment_name": (
                                "Main fridge"
                            )
                        }
                    ],
                }
            ],
        }
    ]
    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_points=approved,
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )
    subsection = _document_subsection(
        document,
        "3.1",
    )

    assert "business_context" not in {
        block.role
        for block in subsection.content_blocks
    }


@pytest.mark.parametrize(
    (
        "safety_point_id",
        "safe_method_id",
        "subsection_number",
    ),
    [
        (
            "4.2.1.4",
            "4.2",
            "3.2",
        ),
        (
            "4.3.1.1",
            "4.3",
            "3.3",
        ),
        (
            "4.4.1.7",
            "4.4",
            "3.4",
        ),
    ],
)
def test_chilling_subsections_have_controlled_block_order(
    monkeypatch,
    safety_point_id,
    safe_method_id,
    subsection_number,
):
    applicable = [
        _safety_point(
            safety_point_id,
            "chilling",
            safe_method_id,
        )
    ]
    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_point_ids=[
            safety_point_id,
        ],
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )
    subsection = _document_subsection(
        document,
        subsection_number,
    )

    assert [
        block.role
        for block in subsection.content_blocks
    ] == [
        "food_safety_importance",
        "policy",
        "procedure",
        "monitoring",
        "corrective_action",
    ]

def _equipment(
    *,
    equipment_id,
    asset_code,
    name,
    equipment_type,
    equipment_use="storage",
    check_method="digital_or_dial_display",
    source_safety_point_id="4.1.1.3",
):
    return SimpleNamespace(
        id=equipment_id,
        equipment_asset_code=asset_code,
        equipment_name=name,
        equipment_type=equipment_type,
        equipment_use=equipment_use,
        temperature_check_method=check_method,
        source_safety_point_id=(
            source_safety_point_id
        ),
        is_active=True,
    )


def test_temperature_monitoring_builds_equipment_table(
    monkeypatch,
):
    applicable = [
        _safety_point(
            "4.1.1.3",
            "chilling",
            "4.1",
        )
    ]
    equipment = [
        _equipment(
            equipment_id=1,
            asset_code="FR-001",
            name="Main Kitchen Fridge",
            equipment_type="fridge",
        ),
        _equipment(
            equipment_id=2,
            asset_code="FZ-001",
            name="Chest Freezer",
            equipment_type="freezer",
            check_method="probe_between_packs",
        ),
    ]
    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_point_ids=[
            "4.1.1.3",
        ],
        active_chilling_equipment=equipment,
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )
    subsection = _document_subsection(
        document,
        "3.5",
    )

    assert [
        block.role
        for block in subsection.content_blocks
    ] == [
        "monitoring",
        "equipment",
        "corrective_action",
    ]

    table = subsection.content_blocks[1]

    assert table.headers == [
        "Asset code",
        "Equipment",
        "Type",
        "Use",
        "Check method",
        "Required limit",
    ]
    assert table.rows == [
        [
            "FR-001",
            "Main Kitchen Fridge",
            "Fridge",
            "Storage",
            "Digital or dial display",
            "8°C or below",
        ],
        [
            "FZ-001",
            "Chest Freezer",
            "Freezer",
            "Storage",
            "Probe between packs",
            "−18°C or below",
        ],
    ]
    assert table.source.safety_point_ids == [
        "4.1.1.3"
    ]


def test_temperature_monitoring_requires_approved_control(
    monkeypatch,
):
    applicable = [
        _safety_point(
            "4.1.1.1",
            "chilling",
            "4.1",
        ),
        _safety_point(
            "4.1.1.3",
            "chilling",
            "4.1",
        ),
    ]
    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_point_ids=[
            "4.1.1.1",
        ],
        active_chilling_equipment=[
            _equipment(
                equipment_id=1,
                asset_code="FR-001",
                name="Main Fridge",
                equipment_type="fridge",
            )
        ],
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )

    section = _document_section(document, "3")

    assert "3.5" not in {
        subsection.subsection_number
        for subsection in section.subsections
    }


def test_temperature_monitoring_requires_active_equipment(
    monkeypatch,
):
    applicable = [
        _safety_point(
            "4.1.1.3",
            "chilling",
            "4.1",
        )
    ]
    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_point_ids=[
            "4.1.1.3",
        ],
        active_chilling_equipment=[],
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )

    section = _document_section(document, "3")

    assert "3.5" not in {
        subsection.subsection_number
        for subsection in section.subsections
    }
    assert "3.6" not in {
        subsection.subsection_number
        for subsection in section.subsections
    }


def test_checklist_is_included_for_other_chilling_control(
    monkeypatch,
):
    applicable = [
        _safety_point(
            "4.2.1.1",
            "chilling",
            "4.2",
        )
    ]
    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_point_ids=[
            "4.2.1.1",
        ],
        active_chilling_equipment=[
            _equipment(
                equipment_id=1,
                asset_code="FR-001",
                name="Main Fridge",
                equipment_type="fridge",
            )
        ],
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )

    section = _document_section(document, "3")

    assert "3.5" not in {
        subsection.subsection_number
        for subsection in section.subsections
    }
    assert "3.6" in {
        subsection.subsection_number
        for subsection in section.subsections
    }


def test_checklist_contains_blank_fields_and_instruction(
    monkeypatch,
):
    applicable = [
        _safety_point(
            "4.1.1.3",
            "chilling",
            "4.1",
        )
    ]
    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_point_ids=[
            "4.1.1.3",
        ],
        active_chilling_equipment=[
            _equipment(
                equipment_id=1,
                asset_code="FR-001",
                name="Main Fridge",
                equipment_type="fridge",
            )
        ],
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )
    subsection = _document_subsection(
        document,
        "3.6",
    )

    assert [
        block.role
        for block in subsection.content_blocks
    ] == [
        "monitoring",
        "checklist",
        "monitoring",
    ]

    assert subsection.content_blocks[0].text == (
        "Date: ____________________\n"
        "Shift / service: ____________________\n"
        "Person in charge: ____________________"
    )

    checklist = subsection.content_blocks[1]

    assert checklist.rows == [
        [
            "Main Fridge",
            "8°C or below",
            "",
            "",
            "",
        ]
    ]

    assert subsection.content_blocks[2].text == (
        "Record the actual temperature shown or measured. "
        "Where a reading exceeds the required limit, follow "
        "the corrective-action procedure immediately and "
        "record the incident and action taken."
    )


@pytest.mark.parametrize(
    ("equipment_type", "expected_limit"),
    [
        ("fridge", "8°C or below"),
        ("freezer", "−18°C or below"),
    ],
)
def test_equipment_limit_uses_existing_compliance_threshold(
    equipment_type,
    expected_limit,
):
    assert (
        service._equipment_required_limit(
            equipment_type
        )
        == expected_limit
    )

def test_cooking_section_content_is_personalised(
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
            "5.1.1.1",
        ],
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )
    section = _document_section(document, "4")

    assert [
        block.role
        for block in section.content_blocks
    ] == [
        "introduction",
        "policy",
    ]
    assert section.content_blocks[0].text == (
        "Example Foods Ltd controls cooking, reheating, "
        "hot holding and the handling of ready-to-eat food "
        "at Example Kitchen to ensure that food is safe to "
        "serve. Approved procedures, suitable equipment, "
        "appropriate checks and corrective actions are used "
        "for the activities carried out at the site."
    )


def test_cooking_safely_uses_approved_source_order(
    monkeypatch,
):
    applicable = [
        _safety_point(
            "5.1.1.2",
            "cooking",
            "5.1",
            instruction=(
                "Follow the manufacturer's instructions.\n"
                "Use the tested cooking method."
            ),
        ),
        _safety_point(
            "5.1.1.12",
            "cooking",
            "5.1",
            instruction=(
                "Use a disinfected temperature probe."
            ),
        ),
    ]
    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_point_ids=[
            "5.1.1.12",
            "5.1.1.2",
        ],
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )
    subsection = _document_subsection(
        document,
        "4.1",
    )

    assert [
        block.role
        for block in subsection.content_blocks
    ] == [
        "food_safety_importance",
        "policy",
        "procedure",
        "monitoring",
        "corrective_action",
    ]
    assert subsection.content_blocks[2].items == [
        (
            "Follow the manufacturer's instructions. "
            "Use the tested cooking method."
        ),
        "Use a disinfected temperature probe.",
    ]
    assert (
        subsection.content_blocks[2]
        .source.safety_point_ids
    ) == [
        "5.1.1.2",
        "5.1.1.12",
    ]


def test_cooking_monitoring_requires_probe_control(
    monkeypatch,
):
    applicable = [
        _safety_point(
            "5.1.1.2",
            "cooking",
            "5.1",
        )
    ]
    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_point_ids=[
            "5.1.1.2",
        ],
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )
    subsection = _document_subsection(
        document,
        "4.1",
    )

    assert [
        block.role
        for block in subsection.content_blocks
    ] == [
        "food_safety_importance",
        "policy",
        "procedure",
        "corrective_action",
    ]


def test_cooking_uses_document_ready_response(
    monkeypatch,
):
    applicable = [
        _safety_point(
            "5.1.1.5",
            "cooking",
            "5.1",
        )
    ]
    approved = [
        {
            "safety_point_id": "5.1.1.5",
            "additional_responses": [
                {
                    "question_key": (
                        "dishes_containing_"
                        "cooked_whole_birds"
                    ),
                    "question_text": (
                        "Which whole birds are cooked?"
                    ),
                    "response_text": (
                        "raw conversational answer"
                    ),
                    "document_response_text": (
                        "Whole chickens are roasted and "
                        "checked in the thickest area "
                        "between the leg and breast."
                    ),
                }
            ],
        }
    ]
    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_points=approved,
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )
    subsection = _document_subsection(
        document,
        "4.1",
    )
    arrangement = next(
        block
        for block in subsection.content_blocks
        if block.role == "business_context"
    )

    assert arrangement.heading == (
        "Business-specific arrangement"
    )
    assert arrangement.text == (
        "Whole chickens are roasted and checked in the "
        "thickest area between the leg and breast."
    )
    assert arrangement.source.safety_point_ids == [
        "5.1.1.5"
    ]
    assert (
        arrangement.source.additional_question_keys
    ) == [
        "dishes_containing_cooked_whole_birds"
    ]

    rendered = str(subsection.model_dump())

    assert "raw conversational answer" not in rendered
    assert "Which whole birds are cooked?" not in rendered


def test_additional_care_separates_control_groups(
    monkeypatch,
):
    applicable = [
        _safety_point(
            "5.2.1.1",
            "cooking",
            "5.2",
            instruction="Apply the egg controls.",
        ),
        _safety_point(
            "5.4.1.1",
            "cooking",
            "5.4",
            instruction="Apply the acrylamide controls.",
        ),
    ]
    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_point_ids=[
            "5.2.1.1",
            "5.4.1.1",
        ],
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )
    subsection = _document_subsection(
        document,
        "4.2",
    )
    procedure_blocks = [
        block
        for block in subsection.content_blocks
        if block.role == "procedure"
    ]

    assert [
        block.heading
        for block in procedure_blocks
    ] == [
        "Food-specific controls",
        "Acrylamide controls",
    ]
    assert [
        block.items
        for block in procedure_blocks
    ] == [
        ["Apply the egg controls."],
        ["Apply the acrylamide controls."],
    ]
    assert [
        block.source.safety_point_ids
        for block in procedure_blocks
    ] == [
        ["5.2.1.1"],
        ["5.4.1.1"],
    ]


def test_additional_care_omits_unapproved_group(
    monkeypatch,
):
    applicable = [
        _safety_point(
            "5.2.1.1",
            "cooking",
            "5.2",
            instruction="Unapproved egg control.",
        ),
        _safety_point(
            "5.4.1.1",
            "cooking",
            "5.4",
            instruction="Approved acrylamide control.",
        ),
    ]
    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_point_ids=[
            "5.4.1.1",
        ],
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )
    subsection = _document_subsection(
        document,
        "4.2",
    )
    procedure_blocks = [
        block
        for block in subsection.content_blocks
        if block.role == "procedure"
    ]

    assert len(procedure_blocks) == 1
    assert procedure_blocks[0].heading == (
        "Acrylamide controls"
    )
    assert procedure_blocks[0].items == [
        "Approved acrylamide control."
    ]


def test_hot_holding_response_and_monitoring(
    monkeypatch,
):
    applicable = [
        _safety_point(
            "5.5.1.1",
            "cooking",
            "5.5",
        ),
        _safety_point(
            "5.5.1.5",
            "cooking",
            "5.5",
        ),
    ]
    approved = [
        {
            "safety_point_id": "5.5.1.1",
            "additional_responses": [
                {
                    "question_key": (
                        "hot_holding_equipment"
                    ),
                    "question_text": (
                        "Which equipment is used?"
                    ),
                    "response_text": "bain marie",
                    "document_response_text": (
                        "A bain-marie and heated display "
                        "unit are used for hot holding "
                        "during service."
                    ),
                }
            ],
        },
        {
            "safety_point_id": "5.5.1.5",
        },
    ]
    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_points=approved,
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )
    subsection = _document_subsection(
        document,
        "4.4",
    )

    assert [
        block.role
        for block in subsection.content_blocks
    ] == [
        "food_safety_importance",
        "policy",
        "procedure",
        "business_context",
        "monitoring",
        "corrective_action",
    ]

    arrangement = subsection.content_blocks[3]

    assert arrangement.text == (
        "A bain-marie and heated display unit are used "
        "for hot holding during service."
    )
    assert arrangement.source.additional_question_keys == [
        "hot_holding_equipment"
    ]


@pytest.mark.parametrize(
    (
        "safety_point_id",
        "safe_method_id",
        "subsection_number",
    ),
    [
        (
            "5.3.1.1",
            "5.3",
            "4.3",
        ),
        (
            "5.6.1.1",
            "5.6",
            "4.5",
        ),
    ],
)
def test_cooking_subsections_have_controlled_block_order(
    monkeypatch,
    safety_point_id,
    safe_method_id,
    subsection_number,
):
    applicable = [
        _safety_point(
            safety_point_id,
            "cooking",
            safe_method_id,
        )
    ]
    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_point_ids=[
            safety_point_id,
        ],
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )
    subsection = _document_subsection(
        document,
        subsection_number,
    )

    assert [
        block.role
        for block in subsection.content_blocks
    ] == [
        "food_safety_importance",
        "policy",
        "procedure",
        "monitoring",
        "corrective_action",
    ]


def test_unapproved_cooking_point_is_not_documented(
    monkeypatch,
):
    applicable = [
        _safety_point(
            "5.3.1.1",
            "cooking",
            "5.3",
            instruction="Unapproved probe control.",
        ),
        _safety_point(
            "5.3.1.2",
            "cooking",
            "5.3",
            instruction="Approved equipment control.",
        ),
    ]
    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_point_ids=[
            "5.3.1.2",
        ],
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )
    subsection = _document_subsection(
        document,
        "4.3",
    )
    procedure = next(
        block
        for block in subsection.content_blocks
        if block.role == "procedure"
    )

    assert procedure.items == [
        "Approved equipment control."
    ]
    assert procedure.source.safety_point_ids == [
        "5.3.1.2"
    ]
    assert "monitoring" not in {
        block.role
        for block in subsection.content_blocks
    }

def test_cooking_checks_are_included_for_approved_content(
    monkeypatch,
):
    applicable = [
        _safety_point(
            "5.6.1.1",
            "cooking",
            "5.6",
        )
    ]
    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_point_ids=[
            "5.6.1.1",
        ],
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )
    subsection = _document_subsection(
        document,
        "4.6",
    )

    assert [
        block.role
        for block in subsection.content_blocks
    ] == [
        "monitoring",
        "procedure",
        "corrective_action",
    ]

    assert subsection.content_blocks[0].text == (
        "Cooking, reheating and hot-holding checks must "
        "demonstrate that the approved control has worked. "
        "The check must be appropriate to the food and may "
        "include a time-and-temperature check, examination "
        "of the centre or thickest part, testing several "
        "locations, confirmation of texture or colour, or "
        "verification of equipment performance."
    )


@pytest.mark.parametrize(
    ("safety_point_id", "safe_method_id"),
    [
        (
            "5.1.1.12",
            "5.1",
        ),
        (
            "5.3.1.1",
            "5.3",
        ),
    ],
)
def test_cooking_checks_table_uses_approved_probe_control(
    monkeypatch,
    safety_point_id,
    safe_method_id,
):
    applicable = [
        _safety_point(
            safety_point_id,
            "cooking",
            safe_method_id,
        )
    ]
    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_point_ids=[
            safety_point_id,
        ],
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )
    subsection = _document_subsection(
        document,
        "4.6",
    )

    assert [
        block.role
        for block in subsection.content_blocks
    ] == [
        "monitoring",
        "monitoring",
        "procedure",
        "corrective_action",
    ]

    table = subsection.content_blocks[1]

    assert table.heading == (
        "Safe time and temperature combinations"
    )
    assert table.headers == [
        "Temperature",
        "Minimum holding time",
    ]
    assert table.rows == [
        [
            "80°C",
            "6 seconds",
        ],
        [
            "75°C",
            "30 seconds",
        ],
        [
            "70°C",
            "2 minutes",
        ],
        [
            "65°C",
            "10 minutes",
        ],
        [
            "60°C",
            "45 minutes",
        ],
    ]
    assert table.source.safety_point_ids == [
        safety_point_id
    ]
    assert (
        "data/sfbb_chilling_cooking.json"
        in table.source.source_references
    )


@pytest.mark.parametrize(
    (
        "safety_point_id",
        "safe_method_id",
        "subsection_number",
        "instruction",
        "expected_item",
    ),
    [
        (
            "5.1.1.12",
            "5.1",
            "4.1",
            (
                "A disinfected temperature probe is used "
                "to check that dishes are properly cooked "
                "or reheated.\n\n"
                "Safe time/temperature combinations for "
                "cooking include:\n"
                "- 80°C for at least 6 seconds\n"
                "- 75°C for at least 30 seconds"
            ),
            (
                "A disinfected temperature probe is used "
                "to check that dishes are properly cooked "
                "or reheated."
            ),
        ),
        (
            "5.3.1.1",
            "5.3",
            "4.3",
            (
                "Food is reheated properly.\n\n"
                "A disinfected temperature probe is used "
                "to check that dishes are properly "
                "reheated.\n\n"
                "Safe time/temperature combinations "
                "include:\n"
                "- 80°C for at least 6 seconds\n"
                "- 75°C for at least 30 seconds"
            ),
            (
                "Food is reheated properly. A disinfected "
                "temperature probe is used to check that "
                "dishes are properly reheated."
            ),
        ),
    ],
)
def test_safe_combinations_are_not_repeated_in_procedures(
    monkeypatch,
    safety_point_id,
    safe_method_id,
    subsection_number,
    instruction,
    expected_item,
):
    applicable = [
        _safety_point(
            safety_point_id,
            "cooking",
            safe_method_id,
            instruction=instruction,
        )
    ]
    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_point_ids=[
            safety_point_id,
        ],
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )
    operational_subsection = _document_subsection(
        document,
        subsection_number,
    )
    procedure = next(
        block
        for block in operational_subsection.content_blocks
        if block.role == "procedure"
    )

    assert procedure.items == [
        expected_item
    ]
    assert (
        "Safe time/temperature combinations"
        not in procedure.items[0]
    )


def test_cooking_checks_trace_all_approved_controls(
    monkeypatch,
):
    applicable = [
        _safety_point(
            "5.1.1.2",
            "cooking",
            "5.1",
        ),
        _safety_point(
            "5.5.1.5",
            "cooking",
            "5.5",
        ),
    ]
    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_point_ids=[
            "5.1.1.2",
            "5.5.1.5",
        ],
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )
    subsection = _document_subsection(
        document,
        "4.6",
    )

    assert (
        subsection.content_blocks[0]
        .source.safety_point_ids
    ) == [
        "5.1.1.2",
        "5.5.1.5",
    ]

    assert "table" not in {
        block.block_type
        for block in subsection.content_blocks
    }

def test_beyond_scope_sections_are_always_included(
    monkeypatch,
):
    _patch_sources(
        monkeypatch,
        applicable_safety_points=[],
        approved_safety_point_ids=[],
    )

    document = (
        service.generate_fsms_policy_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
        )
    )

    outline_sections = [
        section
        for section in document.sections
        if section.section_number
        in {
            "5",
            "6",
            "7",
            "8",
            "9",
            "10",
        }
    ]

    assert [
        (
            section.section_number,
            section.title,
        )
        for section in outline_sections
    ] == [
        (
            "5",
            "Cross-Contamination Control",
        ),
        (
            "6",
            "Cleaning and Disinfection",
        ),
        (
            "7",
            "Allergen Management",
        ),
        (
            "8",
            "Pest Control",
        ),
        (
            "9",
            "Deliveries and Traceability",
        ),
        (
            "10",
            "Training, Responsibilities and Review",
        ),
    ]

    for section in outline_sections:
        assert section.subsections == []
        assert len(section.content_blocks) == 1

        block = section.content_blocks[0]

        assert block.block_type == "text"
        assert block.role == "introduction"
        assert (
            block.heading
            == "Beyond current project scope"
        )
        assert block.text == (
            "This section is included to show the "
            "planned structure of the complete Food "
            "Safety Management System. Operational "
            "content for this section is not currently "
            "generated by the application."
        )
        assert block.source is not None
        assert block.source.safety_point_ids == []
        assert block.source.condition_ids == []
        assert (
            block.source.additional_question_keys
            == []
        )
        assert block.source.source_references == []

def test_document_reflects_active_chilling_equipment_changes(
    monkeypatch,
):
    equipment = [
        SimpleNamespace(
            id=1,
            business_profile_id=1,
            source_safety_point_id="4.1.1.3",
            equipment_asset_code="CHILL-001",
            equipment_name="Prep fridge",
            equipment_use="storage",
            equipment_type="fridge",
            temperature_check_method=(
                "digital_or_dial_display"
            ),
            is_active=True,
        ),
    ]
    applicable = [
        _safety_point(
            "4.1.1.3",
            "chilling",
            "4.1",
        ),
    ]

    _patch_sources(
        monkeypatch,
        applicable_safety_points=applicable,
        approved_safety_point_ids=[
            "4.1.1.3",
        ],
        active_chilling_equipment=equipment,
    )

    def build_document():
        return (
            service
            .generate_fsms_policy_document_for_profile(
                db=FakeSession(_profile()),
                business_profile_id=1,
            )
        )

    def table_rows(
        document,
        subsection_number,
        role,
    ):
        chilling_section = next(
            section
            for section in document.sections
            if section.section_number == "3"
        )
        subsection = next(
            subsection
            for subsection
            in chilling_section.subsections
            if (
                subsection.subsection_number
                == subsection_number
            )
        )
        table = next(
            block
            for block in subsection.content_blocks
            if block.role == role
        )

        return table.rows

    initial_document = build_document()
    initial_equipment_rows = table_rows(
        initial_document,
        "3.5",
        "equipment",
    )
    initial_checklist_rows = table_rows(
        initial_document,
        "3.6",
        "checklist",
    )

    assert [
        row[1]
        for row in initial_equipment_rows
    ] == [
        "Prep fridge",
    ]
    assert "Prep fridge" in str(
        initial_checklist_rows
    )

    equipment[0].equipment_name = (
        "Service fridge"
    )
    equipment[0].equipment_use = "display"
    equipment[0].temperature_check_method = (
        "probe_between_packs"
    )

    updated_document = build_document()
    updated_equipment_rows = table_rows(
        updated_document,
        "3.5",
        "equipment",
    )
    updated_checklist_rows = table_rows(
        updated_document,
        "3.6",
        "checklist",
    )

    assert updated_equipment_rows[0][1:5] == [
        "Service fridge",
        "Fridge",
        "Display",
        "Probe between packs",
    ]
    assert "Prep fridge" not in str(
        updated_equipment_rows
    )
    assert "Prep fridge" not in str(
        updated_checklist_rows
    )
    assert "Service fridge" in str(
        updated_checklist_rows
    )

    freezer = SimpleNamespace(
        id=2,
        business_profile_id=1,
        source_safety_point_id="4.1.1.3",
        equipment_asset_code="CHILL-002",
        equipment_name="Walk-in freezer",
        equipment_use="storage",
        equipment_type="freezer",
        temperature_check_method=(
            "digital_or_dial_display"
        ),
        is_active=True,
    )
    equipment.append(freezer)

    added_document = build_document()
    added_equipment_rows = table_rows(
        added_document,
        "3.5",
        "equipment",
    )
    added_checklist_rows = table_rows(
        added_document,
        "3.6",
        "checklist",
    )

    assert {
        row[1]
        for row in added_equipment_rows
    } == {
        "Service fridge",
        "Walk-in freezer",
    }
    assert "Service fridge" in str(
        added_checklist_rows
    )
    assert "Walk-in freezer" in str(
        added_checklist_rows
    )

    equipment[:] = [
        freezer,
    ]

    removed_document = build_document()
    removed_equipment_rows = table_rows(
        removed_document,
        "3.5",
        "equipment",
    )
    removed_checklist_rows = table_rows(
        removed_document,
        "3.6",
        "checklist",
    )

    assert [
        row[1]
        for row in removed_equipment_rows
    ] == [
        "Walk-in freezer",
    ]
    assert "Service fridge" not in str(
        removed_equipment_rows
    )
    assert "Service fridge" not in str(
        removed_checklist_rows
    )
    assert "Walk-in freezer" in str(
        removed_checklist_rows
    )

    equipment.clear()

    empty_document = build_document()
    chilling_section = next(
        section
        for section in empty_document.sections
        if section.section_number == "3"
    )
    subsection_numbers = {
        subsection.subsection_number
        for subsection
        in chilling_section.subsections
    }

    assert "3.5" not in subsection_numbers
    assert "3.6" not in subsection_numbers
