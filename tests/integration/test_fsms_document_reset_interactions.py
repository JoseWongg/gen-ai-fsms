from types import SimpleNamespace

from sqlalchemy import inspect

from gen_ai_fsms.api.routes import (
    onboarding_approval as approval_routes,
    onboarding_screening as screening_routes,
)
from gen_ai_fsms.services import (
    fsms_policy_document_progress as progress_service,
    fsms_policy_document_service as document_service,
)
from gen_ai_fsms.db.models.approved_safety_point import (
    ApprovedSafetyPoint,
)
from gen_ai_fsms.db.models.approved_safety_point_response import (
    ApprovedSafetyPointResponse,
)
from gen_ai_fsms.db.models.business_profile import (
    BusinessProfile,
)
from gen_ai_fsms.db.models.condition_value import (
    ConditionValue,
)
from gen_ai_fsms.db.models.onboarding_session import (
    OnboardingSession,
)
from gen_ai_fsms.services.fsms_policy_document_pdf import (
    render_fsms_policy_document_pdf,
)


def _safety_point(
    safety_point_id,
    section_id,
    safe_method_id,
):
    return {
        "safety_point_id": safety_point_id,
        "section_id": section_id,
        "safe_method_id": safe_method_id,
        "instruction": (
            f"Approved procedure for {safety_point_id}."
        ),
        "rationale": (
            f"Food safety reason for {safety_point_id}."
        ),
        "source_references": [],
        "additional_source_references": [],
    }


class ResetState:
    def __init__(self):
        self.profile = SimpleNamespace(
            id=100,
            business_name="Example Foods Ltd",
            site_name="Example Kitchen",
            business_type="restaurant",
            business_description=(
                "A restaurant preparing chilled and "
                "cooked food."
            ),
        )
        self.screening_complete = True
        self.condition_values = {
            "chills_food": "true",
            "cooks_food": "true",
        }
        self.applicable_safety_points = [
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
        self.approved_safety_points = [
            {
                "safety_point_id": "4.1.1.1",
            },
            {
                "safety_point_id": "5.1.1.1",
            },
        ]
        self.active_chilling_equipment = [
            {
                "equipment_key": "fridge_1",
                "display_name": "Main fridge",
                "equipment_type": "fridge",
                "use_description": "Chilled storage",
                "temperature_check_method": (
                    "Digital display"
                ),
            },
        ]

    def clear_approved_methods(self):
        deleted_count = len(
            self.approved_safety_points
        )
        self.approved_safety_points = []
        self.active_chilling_equipment = []

        return deleted_count

    def clear_screening(self):
        deleted_count = len(self.condition_values)
        self.condition_values = {}
        self.applicable_safety_points = []
        self.screening_complete = False

        return deleted_count


class FakeQuery:
    def __init__(self, db, model):
        self.db = db
        self.model = model

    def filter(self, *args, **kwargs):
        return self

    def filter_by(self, *args, **kwargs):
        return self

    def all(self):
        if self.model is OnboardingSession:
            return self.db.session_batches.pop(0)

        return []

    def first(self):
        if self.model is BusinessProfile:
            return self.db.state.profile

        return None

    def delete(self, synchronize_session=False):
        if self.model is ConditionValue:
            return self.db.state.clear_screening()

        return 0


class FakeDb:
    def __init__(
        self,
        state,
        *,
        session_batches,
    ):
        self.state = state
        self.session_batches = list(session_batches)
        self.deleted_sessions = []
        self.commits = 0

    def query(self, model):
        return FakeQuery(self, model)

    def delete(self, value):
        self.deleted_sessions.append(
            (
                value.id,
                value.phase,
            )
        )

    def commit(self):
        self.commits += 1


def _patch_document_sources(
    monkeypatch,
    state,
):
    monkeypatch.setattr(
        document_service,
        "get_screening_completion_status",
        lambda **kwargs: {
            "is_complete": state.screening_complete,
        },
    )
    monkeypatch.setattr(
        document_service,
        "get_condition_values_for_profile",
        lambda **kwargs: state.condition_values,
    )
    monkeypatch.setattr(
        document_service,
        "get_relevant_safety_points_for_profile",
        lambda **kwargs: (
            state.applicable_safety_points
        ),
    )
    monkeypatch.setattr(
        document_service,
        "get_approved_methods_for_profile",
        lambda **kwargs: {
            "approved_safety_points": (
                state.approved_safety_points
            ),
        },
    )
    monkeypatch.setattr(
        document_service,
        "_get_active_chilling_equipment",
        lambda **kwargs: (
            state.active_chilling_equipment
        ),
    )


def _generate_document(
    monkeypatch,
    state,
    db,
):
    _patch_document_sources(
        monkeypatch,
        state,
    )

    return (
        document_service
        .generate_fsms_policy_document_for_profile(
            db=db,
            business_profile_id=state.profile.id,
        )
    )


def _calculate_progress(state):
    return (
        progress_service
        .calculate_fsms_policy_document_progress(
            structure_config=(
                document_service
                .load_fsms_policy_document_structure()
            ),
            screening_complete=(
                state.screening_complete
            ),
            applicable_safety_points=(
                state.applicable_safety_points
            ),
            approved_safety_points=(
                state.approved_safety_points
            ),
        )
    )


def test_builder_reset_rebuilds_document_and_progress(
    monkeypatch,
):
    state = ResetState()
    approval_session = SimpleNamespace(
        id=10,
        phase="safety_point_approval",
    )
    db = FakeDb(
        state,
        session_batches=[
            [approval_session],
        ],
    )

    monkeypatch.setattr(
        approval_routes,
        "get_current_user_profile",
        lambda db, current_user: state.profile,
    )
    monkeypatch.setattr(
        approval_routes,
        "reset_business_context_facts_for_profile",
        lambda **kwargs: 2,
    )
    monkeypatch.setattr(
        approval_routes,
        "reset_approved_methods_for_profile",
        lambda **kwargs: (
            state.clear_approved_methods()
        ),
    )

    response = (
        approval_routes
        .reset_safety_point_approval(
            db=db,
            current_user=SimpleNamespace(id=1),
        )
    )

    assert response[
        "deleted_approved_safety_point_count"
    ] == 2
    assert state.screening_complete is True
    assert state.profile.business_type == "restaurant"
    assert state.condition_values == {
        "chills_food": "true",
        "cooks_food": "true",
    }
    assert state.approved_safety_points == []
    assert state.active_chilling_equipment == []

    document = _generate_document(
        monkeypatch,
        state,
        db,
    )
    progress = _calculate_progress(state)

    assert document.document_status == "draft"
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

    for section_number in ("3", "4"):
        operational_section = next(
            section
            for section in document.sections
            if section.section_number == section_number
        )

        assert [
            block.text
            for block
            in operational_section.content_blocks
        ] == [
            (
                "Not completed. The relevant safety "
                "points have not yet been approved."
            )
        ]
    assert progress.screening_complete is True
    assert (
        progress.completed_applicable_section_count
        == 2
    )
    assert (
        progress.applicable_supported_section_count
        == 4
    )
    assert progress.completion_percentage == 50
    assert progress.supported_section_count == 4
    assert progress.planned_section_count == 10

    pdf_bytes = render_fsms_policy_document_pdf(
        document
    )

    assert pdf_bytes.startswith(b"%PDF")


def test_profile_reset_returns_downloadable_draft_shell(
    monkeypatch,
):
    state = ResetState()
    screening_session = SimpleNamespace(
        id=20,
        phase="screening",
    )
    approval_session = SimpleNamespace(
        id=21,
        phase="safety_point_approval",
    )
    db = FakeDb(
        state,
        session_batches=[
            [screening_session],
            [approval_session],
        ],
    )

    monkeypatch.setattr(
        screening_routes,
        "get_current_user_profile",
        lambda db, current_user: state.profile,
    )
    monkeypatch.setattr(
        screening_routes,
        "reset_business_context_facts_for_profile",
        lambda **kwargs: 2,
    )
    monkeypatch.setattr(
        screening_routes,
        "reset_approved_methods_for_profile",
        lambda **kwargs: (
            state.clear_approved_methods()
        ),
    )

    response = screening_routes.reset_screening(
        db=db,
        current_user=SimpleNamespace(id=1),
    )

    assert response[
        "deleted_screening_session_count"
    ] == 1
    assert response[
        "deleted_approval_session_count"
    ] == 1
    assert state.profile.business_type is None
    assert state.profile.business_description is None
    assert state.screening_complete is False
    assert state.condition_values == {}
    assert state.applicable_safety_points == []
    assert state.approved_safety_points == []

    document = _generate_document(
        monkeypatch,
        state,
        db,
    )
    progress = _calculate_progress(state)

    assert document.document_status == "draft"
    assert document.draft_notice is not None
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

    for section_number in ("3", "4"):
        operational_section = next(
            section
            for section in document.sections
            if section.section_number == section_number
        )

        assert [
            block.text
            for block
            in operational_section.content_blocks
        ] == [
            (
                "Not completed. Complete the Food "
                "Safety Profile to determine which "
                "controls apply to this section."
            )
        ]

    operations = document.sections[1].subsections[0]

    assert len(operations.content_blocks) == 1
    assert (
        "None"
        not in operations.content_blocks[0].text
    )

    assert progress.screening_complete is False
    assert progress.completion_percentage == 0
    assert progress.completion_caption == (
        "Food Safety Profile not completed"
    )
    assert progress.supported_section_count == 4
    assert progress.planned_section_count == 10

    pdf_bytes = render_fsms_policy_document_pdf(
        document
    )

    assert pdf_bytes.startswith(b"%PDF")


def test_document_response_is_deleted_with_approved_point():
    response_columns = {
        column.key
        for column in inspect(
            ApprovedSafetyPointResponse
        ).columns
    }
    response_relationship = inspect(
        ApprovedSafetyPoint
    ).relationships["responses"]

    assert "document_response_text" in response_columns
    assert "delete" in response_relationship.cascade
    assert (
        "delete-orphan"
        in response_relationship.cascade
    )
