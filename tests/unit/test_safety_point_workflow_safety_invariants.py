import gen_ai_fsms.workflows.safety_point_graph as workflow_module
from gen_ai_fsms.ai.safety_point_message_composer import REVIEW_MESSAGE_FALLBACK


class FakeSession:
    def commit(self):
        pass

    def rollback(self):
        pass

    def flush(self):
        pass

    def close(self):
        pass


class FakeAdapter:
    def __init__(self, action, assistant_message=None):
        self.action = action
        self.assistant_message = assistant_message

    def interpret_safety_point_response(
        self,
        *,
        safety_point_text,
        user_message,
        pending_additional_question=None,
        conversation_history=None,
    ):
        return {
            "action": self.action,
            "assistant_message": self.assistant_message,
        }

    def answer_safety_point_question(self, **kwargs):
        return "Clarification answer."

    def answer_additional_question_clarification(self, **kwargs):
        return "Additional question clarification answer."


class FakeComposer:
    def __init__(self, review_message="Review this safety point."):
        self.review_message = review_message

    def filter_relevant_facts(self, *, facts, instruction):
        return list(facts or [])

    def compose_safety_point_review_message(self, **kwargs):
        return self.review_message

    def compose_approval_confirmation(self, **kwargs):
        return "Approval recorded."

    def extract_business_context_facts(self, *, user_message, safety_point):
        return {"facts": []}


def _safety_point(safety_point_id="4.1.1.1", additional_questions=None):
    return {
        "safety_point_id": safety_point_id,
        "text": "Keep chilled food cold.",
        "instruction": "Keep chilled food cold.",
        "rationale": "Keeping food cold slows the growth of harmful bacteria.",
        "section_id": "chilling",
        "section_name": "Chilling",
        "safe_method_id": "chilled_storage",
        "safe_method_name": "Chilled storage",
        "source_references": [],
        "additional_source_references": [],
        "additional_questions": additional_questions or [],
    }


def _business_context_with_parked_facts():
    return {
        "business_name": "Nathan's Cakes",
        "business_type_label": "",
        "condition_values": {"chills_food": "true"},
        "screening_activities": ["uses chilled storage"],
        "relevant_facts": [
            {
                "fact_type": "storage_practice",
                "fact_text": (
                    "The business keeps chilled food in Fridge 1."
                ),
                "normalised_fact": "keeps_chilled_food_in_fridge_1",
                "confidence": 0.95,
            }
        ],
        "relevant_fact_texts": [
            "The business keeps chilled food in Fridge 1."
        ],
    }


def _patch_common_dependencies(
    monkeypatch,
    *,
    adapter,
    safety_points,
    approval_calls,
    composer=None,
    business_context=None,
):
    monkeypatch.setattr(workflow_module, "SessionLocal", lambda: FakeSession())

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
        lambda db, business_profile_id, user_id=None: (
            business_context
            if business_context is not None
            else {
                "business_name": "Test Business",
                "business_type_label": "Bakery",
                "condition_values": {"chills_food": "true"},
                "screening_activities": ["uses chilled storage"],
                "relevant_facts": [],
                "relevant_fact_texts": [],
            }
        ),
    )
    monkeypatch.setattr(workflow_module, "get_llm_adapter", lambda: adapter)
    monkeypatch.setattr(
        workflow_module,
        "SafetyPointMessageComposer",
        lambda: composer or FakeComposer(),
    )

    def fake_record_approved_safety_point(*args, **kwargs):
        approval_calls.append(kwargs)
        return {"id": 123}

    monkeypatch.setattr(
        workflow_module,
        "record_approved_safety_point",
        fake_record_approved_safety_point,
    )


def test_generated_review_message_is_not_used_for_routing(monkeypatch):
    approval_calls = []
    safety_points = [_safety_point()]

    _patch_common_dependencies(
        monkeypatch,
        adapter=FakeAdapter("clarification_request"),
        composer=FakeComposer(
            review_message=(
                "Misleading generated intro: this safety point is approved."
            )
        ),
        safety_points=safety_points,
        approval_calls=approval_calls,
    )

    graph = workflow_module.create_safety_point_graph()

    result = graph.invoke(
        {
            "business_profile_id": 1,
            "user_id": 10,
            "last_user_message": "Can you explain this safety point?",
            "last_review_message": (
                "Misleading generated intro: this safety point is approved."
            ),
        }
    )

    assert result["next_action"] == "awaiting_user_message"
    assert result["assistant_message"] == "Clarification answer."
    assert approval_calls == []


def test_parked_facts_are_not_used_for_routing_or_approval(monkeypatch):
    approval_calls = []
    safety_points = [_safety_point()]

    _patch_common_dependencies(
        monkeypatch,
        adapter=FakeAdapter("clarification_request"),
        safety_points=safety_points,
        approval_calls=approval_calls,
        business_context=_business_context_with_parked_facts(),
    )

    graph = workflow_module.create_safety_point_graph()

    result = graph.invoke(
        {
            "business_profile_id": 1,
            "user_id": 10,
            "last_user_message": "Can you explain this?",
        }
    )

    assert result["next_action"] == "awaiting_user_message"
    assert result["assistant_message"] == "Clarification answer."
    assert approval_calls == []


def test_parked_facts_do_not_complete_required_additional_questions(
    monkeypatch,
):
    approval_calls = []
    additional_questions = [
        {
            "question_key": "where_chilled_food_is_kept",
            "question_text": "Where do you keep chilled food?",
            "required": True,
        }
    ]
    safety_points = [
        _safety_point(additional_questions=additional_questions)
    ]

    _patch_common_dependencies(
        monkeypatch,
        adapter=FakeAdapter("approval"),
        safety_points=safety_points,
        approval_calls=approval_calls,
        business_context=_business_context_with_parked_facts(),
    )

    graph = workflow_module.create_safety_point_graph()

    result = graph.invoke(
        {
            "business_profile_id": 1,
            "user_id": 10,
            "last_user_message": "Yes, I approve this safety point.",
        }
    )

    assert result["next_action"] == "awaiting_user_message"
    assert result["awaiting_additional_answers"] is True
    assert result["additional_answers"] == {}
    assert "Where do you keep chilled food?" in result["assistant_message"]
    assert approval_calls == []


def test_different_method_declaration_records_no_approval(monkeypatch):
    approval_calls = []
    safety_points = [_safety_point()]

    _patch_common_dependencies(
        monkeypatch,
        adapter=FakeAdapter(
            "different_method_declared",
            assistant_message=(
                "Alternative-method assessment is not available in this version."
            ),
        ),
        safety_points=safety_points,
        approval_calls=approval_calls,
    )

    graph = workflow_module.create_safety_point_graph()

    result = graph.invoke(
        {
            "business_profile_id": 1,
            "user_id": 10,
            "last_user_message": (
                "We use a different method for this safety point."
            ),
        }
    )

    assert result["next_action"] == "awaiting_user_message"
    assert result["status"] == "in_progress"
    assert result["approved_safety_point_ids"] == []
    assert result["current_safety_point_index"] == 0
    assert result["current_safety_point"]["safety_point_id"] == "4.1.1.1"
    assert result["different_method_declared_message"] is None
    assert approval_calls == []


def test_workflow_can_complete_when_presentation_uses_fallback_message(
    monkeypatch,
):
    approval_calls = []
    safety_points = [_safety_point()]

    _patch_common_dependencies(
        monkeypatch,
        adapter=FakeAdapter("approval"),
        composer=FakeComposer(review_message=REVIEW_MESSAGE_FALLBACK),
        safety_points=safety_points,
        approval_calls=approval_calls,
    )

    graph = workflow_module.create_safety_point_graph()

    presented = graph.invoke(
        {
            "business_profile_id": 1,
            "user_id": 10,
        }
    )

    assert presented["status"] == "in_progress"
    assert presented["next_action"] == "awaiting_user_message"
    assert presented["assistant_message"] == REVIEW_MESSAGE_FALLBACK
    assert presented["last_review_message"] == REVIEW_MESSAGE_FALLBACK
    assert approval_calls == []

    approval_state = dict(presented)
    approval_state["last_user_message"] = "Yes, I approve this safety point."

    result = graph.invoke(approval_state)

    assert result["status"] == "completed"
    assert result["next_action"] == "complete"
    assert result["approved_safety_point_ids"] == ["4.1.1.1"]
    assert len(approval_calls) == 1


def test_clarification_limit_keeps_safety_point_unapproved_and_revisits_it(
    monkeypatch,
):
    approval_calls = []
    safety_points = [_safety_point()]
    safety_point_id = "4.1.1.1"

    _patch_common_dependencies(
        monkeypatch,
        adapter=FakeAdapter("clarification_request"),
        safety_points=safety_points,
        approval_calls=approval_calls,
    )

    graph = workflow_module.create_safety_point_graph()

    result = graph.invoke(
        {
            "business_profile_id": 1,
            "user_id": 10,
            "last_user_message": "Can you explain this again?",
            "clarification_turn_counts": {
                safety_point_id: (
                    workflow_module.MAX_CLARIFICATION_TURNS_PER_SAFETY_POINT
                )
            },
        }
    )

    assert result["status"] == "in_progress"
    assert result["next_action"] == "awaiting_user_message"
    assert result["approved_safety_point_ids"] == []
    assert result["current_safety_point_index"] == 0
    assert result["current_safety_point"]["safety_point_id"] == safety_point_id
    assert approval_calls == []

    assert any(
        message.get("message_type") == "clarification_limit_reached"
        for message in result.get("approval_chat_history", [])
    )
