import pytest

import gen_ai_fsms.workflows.safety_point_graph as workflow_module


class FakeSession:
    def __init__(self, event_log):
        self.event_log = event_log

    def commit(self):
        self.event_log.append("commit")

    def rollback(self):
        self.event_log.append("rollback")

    def flush(self):
        self.event_log.append("flush")

    def close(self):
        self.event_log.append("close")


class FakeAdapter:
    def interpret_safety_point_response(
        self,
        *,
        safety_point_text,
        user_message,
        pending_additional_question=None,
        conversation_history=None,
    ):
        return {
            "action": "approval",
            "assistant_message": None,
        }


class FakeComposer:
    def __init__(self, event_log, confirmation_message):
        self.event_log = event_log
        self.confirmation_message = confirmation_message

    def compose_safety_point_review_message(self, **kwargs):
        self.event_log.append("compose_review")
        return "Review this safety point."

    def compose_approval_confirmation(self, **kwargs):
        self.event_log.append("compose_confirmation")
        return self.confirmation_message

    def extract_business_context_facts(self, *, user_message, safety_point):
        self.event_log.append("extract_facts")
        return {"facts": []}


def _safety_point():
    return {
        "safety_point_id": "4.1.1.1",
        "text": "Keep chilled food cold.",
        "instruction": "Keep chilled food cold.",
        "rationale": "Keeping food cold slows the growth of harmful bacteria.",
        "section_id": "chilling",
        "section_name": "Chilling",
        "safe_method_id": "chilled_storage",
        "safe_method_name": "Chilled storage",
        "source_references": [],
        "additional_source_references": [],
        "additional_questions": [],
    }


def _patch_common_dependencies(
    monkeypatch,
    *,
    event_log,
    approval_should_fail=False,
    confirmation_message="Personalised confirmation generated after approval.",
):
    safety_points = [_safety_point()]

    monkeypatch.setattr(
        workflow_module,
        "SessionLocal",
        lambda: FakeSession(event_log),
    )
    monkeypatch.setattr(
        workflow_module,
        "get_screening_completion_status",
        lambda db, business_profile_id: {
            "active_condition_count": 1,
            "completed_active_condition_count": 1,
            "is_complete": True,
        },
    )
    monkeypatch.setattr(
        workflow_module,
        "get_condition_values_for_profile",
        lambda db, business_profile_id: {"chills_food": "true"},
    )
    monkeypatch.setattr(
        workflow_module,
        "get_relevant_safety_points_for_profile",
        lambda db, business_profile_id: safety_points,
    )
    monkeypatch.setattr(
        workflow_module,
        "get_business_context",
        lambda db, business_profile_id, user_id=None: {
            "business_name": "Test Bakery",
            "business_type_label": "Bakery",
            "condition_values": {"chills_food": "true"},
            "screening_activities": ["uses chilled storage"],
            "relevant_facts": [],
            "relevant_fact_texts": [],
        },
    )
    monkeypatch.setattr(workflow_module, "get_llm_adapter", lambda: FakeAdapter())
    monkeypatch.setattr(
        workflow_module,
        "SafetyPointMessageComposer",
        lambda: FakeComposer(
            event_log=event_log,
            confirmation_message=confirmation_message,
        ),
    )

    def fake_record_approved_safety_point(*args, **kwargs):
        event_log.append("record_approval")

        if approval_should_fail:
            raise RuntimeError("approval write failed")

        return {"id": 123}

    monkeypatch.setattr(
        workflow_module,
        "record_approved_safety_point",
        fake_record_approved_safety_point,
    )


def test_approval_is_committed_before_confirmation_is_generated(monkeypatch):
    event_log = []

    _patch_common_dependencies(
        monkeypatch,
        event_log=event_log,
        confirmation_message="Personalised confirmation generated after approval.",
    )

    graph = workflow_module.create_safety_point_graph()

    result = graph.invoke(
        {
            "business_profile_id": 1,
            "user_id": 10,
            "last_user_message": "Yes, I approve this safety point.",
        }
    )

    assert result["status"] == "completed"
    assert result["next_action"] == "complete"
    assert (
        result["last_confirmation_message"]
        == "Personalised confirmation generated after approval."
    )

    assert "record_approval" in event_log
    assert "commit" in event_log
    assert "compose_confirmation" in event_log

    assert event_log.index("record_approval") < event_log.index("commit")
    assert event_log.index("commit") < event_log.index("compose_confirmation")


def test_confirmation_is_not_generated_if_approval_recording_fails(monkeypatch):
    event_log = []

    _patch_common_dependencies(
        monkeypatch,
        event_log=event_log,
        approval_should_fail=True,
    )

    graph = workflow_module.create_safety_point_graph()

    with pytest.raises(RuntimeError, match="approval write failed"):
        graph.invoke(
            {
                "business_profile_id": 1,
                "user_id": 10,
                "last_user_message": "Yes, I approve this safety point.",
            }
        )

    assert "record_approval" in event_log
    assert "rollback" in event_log
    assert "commit" not in event_log
    assert "compose_confirmation" not in event_log


def test_generated_confirmation_does_not_control_workflow_routing(monkeypatch):
    event_log = []
    misleading_confirmation = (
        "Please ask another clarification question before this can be approved."
    )

    _patch_common_dependencies(
        monkeypatch,
        event_log=event_log,
        confirmation_message=misleading_confirmation,
    )

    graph = workflow_module.create_safety_point_graph()

    result = graph.invoke(
        {
            "business_profile_id": 1,
            "user_id": 10,
            "last_user_message": "Yes, I approve this safety point.",
        }
    )

    assert result["status"] == "completed"
    assert result["next_action"] == "complete"
    assert result["last_confirmation_message"] == misleading_confirmation
    assert (
        result["assistant_message"]
        == "All relevant safety points have been approved."
    )

    assert event_log.count("record_approval") == 1
    assert event_log.count("compose_confirmation") == 1


def test_approved_safety_point_id_is_not_duplicated_in_workflow_state(
    monkeypatch,
):
    event_log = []

    _patch_common_dependencies(
        monkeypatch,
        event_log=event_log,
        confirmation_message="Approval recorded.",
    )

    graph = workflow_module.create_safety_point_graph()

    result = graph.invoke(
        {
            "business_profile_id": 1,
            "user_id": 10,
            "last_user_message": "Yes, I approve this safety point.",
            "approved_safety_point_ids": ["4.1.1.1"],
        }
    )

    assert result["approved_safety_point_ids"].count("4.1.1.1") == 1
    assert event_log.count("record_approval") <= 1
    assert event_log.count("compose_confirmation") <= 1
