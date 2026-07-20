from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import gen_ai_fsms.services.fsms_document_service as service
from gen_ai_fsms.db.models.business_profile import BusinessProfile


STRUCTURE_CONFIG = {
    "document_title": "Food Safety Management System",
    "supported_section_count": 4,
    "planned_section_count": 5,
    "sections": [
        {
            "section_id": "food_safety_policy",
            "title": "Food Safety Policy",
            "display_order": 1,
            "implementation_status": "supported",
            "completion_rule": "business_profile_complete",
            "source_section_ids": [],
            "always_applicable": True,
            "counts_towards_business_completion": True,
            "introduction": "Policy introduction.",
        "summary_subsection": {
            "subsection_id": "1.1",
            "title": "Food Safety Commitment",
            "introduction": "Policy subsection introduction.",
            "arrangement_title": "Policy statement",
            "policy_statements": [
                (
                    "{business_name} commits to applying the "
                    "approved food safety controls at {site_name}."
                )
            ],
        },
        },
        {
            "section_id": "business_and_hazard_overview",
            "title": "Business and Hazard Overview",
            "display_order": 2,
            "implementation_status": "supported",
            "completion_rule": "food_safety_profile_complete",
            "source_section_ids": [],
            "always_applicable": True,
            "counts_towards_business_completion": True,
            "introduction": "Business overview introduction.",
        "summary_subsection": {
            "subsection_id": "2.1",
            "title": (
                "Business Activities and Food Safety Profile"
            ),
            "introduction": (
                "Business profile subsection introduction."
            ),
            "business_arrangement_title": (
                "Business overview"
            ),
            "screening_arrangement_title": (
                "Food Safety Profile"
            ),
            "screening_table_headers": [
                "Food Safety Profile question",
                "Recorded answer",
            ],
        },
        },
        {
            "section_id": "temperature_control",
            "title": "Temperature Control",
            "display_order": 3,
            "implementation_status": "supported",
            "completion_rule": (
                "all_applicable_chilling_requirements_complete"
            ),
            "source_section_ids": ["chilling"],
            "always_applicable": False,
            "counts_towards_business_completion": True,
            "introduction": "Temperature introduction.",
        },
        {
            "section_id": "cooking_and_reheating",
            "title": "Cooking and Reheating",
            "display_order": 4,
            "implementation_status": "supported",
            "completion_rule": (
                "all_applicable_cooking_requirements_complete"
            ),
            "source_section_ids": ["cooking"],
            "always_applicable": False,
            "counts_towards_business_completion": True,
            "introduction": "Cooking introduction.",
        },
        {
            "section_id": "cross_contamination_control",
            "title": "Cross-Contamination Control",
            "display_order": 5,
            "implementation_status": (
                "beyond_prototype_scope"
            ),
            "source_section_ids": [],
            "always_applicable": True,
            "counts_towards_business_completion": False,
            "introduction": "Planned section introduction.",
        },
    ],
    "safe_method_introductions": {
        "4.1": {
            "title": "Chilled Storage",
            "source_section_id": "chilling",
            "introduction": "Chilled storage introduction.",
        },
        "5.1": {
            "title": "Cooking Safely",
            "source_section_id": "cooking",
            "introduction": "Cooking safely introduction.",
        },
    },
    "appendices": [
        {
            "appendix_id": (
                "monitoring_arrangements_and_records"
            ),
            "title": "Monitoring Arrangements and Records",
            "display_order": 1,
        },
        {
            "appendix_id": "source_references",
            "title": "Source References",
            "display_order": 2,
        },
    ],
}


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
        "business_type": "restaurant",
        "business_description": (
            "A small restaurant serving cooked meals."
        ),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _patch_document_sources(
    monkeypatch,
    *,
    screening_complete=True,
    condition_values=None,
    applicable_safety_points=None,
    approved_safety_points=None,
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
        "get_condition_values_for_profile",
        lambda **kwargs: (
            condition_values
            if condition_values is not None
            else {}
        ),
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
            "approved_safety_points": (
                approved_safety_points
                if approved_safety_points is not None
                else []
            )
        },
    )


def test_service_builds_live_document_from_current_data(
    monkeypatch,
):
    applicable_safety_points = [
        {
            "safety_point_id": "4.1.1.1",
            "section_id": "chilling",
            "safe_method_id": "4.1",
            "instruction": "Chilled food is kept cold.",
            "source_references": [
                "SFBB Pack > Chilling > Chilled Storage"
            ],
            "additional_source_references": [],
        }
    ]
    approved_safety_points = [
        {
            "safety_point_id": "4.1.1.1",
            "provenance_references": [],
            "additional_responses": [],
        }
    ]
    _patch_document_sources(
        monkeypatch,
        applicable_safety_points=applicable_safety_points,
        approved_safety_points=approved_safety_points,
    )
    generated_at = datetime(
        2026,
        7,
        19,
        12,
        0,
        tzinfo=timezone.utc,
    )

    document = service.generate_fsms_document_for_profile(
        db=FakeSession(_profile()),
        business_profile_id=1,
        generated_at=generated_at,
        structure_config=STRUCTURE_CONFIG,
    )

    assert document.business_name == "Example Foods Ltd"
    assert document.site_name == "Example Kitchen"
    assert document.business_type == "Restaurant"
    assert document.generated_at == generated_at

    assert [
        section.section_id
        for section in document.sections
    ] == [
        "food_safety_policy",
        "business_and_hazard_overview",
        "temperature_control",
        "cross_contamination_control",
    ]

    assert document.sections[0].status == "completed"
    assert document.sections[1].status == "completed"
    assert document.sections[2].status == "completed"
    assert document.sections[3].status == (
        "beyond_prototype_scope"
    )

    assert document.progress.main_value == "3/3"
    assert document.progress.completion_percentage == 100
    assert (
        document.sections[2]
        .subsections[0]
        .approved_rules[0]
        .instruction
        == "Chilled food is kept cold."
    )


def test_incomplete_screening_keeps_overview_outstanding(
    monkeypatch,
):
    _patch_document_sources(
        monkeypatch,
        screening_complete=False,
    )

    document = service.generate_fsms_document_for_profile(
        db=FakeSession(_profile()),
        business_profile_id=1,
        structure_config=STRUCTURE_CONFIG,
    )

    assert document.sections[0].status == "completed"
    assert document.sections[1].status == "not_completed"
    assert document.sections[1].completion_message == (
        "Not completed: Food Safety Profile screening is "
        "incomplete."
    )
    assert document.progress.main_value == "1/2"
    assert document.progress.document_status == "in_progress"


def test_missing_business_context_keeps_summary_sections_outstanding(
    monkeypatch,
):
    _patch_document_sources(monkeypatch)

    document = service.generate_fsms_document_for_profile(
        db=FakeSession(
            _profile(
                business_type=None,
                business_description=None,
            )
        ),
        business_profile_id=1,
        structure_config=STRUCTURE_CONFIG,
    )

    assert document.sections[0].status == "not_completed"
    assert document.sections[1].status == "not_completed"
    assert document.progress.main_value == "0/2"
    assert document.progress.document_status == "not_started"


def test_missing_business_profile_is_rejected():
    with pytest.raises(
        ValueError,
        match="Business profile not found",
    ):
        service.generate_fsms_document_for_profile(
            db=FakeSession(None),
            business_profile_id=999,
            structure_config=STRUCTURE_CONFIG,
        )


def test_unknown_summary_completion_rule_is_rejected(
    monkeypatch,
):
    _patch_document_sources(monkeypatch)
    invalid_structure = deepcopy(STRUCTURE_CONFIG)
    invalid_structure["sections"][0]["completion_rule"] = (
        "unknown_rule"
    )

    with pytest.raises(
        ValueError,
        match=(
            "Unsupported FSMS document summary completion rule"
        ),
    ):
        service.generate_fsms_document_for_profile(
            db=FakeSession(_profile()),
            business_profile_id=1,
            structure_config=invalid_structure,
        )



def test_summary_sections_include_substantive_content(
    monkeypatch,
):
    _patch_document_sources(
        monkeypatch,
        condition_values={
            "chills_food": "true",
            "cooks_food": "false",
            "displays_chilled_food": "false",
        },
    )

    document = service.generate_fsms_document_for_profile(
        db=FakeSession(_profile()),
        business_profile_id=1,
        structure_config=STRUCTURE_CONFIG,
    )

    policy_section = document.sections[0]
    overview_section = document.sections[1]

    assert policy_section.subsections[0].safe_method_id == "1.1"
    assert (
        policy_section
        .subsections[0]
        .business_specific_arrangements[0]
        .statements
        == [
            (
                "Example Foods Ltd commits to applying the "
                "approved food safety controls at "
                "Example Kitchen."
            )
        ]
    )

    overview_arrangements = (
        overview_section
        .subsections[0]
        .business_specific_arrangements
    )

    assert overview_arrangements[0].statements == [
        "Example Kitchen is operated by Example Foods Ltd.",
        "The recorded business type is Restaurant.",
        (
            "Business description: A small restaurant "
            "serving cooked meals."
        ),
    ]

    assert [
        (
            "Do you keep any food chilled in fridges or "
            "chilled display units?"
        ),
        "Yes",
    ] in overview_arrangements[1].table_rows

    display_rows = [
        row
        for row in overview_arrangements[1].table_rows
        if row[0].startswith(
            "Do you display chilled food for customers"
        )
    ]

    assert len(display_rows) == 1
    assert display_rows[0][1] == "No"


def test_screening_profile_rows_follow_question_dependencies():
    rows = service._build_screening_profile_rows(
        {
            "chills_food": "true",
            "cooks_food": "false",
            "displays_chilled_food": "true",
        }
    )

    questions = {
        row[0]
        for row in rows
    }

    assert any(
        question.startswith(
            "Do you display chilled food for customers"
        )
        for question in questions
    )
    assert "Do you handle raw meat or poultry?" not in questions
