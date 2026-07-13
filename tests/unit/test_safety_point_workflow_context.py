import gen_ai_fsms.workflows.safety_point_graph as workflow_module


class FakeSession:
    def close(self):
        pass


def test_workflow_loads_business_context_without_changing_initial_routing(
    monkeypatch,
):
    safety_points = [
        {
            "safety_point_id": "4.1.1.1",
            "text": "Original SFBB text about chilled food.",
            "instruction": "Chilled food is kept cold.",
            "rationale": "Keeping chilled food cold helps prevent harmful bacteria from growing.",
            "section_id": "chilling",
            "section_name": "Chilling",
            "safe_method_id": "chilled_storage",
            "safe_method_name": "Chilled storage",
            "source_references": [],
            "additional_source_references": [],
            "additional_questions": [],
        }
    ]

    business_context = {
        "user_first_name": "Jose",
        "business_name": "Test Bakery",
        "site_name": "Main Kitchen",
        "business_type": "bakery",
        "business_type_label": "Bakery",
        "business_description": "Makes celebration cakes and cupcakes.",
        "condition_values": {"chills_food": "true"},
        "screening_activities": ["uses chilled storage"],
        "relevant_facts": [],
        "relevant_fact_texts": [],
    }

    approval_record_called = False

    def fake_record_approved_safety_point(*args, **kwargs):
        nonlocal approval_record_called
        approval_record_called = True
        return {}

    class FakeSafetyPointMessageComposer:
        def filter_relevant_facts(self, *, facts, instruction):
            return list(facts or [])

        def compose_safety_point_review_message(
            self,
            *,
            business_context,
            safety_point,
            relevant_facts=None,
            is_first_message=True,
            previous_message=None,
            previous_review_message=None,
        ):
            assert business_context["business_name"] == "Test Bakery"
            assert safety_point["safety_point_id"] == "4.1.1.1"
            assert relevant_facts == []
            return "Review this chilled storage safety point."

    monkeypatch.setattr(
        workflow_module,
        "SafetyPointMessageComposer",
        lambda: FakeSafetyPointMessageComposer(),
    )

    monkeypatch.setattr(
        workflow_module,
        "SessionLocal",
        lambda: FakeSession(),
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
        lambda db, business_profile_id, user_id=None: business_context,
    )
    monkeypatch.setattr(
        workflow_module,
        "record_approved_safety_point",
        fake_record_approved_safety_point,
    )

    graph = workflow_module.create_safety_point_graph()

    result = graph.invoke(
        {
            "business_profile_id": 1,
            "user_id": 10,
        }
    )

    assert result["status"] == "in_progress"
    assert result["next_action"] == "awaiting_user_message"
    assert result["condition_values"] == {"chills_food": "true"}
    assert result["business_context"] == business_context
    assert result["safety_points_list"] == safety_points
    assert result["relevant_safety_point_count"] == 1
    assert result["current_safety_point"]["safety_point_id"] == "4.1.1.1"
    assert result["current_safety_point_view"]["safety_point_id"] == "4.1.1.1"
    assert (
        result["current_safety_point_view"]["safety_point_text"]
        == "Original SFBB text about chilled food."
    )
    assert (
        result["current_safety_point_view"]["original_safety_point_text"]
        == "Original SFBB text about chilled food."
    )
    assert (
        result["current_safety_point_view"]["safety_point_instruction"]
        == "Chilled food is kept cold."
    )
    assert (
        result["current_safety_point_view"]["safety_point_rationale"]
        == "Keeping chilled food cold helps prevent harmful bacteria from growing."
    )

    assert result["assistant_message"] == "Review this chilled storage safety point."
    assert result["last_review_message"] == "Review this chilled storage safety point."
    assert result["last_confirmation_message"] is None


    assert approval_record_called is False


def test_persist_business_context_facts_from_user_message(monkeypatch):
    recorded_facts = []

    class FakeSessionWithTransaction:
        def __init__(self):
            self.committed = False
            self.rolled_back = False
            self.closed = False

        def commit(self):
            self.committed = True

        def rollback(self):
            self.rolled_back = True

        def close(self):
            self.closed = True

    db = FakeSessionWithTransaction()

    class FakeSafetyPointMessageComposer:
        def extract_business_context_facts(
            self,
            *,
            user_message,
            safety_point,
        ):
            assert user_message == "We check fridge temperatures daily."
            assert safety_point["safety_point_id"] == "4.1.1.1"
            return {
                "facts": [
                    {
                        "fact_type": "monitoring_or_recording_practice",
                        "fact_text": "The business checks fridge temperatures daily.",
                        "normalised_fact": "checks_fridge_temperatures_daily",
                        "confidence": 0.95,
                    }
                ]
            }

    def fake_create_business_context_fact(**kwargs):
        recorded_facts.append(kwargs)

    monkeypatch.setattr(
        workflow_module,
        "SafetyPointMessageComposer",
        lambda: FakeSafetyPointMessageComposer(),
    )
    monkeypatch.setattr(workflow_module, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        workflow_module,
        "create_business_context_fact",
        fake_create_business_context_fact,
    )

    workflow_module._persist_business_context_facts_from_message(
        state={
            "business_profile_id": 1,
            "user_id": 10,
        },
        user_message="We check fridge temperatures daily.",
        current_safety_point={
            "safety_point_id": "4.1.1.1",
            "section_name": "Chilling",
            "safe_method_name": "Chilled storage",
        },
    )

    assert len(recorded_facts) == 1
    recorded_fact = recorded_facts[0]

    assert recorded_fact["business_profile_id"] == 1
    assert recorded_fact["fact_type"] == "monitoring_or_recording_practice"
    assert (
        recorded_fact["fact_text"]
        == "The business checks fridge temperatures daily."
    )
    assert recorded_fact["source_safety_point_id"] == "4.1.1.1"
    assert (
        recorded_fact["source_user_message"]
        == "We check fridge temperatures daily."
    )
    assert recorded_fact["normalised_fact"] == "checks_fridge_temperatures_daily"
    assert recorded_fact["confidence"] == 0.95
    assert recorded_fact["created_by_user_id"] == 10
    assert recorded_fact["commit"] is False
    assert recorded_fact["refresh"] is False

    assert db.committed is True
    assert db.rolled_back is False
    assert db.closed is True
