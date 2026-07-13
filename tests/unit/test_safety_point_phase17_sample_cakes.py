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


class SampleCakesJourneyAdapter:
    def interpret_safety_point_response(
        self,
        *,
        safety_point_text,
        user_message,
        pending_additional_question=None,
        conversation_history=None,
    ):
        clean_message = (user_message or "").lower()

        if "different method" in clean_message:
            return {
                "action": "different_method_declared",
                "assistant_message": (
                    "Alternative-method assessment is not available in this version."
                ),
            }

        if "approve" in clean_message or clean_message.strip() in {"yes", "yes."}:
            return {
                "action": "approval",
                "assistant_message": None,
            }

        return {
            "action": "clarification_request",
            "assistant_message": None,
        }

    def answer_safety_point_question(self, **kwargs):
        return "Clarification answer."

    def answer_additional_question_clarification(self, **kwargs):
        return "Additional question clarification answer."


class SampleCakesJourneyComposer:
    def __init__(self, review_calls):
        self.review_calls = review_calls

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
        relevant_facts = relevant_facts or []
        self.review_calls.append(
            {
                "business_context": business_context,
                "safety_point_id": safety_point.get("safety_point_id"),
                "relevant_facts": relevant_facts,
                "is_first_message": is_first_message,
            }
        )

        relevant_fact_text = " ".join(
            (
                fact.get("fact_text", "")
                if isinstance(fact, dict)
                else str(fact)
            )
            for fact in relevant_facts
        ).lower()

        if "probe" in relevant_fact_text or "thermometer" in relevant_fact_text:
            return (
                "Since Sample Cakes already records fridge temperatures with "
                "a probe thermometer, review this related chilling point before "
                "approving it."
            )

        return "Review this chilling safety point for Sample Cakes."

    def compose_approval_confirmation(self, **kwargs):
        return "Approval recorded for this safety point."

    def extract_business_context_facts(self, *, user_message, safety_point):
        clean_message = (user_message or "").lower()

        if "probe thermometer" not in clean_message:
            return {"facts": []}

        return {
            "facts": [
                {
                    "fact_type": "monitoring_or_recording_practice",
                    "fact_text": (
                        "Sample Cakes checks fridge temperatures every "
                        "morning with a probe thermometer before service."
                    ),
                    "normalised_fact": (
                        "checks_fridge_temperatures_every_morning_with_probe"
                    ),
                    "confidence": 0.95,
                }
            ]
        }


def _safety_points():
    return [
        {
            "safety_point_id": "4.1.1.1",
            "text": "Keep chilled food cold.",
            "instruction": "Keep chilled food cold.",
            "rationale": (
                "Keeping chilled food cold slows the growth of harmful bacteria."
            ),
            "section_id": "chilling",
            "section_name": "Chilling",
            "safe_method_id": "chilled_storage",
            "safe_method_name": "Chilled storage",
            "source_references": [],
            "additional_source_references": [],
            "additional_questions": [],
        },
        {
            "safety_point_id": "4.1.1.2",
            "text": "Check and record fridge temperatures.",
            "instruction": "Check and record fridge temperatures.",
            "rationale": (
                "Temperature checks help confirm chilled food is kept safely."
            ),
            "section_id": "chilling",
            "section_name": "Chilling",
            "safe_method_id": "temperature_monitoring",
            "safe_method_name": "Temperature monitoring",
            "source_references": [],
            "additional_source_references": [],
            "additional_questions": [
                {
                    "question_key": "where_temperature_records_are_kept",
                    "question_text": "Where are fridge temperature records kept?",
                    "required": True,
                }
            ],
        },
    ]


def _business_context(recorded_facts):
    relevant_facts = [
        {
            "fact_type": fact["fact_type"],
            "fact_text": fact["fact_text"],
            "normalised_fact": fact["normalised_fact"],
            "confidence": fact["confidence"],
        }
        for fact in recorded_facts
    ]

    return {
        "business_name": "Sample Cakes",
        "user_first_name": "Test User",
        "business_type_label": "Bakery",
        "business_description": (
            "Celebration cakes and cupcakes, including chilled dairy cream "
            "fillings."
        ),
        "condition_values": {
            "chills_food": "true",
            "cooks_food": "true",
        },
        "screening_activities": [
            "chills food",
            "cooks food",
        ],
        "relevant_facts": relevant_facts,
        "relevant_fact_texts": [
            fact["fact_text"] for fact in recorded_facts
        ],
    }


def _patch_sample_cakes_dependencies(
    monkeypatch,
    *,
    recorded_facts,
    approval_calls,
    review_calls,
):
    safety_points = _safety_points()

    monkeypatch.setattr(workflow_module, "SessionLocal", lambda: FakeSession())

    monkeypatch.setattr(
        workflow_module,
        "get_screening_completion_status",
        lambda db, business_profile_id: {
            "active_condition_count": 2,
            "completed_active_condition_count": 2,
            "is_complete": True,
        },
    )
    monkeypatch.setattr(
        workflow_module,
        "get_condition_values_for_profile",
        lambda db, business_profile_id: {
            "chills_food": "true",
            "cooks_food": "true",
        },
    )
    monkeypatch.setattr(
        workflow_module,
        "get_relevant_safety_points_for_profile",
        lambda db, business_profile_id: safety_points,
    )
    monkeypatch.setattr(
        workflow_module,
        "get_business_context",
        lambda db, business_profile_id, user_id=None: _business_context(
            recorded_facts
        ),
    )
    monkeypatch.setattr(
        workflow_module,
        "get_llm_adapter",
        lambda: SampleCakesJourneyAdapter(),
    )
    monkeypatch.setattr(
        workflow_module,
        "SafetyPointMessageComposer",
        lambda: SampleCakesJourneyComposer(review_calls),
    )

    def fake_create_business_context_fact(**kwargs):
        recorded_facts.append(
            {
                "fact_type": kwargs["fact_type"],
                "fact_text": kwargs["fact_text"],
                "normalised_fact": kwargs["normalised_fact"],
                "confidence": kwargs["confidence"],
                "source_user_message": kwargs["source_user_message"],
                "source_safety_point_id": kwargs["source_safety_point_id"],
                "business_profile_id": kwargs["business_profile_id"],
                "created_by_user_id": kwargs["created_by_user_id"],
                "commit": kwargs["commit"],
                "refresh": kwargs["refresh"],
            }
        )

    def fake_record_approved_safety_point(*args, **kwargs):
        approval_calls.append(kwargs)
        return {"id": len(approval_calls)}

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


def test_phase17_sample_cakes_probe_fact_is_saved_and_reused_only_for_personalisation(
    monkeypatch,
):
    recorded_facts = []
    approval_calls = []
    review_calls = []

    _patch_sample_cakes_dependencies(
        monkeypatch,
        recorded_facts=recorded_facts,
        approval_calls=approval_calls,
        review_calls=review_calls,
    )

    graph = workflow_module.create_safety_point_graph()

    initial_state = graph.invoke(
        {
            "business_profile_id": 1,
            "user_id": 10,
        }
    )

    assert initial_state["status"] == "in_progress"
    assert initial_state["next_action"] == "awaiting_user_message"
    assert initial_state["current_safety_point"]["safety_point_id"] == "4.1.1.1"
    assert "Review this chilling safety point" in initial_state["assistant_message"]
    assert approval_calls == []
    assert recorded_facts == []

    approval_state = dict(initial_state)
    approval_state["last_user_message"] = (
        "Yes, we approve this. At Sample Cakes we check fridge "
        "temperatures every morning with a probe thermometer before service."
    )

    after_first_approval = graph.invoke(approval_state)

    assert len(approval_calls) == 1
    assert approval_calls[0]["safety_point"]["safety_point_id"] == "4.1.1.1"
    assert after_first_approval["approved_safety_point_ids"] == ["4.1.1.1"]

    assert len(recorded_facts) == 1
    fact = recorded_facts[0]
    assert fact["business_profile_id"] == 1
    assert fact["created_by_user_id"] == 10
    assert fact["source_safety_point_id"] == "4.1.1.1"
    assert fact["fact_type"] == "monitoring_or_recording_practice"
    assert (
        fact["fact_text"]
        == (
            "Sample Cakes checks fridge temperatures every morning with a "
            "probe thermometer before service."
        )
    )
    assert (
        fact["normalised_fact"]
        == "checks_fridge_temperatures_every_morning_with_probe"
    )
    assert fact["confidence"] == 0.95
    assert fact["source_user_message"] == approval_state["last_user_message"]
    assert fact["commit"] is False
    assert fact["refresh"] is False

    assert after_first_approval["current_safety_point"]["safety_point_id"] == (
        "4.1.1.2"
    )
    assert after_first_approval["next_action"] == "awaiting_user_message"
    assert "probe thermometer" in after_first_approval["assistant_message"]

    second_review_call = review_calls[-1]
    assert second_review_call["safety_point_id"] == "4.1.1.2"
    assert any(
        "probe thermometer" in fact["fact_text"].lower()
        for fact in second_review_call["relevant_facts"]
    )

    # Regression check: only the very first safety point presented in this
    # conversation should be composed with is_first_message=True. Once the
    # approval chat history is non-empty, later safety points must not
    # re-greet the user by name.
    first_review_call = review_calls[0]
    assert first_review_call["is_first_message"] is True
    assert second_review_call["is_first_message"] is False

    second_approval_attempt = dict(after_first_approval)
    second_approval_attempt["last_user_message"] = (
        "Yes, I approve this next safety point."
    )

    after_second_attempt = graph.invoke(second_approval_attempt)

    assert len(approval_calls) == 1
    assert after_second_attempt["approved_safety_point_ids"] == ["4.1.1.1"]
    assert after_second_attempt["awaiting_additional_answers"] is True
    assert after_second_attempt["additional_answers"] == {}
    assert (
        "Where are fridge temperature records kept?"
        in after_second_attempt["assistant_message"]
    )
