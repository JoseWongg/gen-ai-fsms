import gen_ai_fsms.workflows.safety_point_graph as workflow_module


QUESTION_KEY = "chilling_equipment_temperature_checks"


class FakeSession:
    def commit(self):
        pass

    def rollback(self):
        pass

    def flush(self):
        pass

    def close(self):
        pass


class NoEquipmentAdapter:
    def extract_chilling_equipment_names(self, user_message):
        return {
            "has_usable_equipment_names": False,
            "no_chilling_equipment_declared": True,
            "equipment_names": [],
            "reason": "The business declared no chilling equipment.",
            "assistant_message": None,
        }


class FakeComposer:
    def filter_relevant_facts(self, *, facts, instruction):
        return list(facts or [])

    def compose_safety_point_review_message(self, **kwargs):
        return "Review this safety point."

    def compose_approval_confirmation(self, **kwargs):
        return "Approval recorded."

    def extract_business_context_facts(self, **kwargs):
        return {"facts": []}


def _question():
    return {
        "question_key": QUESTION_KEY,
        "question_text": (
            "What chilling equipment does the business use and how are "
            "its temperatures checked?"
        ),
        "required": True,
    }


def _safety_point():
    return {
        "safety_point_id": "4.1.1.3",
        "text": "Check chilling equipment temperatures.",
        "instruction": "Check chilling equipment temperatures.",
        "rationale": "Temperature checks confirm that food is kept cold.",
        "section_id": "chilling",
        "section_name": "Chilling",
        "safe_method_id": "4.1",
        "safe_method_name": "Chilled Storage",
        "source_references": [],
        "additional_source_references": [],
        "additional_questions": [_question()],
    }


def test_no_chilling_equipment_populates_both_response_versions(
    monkeypatch,
):
    approval_calls = []

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
        lambda db, business_profile_id: {
            "uses_chilling_equipment": "true"
        },
    )
    monkeypatch.setattr(
        workflow_module,
        "get_relevant_safety_points_for_profile",
        lambda db, business_profile_id: [_safety_point()],
    )
    monkeypatch.setattr(
        workflow_module,
        "get_business_context",
        lambda db, business_profile_id, user_id=None: {
            "business_name": "Test Business",
            "business_type_label": "Restaurant",
            "condition_values": {
                "uses_chilling_equipment": "true"
            },
            "screening_activities": [],
            "relevant_facts": [],
            "relevant_fact_texts": [],
        },
    )
    monkeypatch.setattr(
        workflow_module,
        "get_llm_adapter",
        lambda: NoEquipmentAdapter(),
    )
    monkeypatch.setattr(
        workflow_module,
        "SafetyPointMessageComposer",
        lambda: FakeComposer(),
    )

    def fake_record_approved_safety_point(*args, **kwargs):
        approval_calls.append(kwargs)
        return {"id": 123}

    monkeypatch.setattr(
        workflow_module,
        "record_approved_safety_point",
        fake_record_approved_safety_point,
    )

    graph = workflow_module.create_safety_point_graph()
    question = _question()

    result = graph.invoke(
        {
            "business_profile_id": 1,
            "user_id": 10,
            "last_user_message": (
                "The business does not use any chilling equipment."
            ),
            "awaiting_additional_answers": True,
            "pending_additional_questions": [question],
            "current_additional_question_index": 0,
            "current_additional_question": question,
        }
    )

    expected = (
        "The business stated that it does not use chilling equipment."
    )

    assert len(approval_calls) == 1
    assert approval_calls[0]["additional_answers"] == {
        QUESTION_KEY: expected
    }
    assert approval_calls[0]["document_additional_answers"] == {
        QUESTION_KEY: expected
    }
    assert result["status"] == "completed"


def test_completed_chilling_equipment_populates_both_response_versions(
    monkeypatch,
):
    saved_calls = []

    monkeypatch.setattr(
        workflow_module,
        "SessionLocal",
        lambda: FakeSession(),
    )

    def fake_save_chilling_equipment_items_for_profile(**kwargs):
        saved_calls.append(kwargs)
        return {
            "saved_count": 1,
            "skipped_count": 0,
            "saved_items": [],
            "skipped_items": [],
        }

    monkeypatch.setattr(
        workflow_module,
        "save_chilling_equipment_items_for_profile",
        fake_save_chilling_equipment_items_for_profile,
    )

    complete_item = {
        "equipment_name": "Fridge 1",
        "equipment_type": "upright refrigerator",
        "equipment_use": "chilled food storage",
        "temperature_check_method": (
            "digital display and probe thermometer"
        ),
        "attempt_count": 1,
        "is_complete": True,
    }

    state = {
        "business_profile_id": 1,
        "user_id": 10,
        "approval_chat_history": [],
        "additional_answers": {},
        "document_additional_answers": {},
    }
    flow = {
        "items": [complete_item],
        "saved_result": None,
    }

    result = workflow_module._finalize_chilling_equipment_flow(
        state=state,
        flow=flow,
    )

    expected = (
        "Chilling equipment recorded:\n"
        "- Fridge 1: upright refrigerator, chilled food storage, "
        "digital display and probe thermometer"
    )

    assert result["next_action"] == "record_approval"
    assert result["additional_answers"] == {
        QUESTION_KEY: expected
    }
    assert result["document_additional_answers"] == {
        QUESTION_KEY: expected
    }

    assert len(saved_calls) == 1
    assert saved_calls[0]["equipment_items"] == [complete_item]
