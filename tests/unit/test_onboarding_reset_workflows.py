from types import SimpleNamespace

import gen_ai_fsms.api.routes.onboarding_approval as approval_routes
import gen_ai_fsms.api.routes.onboarding_screening as screening_routes
from gen_ai_fsms.db.models.condition_value import ConditionValue
from gen_ai_fsms.db.models.onboarding_session import OnboardingSession


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

    def delete(self, synchronize_session=False):
        if self.model is ConditionValue:
            self.db.events.append(("delete_condition_values",))
            return self.db.condition_value_delete_count

        self.db.events.append(("delete_query", self.model))
        return 0


class FakeDb:
    def __init__(self, session_batches=None, condition_value_delete_count=0):
        self.session_batches = list(session_batches or [])
        self.condition_value_delete_count = condition_value_delete_count
        self.events = []

    def query(self, model):
        return FakeQuery(self, model)

    def delete(self, obj):
        self.events.append(("delete_session", obj.id, obj.phase))

    def commit(self):
        self.events.append(("commit",))


def test_safety_point_approval_reset_deletes_parked_facts_before_session_delete(
    monkeypatch,
):
    profile = SimpleNamespace(id=100)
    approval_sessions = [
        SimpleNamespace(id=10, phase="safety_point_approval"),
        SimpleNamespace(id=11, phase="safety_point_approval"),
    ]
    db = FakeDb(session_batches=[approval_sessions])

    monkeypatch.setattr(
        approval_routes,
        "get_current_user_profile",
        lambda db, current_user: profile,
    )

    def fake_reset_facts(db, business_profile_id, workflow_session_ids=None):
        db.events.append(
            (
                "delete_business_context_facts",
                business_profile_id,
                tuple(workflow_session_ids or []),
            )
        )
        return 2

    def fake_reset_approved_methods(db, business_profile_id):
        db.events.append(("delete_approved_methods", business_profile_id))
        return 3

    monkeypatch.setattr(
        approval_routes,
        "reset_business_context_facts_for_profile",
        fake_reset_facts,
    )
    monkeypatch.setattr(
        approval_routes,
        "reset_approved_methods_for_profile",
        fake_reset_approved_methods,
    )

    response = approval_routes.reset_safety_point_approval(
        db=db,
        current_user=SimpleNamespace(id=1),
    )

    assert response["deleted_session_count"] == 2
    assert response["deleted_business_context_fact_count"] == 2
    assert response["deleted_approved_safety_point_count"] == 3

    assert db.events == [
        ("delete_business_context_facts", 100, ()),
        ("delete_session", 10, "safety_point_approval"),
        ("delete_session", 11, "safety_point_approval"),
        ("delete_approved_methods", 100),
        ("commit",),
    ]


def test_screening_reset_deletes_parked_facts_before_sessions_and_values(
    monkeypatch,
):
    profile = SimpleNamespace(
        id=200,
        business_type="bakery",
        business_description="Cake business",
    )
    screening_sessions = [
        SimpleNamespace(id=20, phase="screening"),
    ]
    approval_sessions = [
        SimpleNamespace(id=21, phase="safety_point_approval"),
    ]
    db = FakeDb(
        session_batches=[screening_sessions, approval_sessions],
        condition_value_delete_count=4,
    )

    monkeypatch.setattr(
        screening_routes,
        "get_current_user_profile",
        lambda db, current_user: profile,
    )

    def fake_reset_facts(db, business_profile_id, workflow_session_ids=None):
        db.events.append(
            (
                "delete_business_context_facts",
                business_profile_id,
                workflow_session_ids,
            )
        )
        return 5

    def fake_reset_approved_methods(db, business_profile_id):
        db.events.append(("delete_approved_methods", business_profile_id))
        return 6

    monkeypatch.setattr(
        screening_routes,
        "reset_business_context_facts_for_profile",
        fake_reset_facts,
    )
    monkeypatch.setattr(
        screening_routes,
        "reset_approved_methods_for_profile",
        fake_reset_approved_methods,
    )

    response = screening_routes.reset_screening(
        db=db,
        current_user=SimpleNamespace(id=1),
    )

    assert profile.business_type is None
    assert profile.business_description is None

    assert response["deleted_screening_session_count"] == 1
    assert response["deleted_approval_session_count"] == 1
    assert response["deleted_condition_value_count"] == 4
    assert response["deleted_business_context_fact_count"] == 5
    assert response["deleted_approved_safety_point_count"] == 6

    assert db.events == [
        ("delete_business_context_facts", 200, None),
        ("delete_session", 20, "screening"),
        ("delete_session", 21, "safety_point_approval"),
        ("delete_condition_values",),
        ("delete_approved_methods", 200),
        ("commit",),
    ]
