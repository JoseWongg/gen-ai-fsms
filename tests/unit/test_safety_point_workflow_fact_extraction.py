import gen_ai_fsms.workflows.safety_point_graph as workflow_module


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
    def __init__(self, action):
        self.action = action

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
            "assistant_message": None,
        }

    def answer_safety_point_question(self, **kwargs):
        return "Clarification answer."

    def answer_additional_question_clarification(self, **kwargs):
        return "Additional question clarification answer."


class FakeComposer:
    def __init__(self, facts=None, raise_on_extract=False):
        self.facts = facts or []
        self.raise_on_extract = raise_on_extract

    def compose_safety_point_review_message(self, **kwargs):
        return "Review this safety point."

    def compose_approval_confirmation(self, **kwargs):
        return "Approval recorded."

    def extract_business_context_facts(self, *, user_message, safety_point):
        if self.raise_on_extract:
            raise RuntimeError("Fact extraction failed.")
        return {"facts": self.facts}


def _safety_point(additional_questions=None):
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
        "additional_questions": additional_questions or [],
    }


def _patch_common_dependencies(
    monkeypatch,
    *,
    adapter,
    composer,
    safety_points,
    recorded_facts,
    approval_calls,
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
        lambda db, business_profile_id, user_id=None: {
            "business_name": "Test Bakery",
            "business_type_label": "Bakery",
            "condition_values": {"chills_food": "true"},
            "screening_activities": ["uses chilled storage"],
            "relevant_facts": [],
            "relevant_fact_texts": [],
        },
    )
    monkeypatch.setattr(workflow_module, "get_llm_adapter", lambda: adapter)
    monkeypatch.setattr(workflow_module, "SafetyPointMessageComposer", lambda: composer)

    def fake_create_business_context_fact(**kwargs):
        recorded_facts.append(kwargs)

    def fake_record_approved_safety_point(*args, **kwargs):
        approval_calls.append(kwargs)
        return {"id": 123}

    monkeypatch.setattr(
        workflow_module,
        "create_business_context_fact",
        fake_create_business_context_fact,
    )
    monkeypatch.setattr(
        workflow_module,
        "record_approved_safety_point",
        fake_record_approved_safety_point,
    )


def test_clarification_message_can_persist_business_context_fact(monkeypatch):
    recorded_facts = []
    approval_calls = []
    safety_points = [_safety_point()]

    _patch_common_dependencies(
        monkeypatch,
        adapter=FakeAdapter("clarification_request"),
        composer=FakeComposer(
            facts=[
                {
                    "fact_type": "monitoring_or_recording_practice",
                    "fact_text": "The business checks fridge temperatures daily.",
                    "normalised_fact": "checks_fridge_temperatures_daily",
                    "confidence": 0.95,
                }
            ]
        ),
        safety_points=safety_points,
        recorded_facts=recorded_facts,
        approval_calls=approval_calls,
    )

    graph = workflow_module.create_safety_point_graph()

    result = graph.invoke(
        {
            "business_profile_id": 1,
            "user_id": 10,
            "last_user_message": (
                "Can you explain this? We check fridge temperatures every day."
            ),
        }
    )

    assert result["next_action"] == "awaiting_user_message"
    assert result["assistant_message"] == "Clarification answer."
    assert approval_calls == []

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
        == "Can you explain this? We check fridge temperatures every day."
    )
    assert recorded_fact["normalised_fact"] == "checks_fridge_temperatures_daily"
    assert recorded_fact["confidence"] == 0.95
    assert recorded_fact["created_by_user_id"] == 10
    assert recorded_fact["commit"] is False
    assert recorded_fact["refresh"] is False


def test_additional_question_answer_can_persist_fact_separately_from_approval(
    monkeypatch,
):
    recorded_facts = []
    approval_calls = []
    additional_questions = [
        {
            "question_key": "where_chilled_food_is_kept",
            "question_text": "Where do you keep chilled food?",
            "required": True,
        }
    ]
    safety_points = [_safety_point(additional_questions=additional_questions)]

    _patch_common_dependencies(
        monkeypatch,
        adapter=FakeAdapter("additional_answer"),
        composer=FakeComposer(
            facts=[
                {
                    "fact_type": "storage_practice",
                    "fact_text": "The business keeps chilled food in Fridge 1.",
                    "normalised_fact": "keeps_chilled_food_in_fridge_1",
                    "confidence": 0.9,
                }
            ]
        ),
        safety_points=safety_points,
        recorded_facts=recorded_facts,
        approval_calls=approval_calls,
    )

    graph = workflow_module.create_safety_point_graph()

    result = graph.invoke(
        {
            "business_profile_id": 1,
            "user_id": 10,
            "last_user_message": "We keep chilled food in Fridge 1.",
            "awaiting_additional_answers": True,
            "current_additional_question_index": 0,
            "pending_additional_questions": additional_questions,
            "current_additional_question": additional_questions[0],
        }
    )

    assert result["next_action"] == "complete"
    assert result["status"] == "completed"
    assert (
        result["assistant_message"]
        == "All relevant safety points have been approved."
    )
    assert result["additional_answers"] == {}

    assert len(approval_calls) == 1
    assert approval_calls[0]["additional_answers"] == {
        "where_chilled_food_is_kept": "We keep chilled food in Fridge 1."
    }
    assert approval_calls[0]["additional_answers"] == {
        "where_chilled_food_is_kept": "We keep chilled food in Fridge 1."
    }

    assert len(recorded_facts) == 1
    recorded_fact = recorded_facts[0]
    assert recorded_fact["fact_type"] == "storage_practice"
    assert (
        recorded_fact["fact_text"]
        == "The business keeps chilled food in Fridge 1."
    )
    assert (
        recorded_fact["source_user_message"]
        == "We keep chilled food in Fridge 1."
    )


def test_plain_approval_with_no_extracted_facts_stores_no_fact(monkeypatch):
    recorded_facts = []
    approval_calls = []
    safety_points = [_safety_point()]

    _patch_common_dependencies(
        monkeypatch,
        adapter=FakeAdapter("approval"),
        composer=FakeComposer(facts=[]),
        safety_points=safety_points,
        recorded_facts=recorded_facts,
        approval_calls=approval_calls,
    )

    graph = workflow_module.create_safety_point_graph()

    result = graph.invoke(
        {
            "business_profile_id": 1,
            "user_id": 10,
            "last_user_message": "Yes.",
        }
    )

    assert result["status"] == "completed"
    assert result["assistant_message"] == "All relevant safety points have been approved."
    assert len(approval_calls) == 1
    assert recorded_facts == []


def test_fact_extraction_failure_does_not_block_approval(monkeypatch):
    recorded_facts = []
    approval_calls = []
    safety_points = [_safety_point()]

    _patch_common_dependencies(
        monkeypatch,
        adapter=FakeAdapter("approval"),
        composer=FakeComposer(raise_on_extract=True),
        safety_points=safety_points,
        recorded_facts=recorded_facts,
        approval_calls=approval_calls,
    )

    graph = workflow_module.create_safety_point_graph()

    result = graph.invoke(
        {
            "business_profile_id": 1,
            "user_id": 10,
            "last_user_message": (
                "Yes, and we check temperatures every day with a probe."
            ),
        }
    )

    assert result["status"] == "completed"
    assert len(approval_calls) == 1
    assert recorded_facts == []
