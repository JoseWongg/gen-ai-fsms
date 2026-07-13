from types import SimpleNamespace

import gen_ai_fsms.api.routes.onboarding_screening as screening_routes


class FakeAdapter:
    def __init__(self, suggestion="true"):
        self.suggestion = suggestion
        self.calls = []

    def suggest_screening_answer(
        self,
        *,
        business_description,
        question_text,
    ):
        self.calls.append(
            {
                "business_description": business_description,
                "question_text": question_text,
            }
        )
        return self.suggestion


def test_set_current_screening_question_adds_llm_suggestion(monkeypatch):
    adapter = FakeAdapter(suggestion="true")
    monkeypatch.setattr(
        screening_routes,
        "get_llm_adapter",
        lambda: adapter,
    )

    state = {}
    question = {
        "question_id": "cooks_rice",
        "text": "Do you cook rice?",
        "sets_conditions": ["cooks_rice"],
        "question_type": "screening",
        "input_type": "yes_no",
        "options": [],
    }

    screening_routes.set_current_question_from_payload(
        state,
        question,
        business_description="We cook rice every day.",
    )

    assert state["current_question_id"] == "cooks_rice"
    assert state["current_question_input_type"] == "yes_no"
    assert state["current_question_suggested_answer"] == "true"
    assert adapter.calls == [
        {
            "business_description": "We cook rice every day.",
            "question_text": "Do you cook rice?",
        }
    ]

    response_fields = screening_routes.build_question_response_fields(state)

    assert response_fields["question_input_type"] == "yes_no"
    assert response_fields["question_suggested_answer"] == "true"


def test_business_context_question_does_not_request_suggestion(monkeypatch):
    def fail_if_called():
        raise AssertionError(
            "The LLM adapter must not be requested for business-context questions."
        )

    monkeypatch.setattr(
        screening_routes,
        "get_llm_adapter",
        fail_if_called,
    )

    state = {}
    question = {
        "question_id": "business_description",
        "text": "Tell us a little about the business.",
        "sets_conditions": [],
        "question_type": "business_context",
        "input_type": "textarea",
        "options": [],
    }

    screening_routes.set_current_question_from_payload(
        state,
        question,
        business_description="A bakery.",
    )

    assert state["current_question_input_type"] == "textarea"
    assert state["current_question_suggested_answer"] is None


def test_first_screening_question_uses_yes_no_input_and_description(
    monkeypatch,
):
    adapter = FakeAdapter(suggestion="false")

    monkeypatch.setattr(
        screening_routes,
        "get_llm_adapter",
        lambda: adapter,
    )
    monkeypatch.setattr(
        screening_routes,
        "get_next_question",
        lambda condition_values, answered_question_ids: {
            "question_id": "keeps_food_chilled",
            "text": (
                "Do you keep any food chilled in fridges or "
                "chilled display units?"
            ),
            "sets_conditions": ["keeps_food_chilled"],
        },
    )

    state = {}

    question = screening_routes.start_first_screening_question(
        state,
        business_description="We make cakes with chilled dairy fillings.",
    )

    assert question["input_type"] == "yes_no"
    assert state["current_question_input_type"] == "yes_no"
    assert state["current_question_suggested_answer"] == "false"
    assert state["next_action"] == "next_question"
    assert adapter.calls == [
        {
            "business_description": (
                "We make cakes with chilled dairy fillings."
            ),
            "question_text": (
                "Do you keep any food chilled in fridges or "
                "chilled display units?"
            ),
        }
    ]
