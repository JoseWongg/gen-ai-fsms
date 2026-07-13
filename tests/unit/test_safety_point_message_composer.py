import json
from types import SimpleNamespace

from gen_ai_fsms.ai.safety_point_message_composer import (
    APPROVAL_CONFIRMATION_FALLBACK,
    REVIEW_MESSAGE_FALLBACK,
    SafetyPointMessageComposer,
)


class FakeCompletions:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = self.responses.pop(0)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=content)
                )
            ]
        )


class FakeClient:
    def __init__(self, responses):
        self.completions = FakeCompletions(responses)
        self.chat = SimpleNamespace(completions=self.completions)


class FakeAdapter:
    def __init__(self, responses):
        self.client = FakeClient(responses)
        self.model = "test-model"


def test_compose_safety_point_review_message_uses_rendered_prompt_context():
    adapter = FakeAdapter(
        [
            (
                "This is relevant to Test Bakery because chilled storage is "
                "part of the way the business works. You can approve it, ask "
                "a question, or say if you use a different method."
            )
        ]
    )
    composer = SafetyPointMessageComposer(llm_adapter=adapter)

    message = composer.compose_safety_point_review_message(
        business_context={
            "business_name": "Test Bakery",
            "user_first_name": "Jose",
            "business_type_label": "Bakery",
            "business_description": "Makes celebration cakes.",
            "screening_activities": ["uses chilled storage"],
            "relevant_fact_texts": [
                "The business records fridge temperatures every morning."
            ],
        },
        safety_point={
            "safety_point_id": "4.1.1.1",
            "section_name": "Chilling",
            "safe_method_name": "Chilled storage",
            "instruction": "Chilled food is kept cold.",
            "rationale": (
                "Keeping food cold slows the growth of harmful bacteria."
            ),
        },
    )

    assert "Test Bakery" in message

    call = adapter.client.completions.calls[0]
    assert call["model"] == "test-model"
    assert call["temperature"] == 0.4

    combined_prompt = "\n".join(
        item["content"] for item in call["messages"]
    )
    assert "Business name: Test Bakery" in combined_prompt
    assert "Business type: Bakery" in combined_prompt
    assert "uses chilled storage" in combined_prompt
    assert "records fridge temperatures every morning" in combined_prompt
    assert "Official rationale:" in combined_prompt
    assert "1-2 short sentences" in combined_prompt
    assert "no more than 70 words" in combined_prompt
    assert "complete, coherent review message" in combined_prompt
    assert "incomplete or cut-off message" in combined_prompt


def test_compose_safety_point_review_message_rejects_unsafe_content():
    adapter = FakeAdapter(
        [
            (
                "Chilled food is kept cold. This point is approved and shows "
                "the business is compliant."
            )
        ]
    )
    composer = SafetyPointMessageComposer(llm_adapter=adapter)

    message = composer.compose_safety_point_review_message(
        business_context={},
        safety_point={
            "instruction": "Chilled food is kept cold.",
            "section_name": "Chilling",
            "safe_method_name": "Chilled storage",
        },
    )

    assert message == REVIEW_MESSAGE_FALLBACK


def test_compose_safety_point_review_message_rejects_overlong_intro():
    overlong_message = " ".join(["context"] * 71) + "."

    adapter = FakeAdapter([overlong_message])
    composer = SafetyPointMessageComposer(llm_adapter=adapter)

    message = composer.compose_safety_point_review_message(
        business_context={},
        safety_point={
            "instruction": "Chilled food is kept cold.",
            "section_name": "Chilling",
            "safe_method_name": "Chilled storage",
        },
    )

    assert message == REVIEW_MESSAGE_FALLBACK


def test_compose_safety_point_review_message_falls_back_without_llm():
    composer = SafetyPointMessageComposer(
        llm_adapter=SimpleNamespace(client=None, model="test-model")
    )

    message = composer.compose_safety_point_review_message(
        business_context={},
        safety_point={
            "instruction": "Chilled food is kept cold.",
            "section_name": "Chilling",
            "safe_method_name": "Chilled storage",
        },
    )

    assert message == REVIEW_MESSAGE_FALLBACK


def test_compose_approval_confirmation_uses_prompt_and_rejects_bad_content():
    adapter = FakeAdapter(["This confirms broader compliance as approved."])
    composer = SafetyPointMessageComposer(llm_adapter=adapter)

    message = composer.compose_approval_confirmation(
        business_context={"business_name": "Test Bakery"},
        safety_point={
            "section_name": "Chilling",
            "safe_method_name": "Chilled storage",
        },
        approved_count=1,
        total_count=3,
    )

    assert message == APPROVAL_CONFIRMATION_FALLBACK

    call = adapter.client.completions.calls[0]
    assert call["temperature"] == 0.3
    combined_prompt = "\n".join(
        item["content"] for item in call["messages"]
    )
    assert "Business name: Test Bakery" in combined_prompt
    assert "Approved count: 1" in combined_prompt
    assert "Total count: 3" in combined_prompt


def test_extract_business_context_facts_returns_normalised_valid_facts_only():
    adapter = FakeAdapter(
        [
            json.dumps(
                {
                    "facts": [
                        {
                            "fact_type": "monitoring_or_recording_practice",
                            "fact_text": (
                                "The business checks fridge temperatures daily."
                            ),
                            "normalised_fact": "checks_fridge_temperatures_daily",
                            "confidence": 1.5,
                        },
                        {
                            "fact_type": "invalid_type",
                            "fact_text": "This should be ignored.",
                            "normalised_fact": "ignored",
                            "confidence": 0.8,
                        },
                    ]
                }
            )
        ]
    )
    composer = SafetyPointMessageComposer(llm_adapter=adapter)

    result = composer.extract_business_context_facts(
        user_message="We check fridge temperatures daily.",
        safety_point={
            "safety_point_id": "4.1.1.1",
            "section_name": "Chilling",
            "safe_method_name": "Chilled storage",
        },
    )

    assert result == {
        "facts": [
            {
                "fact_type": "monitoring_or_recording_practice",
                "fact_text": "The business checks fridge temperatures daily.",
                "normalised_fact": "checks_fridge_temperatures_daily",
                "confidence": 1.0,
            }
        ]
    }

    call = adapter.client.completions.calls[0]
    assert call["temperature"] == 0.1
    assert call["response_format"] == {"type": "json_object"}


def test_extract_business_context_facts_returns_empty_for_invalid_json():
    adapter = FakeAdapter(["not json"])
    composer = SafetyPointMessageComposer(llm_adapter=adapter)

    result = composer.extract_business_context_facts(
        user_message="hello",
        safety_point={},
    )

    assert result == {"facts": []}


def test_review_prompt_does_not_send_fixed_instruction_to_llm():
    adapter = FakeAdapter(["Review this safety point."])
    composer = SafetyPointMessageComposer(llm_adapter=adapter)

    composer.compose_safety_point_review_message(
        business_context={"business_name": "Test Bakery"},
        safety_point={
            "instruction": "Chilled food is kept cold.",
            "section_name": "Chilling",
            "safe_method_name": "Chilled storage",
            "rationale": "Keeping food cold slows bacterial growth.",
        },
    )

    call = adapter.client.chat.completions.calls[0]
    combined_prompt = "\n".join(
        item["content"] for item in call["messages"]
    )

    assert "Chilled food is kept cold." not in combined_prompt
    assert "Official rationale:" in combined_prompt
    assert "Keeping food cold slows bacterial growth." in combined_prompt
    assert "Do not reproduce, paraphrase, or rewrite" in combined_prompt


def test_review_prompt_does_not_infer_business_type_from_business_name():
    adapter = FakeAdapter(["Review this safety point."])
    composer = SafetyPointMessageComposer(llm_adapter=adapter)

    composer.compose_safety_point_review_message(
        business_context={
            "business_name": "Nathan's Cakes",
            "business_type_label": "",
        },
        safety_point={
            "instruction": "Chilled food is kept cold.",
            "section_name": "Chilling",
            "safe_method_name": "Chilled storage",
        },
    )

    call = adapter.client.chat.completions.calls[0]
    combined_prompt = "\n".join(
        item["content"] for item in call["messages"]
    )

    assert "Business name: Nathan's Cakes" in combined_prompt
    assert "Business type:" in combined_prompt
    assert "Business type: Bakery" not in combined_prompt
    assert "Do not guess the business type from the business name." in combined_prompt


def test_compose_safety_point_review_message_rejects_adviser_wording():
    adapter = FakeAdapter(
        [
            (
                "As your food safety advisor, I recommend reviewing this "
                "safety point before approval."
            )
        ]
    )
    composer = SafetyPointMessageComposer(llm_adapter=adapter)

    message = composer.compose_safety_point_review_message(
        business_context={},
        safety_point={
            "instruction": "Chilled food is kept cold.",
            "section_name": "Chilling",
            "safe_method_name": "Chilled storage",
        },
    )

    assert message == REVIEW_MESSAGE_FALLBACK


def test_compose_approval_confirmation_rejects_adviser_wording():
    adapter = FakeAdapter(
        ["As your food safety adviser, approval has been recorded."]
    )
    composer = SafetyPointMessageComposer(llm_adapter=adapter)

    message = composer.compose_approval_confirmation(
        business_context={"business_name": "Test Bakery"},
        safety_point={
            "section_name": "Chilling",
            "safe_method_name": "Chilled storage",
        },
        approved_count=1,
        total_count=3,
    )

    assert message == APPROVAL_CONFIRMATION_FALLBACK


def test_review_message_is_not_rejected_when_safe_and_different_method_are_unrelated():
    adapter = FakeAdapter(
        [
            (
                "Chilled food must be kept at a safe temperature to stop "
                "harmful bacteria growing. Let me know if you have any "
                "questions or if there is a different method you use."
            )
        ]
    )
    composer = SafetyPointMessageComposer(llm_adapter=adapter)

    message = composer.compose_safety_point_review_message(
        business_context={},
        safety_point={
            "instruction": "Chilled food is kept cold.",
            "section_name": "Chilling",
            "safe_method_name": "Chilled storage",
        },
    )

    assert message != REVIEW_MESSAGE_FALLBACK
    assert "safe temperature" in message


def test_review_message_is_still_rejected_when_endorsing_a_different_method_as_safe():
    adapter = FakeAdapter(
        [
            "If you use a different method, that is also considered safe."
        ]
    )
    composer = SafetyPointMessageComposer(llm_adapter=adapter)

    message = composer.compose_safety_point_review_message(
        business_context={},
        safety_point={
            "instruction": "Chilled food is kept cold.",
            "section_name": "Chilling",
            "safe_method_name": "Chilled storage",
        },
    )

    assert message == REVIEW_MESSAGE_FALLBACK


def test_filter_relevant_facts_keeps_only_the_indexes_the_llm_returns():
    adapter = FakeAdapter(
        [
            json.dumps({"relevant_fact_indexes": [1]}),
        ]
    )
    composer = SafetyPointMessageComposer(llm_adapter=adapter)

    facts = [
        {"fact_type": "food_type_or_ingredient", "fact_text": "Sells sourdough bread."},
        {"fact_type": "monitoring_or_recording_practice", "fact_text": "Checks fridge temperatures with a probe thermometer."},
    ]

    result = composer.filter_relevant_facts(
        facts=facts,
        instruction="Fridges are set at 5C or below and checked regularly.",
    )

    assert result == [facts[1]]

    call = adapter.client.completions.calls[0]
    assert call["temperature"] == 0.0
    assert call["response_format"] == {"type": "json_object"}
    combined_prompt = "\n".join(item["content"] for item in call["messages"])
    assert "Fridges are set at 5C or below" in combined_prompt
    assert "0: Sells sourdough bread." in combined_prompt
    assert "1: Checks fridge temperatures with a probe thermometer." in combined_prompt


def test_filter_relevant_facts_returns_empty_list_when_none_are_relevant():
    adapter = FakeAdapter(
        [
            json.dumps({"relevant_fact_indexes": []}),
        ]
    )
    composer = SafetyPointMessageComposer(llm_adapter=adapter)

    facts = [
        {"fact_type": "food_type_or_ingredient", "fact_text": "Sells sourdough bread."},
    ]

    result = composer.filter_relevant_facts(
        facts=facts,
        instruction="Fridges are set at 5C or below and checked regularly.",
    )

    assert result == []


def test_filter_relevant_facts_returns_empty_list_with_no_facts_or_instruction():
    composer = SafetyPointMessageComposer(llm_adapter=FakeAdapter([]))

    assert composer.filter_relevant_facts(facts=[], instruction="Some rule.") == []
    assert composer.filter_relevant_facts(facts=None, instruction="Some rule.") == []
    assert (
        composer.filter_relevant_facts(
            facts=[{"fact_type": "x", "fact_text": "y"}], instruction=""
        )
        == []
    )


def test_filter_relevant_facts_fails_closed_on_llm_error():
    class RaisingAdapter:
        def __init__(self):
            self.client = SimpleNamespace(
                chat=SimpleNamespace(
                    completions=SimpleNamespace(
                        create=lambda **kwargs: (_ for _ in ()).throw(
                            RuntimeError("network error")
                        )
                    )
                )
            )
            self.model = "test-model"

    composer = SafetyPointMessageComposer(llm_adapter=RaisingAdapter())

    result = composer.filter_relevant_facts(
        facts=[{"fact_type": "x", "fact_text": "y"}],
        instruction="Some rule.",
    )

    assert result == []


def test_filter_relevant_facts_fails_closed_on_invalid_json():
    adapter = FakeAdapter(["not valid json"])
    composer = SafetyPointMessageComposer(llm_adapter=adapter)

    result = composer.filter_relevant_facts(
        facts=[{"fact_type": "x", "fact_text": "y"}],
        instruction="Some rule.",
    )

    assert result == []


def test_filter_relevant_facts_ignores_out_of_range_indexes():
    adapter = FakeAdapter(
        [
            json.dumps({"relevant_fact_indexes": [0, 5, -1, "not a number"]}),
        ]
    )
    composer = SafetyPointMessageComposer(llm_adapter=adapter)

    facts = [{"fact_type": "x", "fact_text": "only fact"}]

    result = composer.filter_relevant_facts(
        facts=facts,
        instruction="Some rule.",
    )

    assert result == [facts[0]]
