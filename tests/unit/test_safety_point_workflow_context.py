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

    assert result["last_review_message"] is None
    assert result["last_confirmation_message"] is None

    assert "the business" in result["assistant_message"]
    assert "Alternatively, you can ask clarification questions." in (
        result["assistant_message"]
    )

    assert approval_record_called is False
