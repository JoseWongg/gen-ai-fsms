import pytest
from pydantic import ValidationError

from gen_ai_fsms.schemas.fsms_policy_document import (
    FSMSPolicyDocumentProgress,
)
from gen_ai_fsms.services import (
    fsms_policy_document_progress as progress_service,
)


def _structure():
    beyond_scope_sections = [
        "cross_contamination_control",
        "cleaning_and_disinfection",
        "allergen_management",
        "pest_control",
        "deliveries_and_traceability",
        "training_responsibilities_and_review",
    ]

    sections = [
        {
            "section_id": "food_safety_policy",
            "inclusion": "always",
        },
        {
            "section_id": (
                "business_scope_and_food_safety_overview"
            ),
            "inclusion": "business_profile_exists",
        },
        {
            "section_id": (
                "chilling_and_temperature_control"
            ),
            "inclusion": "approved_applicable_content",
            "source_section_ids": ["4"],
        },
        {
            "section_id": "cooking_and_reheating",
            "inclusion": "approved_applicable_content",
            "source_section_ids": ["5"],
        },
    ]

    sections.extend(
        {
            "section_id": section_id,
            "inclusion": (
                "beyond_current_project_scope"
            ),
        }
        for section_id in beyond_scope_sections
    )

    return {
        "sections": sections,
    }


def _safety_point(
    safety_point_id,
    section_id,
):
    return {
        "safety_point_id": safety_point_id,
        "section_id": section_id,
    }


def test_not_started_counts_applicable_current_sections():
    result = (
        progress_service
        .calculate_fsms_policy_document_progress(
            structure_config=_structure(),
            screening_complete=False,
            applicable_safety_points=[
                _safety_point("4.1.1.1", "4"),
                _safety_point("5.1.1.1", "5"),
            ],
            approved_safety_points=[],
        )
    )

    assert result == FSMSPolicyDocumentProgress(
        screening_complete=False,
        completed_applicable_section_count=0,
        applicable_supported_section_count=4,
        completion_percentage=0,
        supported_section_count=4,
        planned_section_count=10,
        document_status="not_started",
        main_value="0%",
        completion_caption=(
            "Food Safety Profile not completed"
        ),
        coverage_caption=(
            "4 of 10 planned sections supported"
        ),
    )


def test_partial_approval_returns_in_progress_status():
    result = (
        progress_service
        .calculate_fsms_policy_document_progress(
            structure_config=_structure(),
            screening_complete=True,
            applicable_safety_points=[
                _safety_point("4.1.1.1", "4"),
                _safety_point("5.1.1.1", "5"),
                _safety_point("5.1.1.2", "5"),
            ],
            approved_safety_points=[
                _safety_point("4.1.1.1", "4"),
                _safety_point("5.1.1.1", "5"),
            ],
        )
    )

    assert (
        result.completed_applicable_section_count
        == 3
    )
    assert (
        result.applicable_supported_section_count
        == 4
    )
    assert result.screening_complete is True
    assert result.completion_percentage == 75
    assert result.document_status == "in_progress"
    assert result.main_value == "75%"
    assert result.completion_caption == (
        "3 of 4 current sections complete"
    )


def test_non_applicable_operational_section_is_excluded():
    result = (
        progress_service
        .calculate_fsms_policy_document_progress(
            structure_config=_structure(),
            screening_complete=True,
            applicable_safety_points=[
                _safety_point("4.1.1.1", "4"),
            ],
            approved_safety_points=[
                _safety_point("4.1.1.1", "4"),
            ],
        )
    )

    assert (
        result.completed_applicable_section_count
        == 3
    )
    assert (
        result.applicable_supported_section_count
        == 3
    )
    assert result.completion_percentage == 100
    assert result.document_status == "completed"
    assert result.main_value == "100%"
    assert result.completion_caption == (
        "3 of 3 current sections complete"
    )


def test_every_applicable_point_must_be_approved():
    result = (
        progress_service
        .calculate_fsms_policy_document_progress(
            structure_config=_structure(),
            screening_complete=True,
            applicable_safety_points=[
                _safety_point("4.1.1.1", "4"),
                _safety_point("4.1.1.2", "4"),
            ],
            approved_safety_points=[
                _safety_point("4.1.1.1", "4"),
            ],
        )
    )

    assert (
        result.completed_applicable_section_count
        == 2
    )
    assert (
        result.applicable_supported_section_count
        == 3
    )
    assert result.completion_percentage == 67
    assert result.document_status == "in_progress"


def test_beyond_scope_sections_affect_coverage_only():
    result = (
        progress_service
        .calculate_fsms_policy_document_progress(
            structure_config=_structure(),
            screening_complete=True,
            applicable_safety_points=[],
            approved_safety_points=[],
        )
    )

    assert (
        result.completed_applicable_section_count
        == 2
    )
    assert (
        result.applicable_supported_section_count
        == 2
    )
    assert result.completion_percentage == 100
    assert result.supported_section_count == 4
    assert result.planned_section_count == 10
    assert result.coverage_caption == (
        "4 of 10 planned sections supported"
    )


def test_generator_loads_live_business_sources(
    monkeypatch,
):
    db = object()
    calls = {}

    monkeypatch.setattr(
        progress_service,
        "load_fsms_policy_document_structure",
        lambda: _structure(),
    )

    def fake_screening_status(
        *,
        db,
        business_profile_id,
    ):
        calls["screening"] = (
            db,
            business_profile_id,
        )

        return {
            "is_complete": True,
        }

    def fake_relevant_points(
        *,
        db,
        business_profile_id,
    ):
        calls["applicable"] = (
            db,
            business_profile_id,
        )

        return [
            _safety_point("4.1.1.1", "4"),
        ]

    def fake_approved_methods(
        *,
        db,
        business_profile_id,
    ):
        calls["approved"] = (
            db,
            business_profile_id,
        )

        return {
            "approved_safety_points": [
                _safety_point("4.1.1.1", "4"),
            ],
        }

    monkeypatch.setattr(
        progress_service,
        "get_screening_completion_status",
        fake_screening_status,
    )
    monkeypatch.setattr(
        progress_service,
        "get_relevant_safety_points_for_profile",
        fake_relevant_points,
    )
    monkeypatch.setattr(
        progress_service,
        "get_approved_methods_for_profile",
        fake_approved_methods,
    )

    result = (
        progress_service
        .generate_fsms_policy_document_progress_for_profile(
            db=db,
            business_profile_id=42,
        )
    )

    assert result.completion_percentage == 100
    assert (
        result.applicable_supported_section_count
        == 3
    )
    assert calls == {
        "screening": (db, 42),
        "applicable": (db, 42),
        "approved": (db, 42),
    }


def test_unknown_current_section_inclusion_is_rejected():
    structure = _structure()
    structure["sections"][0]["inclusion"] = (
        "unknown_rule"
    )

    with pytest.raises(
        ValueError,
        match=(
            "Unsupported current FSMS policy section "
            "inclusion rule"
        ),
    ):
        (
            progress_service
            .calculate_fsms_policy_document_progress(
                structure_config=structure,
                screening_complete=True,
                applicable_safety_points=[],
                approved_safety_points=[],
            )
        )


def test_operational_section_requires_source_sections():
    structure = _structure()
    structure["sections"][2].pop(
        "source_section_ids"
    )

    with pytest.raises(
        ValueError,
        match="must define source section IDs",
    ):
        (
            progress_service
            .calculate_fsms_policy_document_progress(
                structure_config=structure,
                screening_complete=True,
                applicable_safety_points=[
                    _safety_point("4.1.1.1", "4"),
                ],
                approved_safety_points=[],
            )
        )


def test_invalid_applicable_safety_point_is_rejected():
    with pytest.raises(
        ValueError,
        match="missing 'section_id'",
    ):
        (
            progress_service
            .calculate_fsms_policy_document_progress(
                structure_config=_structure(),
                screening_complete=True,
                applicable_safety_points=[
                    {
                        "safety_point_id": "4.1.1.1",
                    },
                ],
                approved_safety_points=[],
            )
        )


def test_progress_schema_rejects_invalid_percentage():
    with pytest.raises(ValidationError):
        FSMSPolicyDocumentProgress(
            screening_complete=False,
            completed_applicable_section_count=0,
            applicable_supported_section_count=4,
            completion_percentage=101,
            supported_section_count=4,
            planned_section_count=10,
            document_status="not_started",
            main_value="101%",
            completion_caption=(
                "0 of 4 current sections complete"
            ),
            coverage_caption=(
                "4 of 10 planned sections supported"
            ),
        )
