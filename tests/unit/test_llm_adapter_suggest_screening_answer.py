import json
from types import SimpleNamespace

from gen_ai_fsms.ai.adapter import LLMAdapter


class FakeCompletions:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.content)
                )
            ]
        )


class RaisingCompletions:
    def create(self, **kwargs):
        raise RuntimeError("network error")


class FakeClient:
    def __init__(self, completions):
        self.completions = completions
        self.chat = SimpleNamespace(completions=self.completions)


def make_adapter(client=None):
    adapter = object.__new__(LLMAdapter)
    adapter.client = client
    adapter.model = "test-model"
    return adapter


def test_suggest_screening_answer_returns_true_when_llm_says_true():
    completions = FakeCompletions(json.dumps({"value": "true"}))
    adapter = make_adapter(client=FakeClient(completions))

    result = adapter.suggest_screening_answer(
        business_description="We cook rice and fish every day.",
        question_text="Do you cook rice?",
    )

    assert result == "true"

    call = completions.calls[0]
    assert call["model"] == "test-model"
    assert call["temperature"] == 0.0
    assert call["response_format"] == {"type": "json_object"}

    combined_prompt = "\n".join(
        item["content"] for item in call["messages"]
    )
    assert "We cook rice and fish every day." in combined_prompt
    assert "Do you cook rice?" in combined_prompt
    assert "only a starting suggestion" in combined_prompt


def test_suggest_screening_answer_returns_false_when_llm_says_false():
    completions = FakeCompletions(json.dumps({"value": "false"}))
    adapter = make_adapter(client=FakeClient(completions))

    result = adapter.suggest_screening_answer(
        business_description="We only sell packaged snacks.",
        question_text="Do you cook rice?",
    )

    assert result == "false"


def test_suggest_screening_answer_returns_false_with_no_client():
    adapter = make_adapter(client=None)

    result = adapter.suggest_screening_answer(
        business_description="We cook rice every day.",
        question_text="Do you cook rice?",
    )

    assert result == "false"


def test_suggest_screening_answer_returns_false_with_empty_description():
    completions = FakeCompletions(json.dumps({"value": "true"}))
    adapter = make_adapter(client=FakeClient(completions))

    result = adapter.suggest_screening_answer(
        business_description="   ",
        question_text="Do you cook rice?",
    )

    assert result == "false"
    assert completions.calls == []


def test_suggest_screening_answer_fails_closed_on_invalid_json():
    completions = FakeCompletions("not valid json")
    adapter = make_adapter(client=FakeClient(completions))

    result = adapter.suggest_screening_answer(
        business_description="We cook rice every day.",
        question_text="Do you cook rice?",
    )

    assert result == "false"


def test_suggest_screening_answer_fails_closed_on_llm_error():
    adapter = make_adapter(client=FakeClient(RaisingCompletions()))

    result = adapter.suggest_screening_answer(
        business_description="We cook rice every day.",
        question_text="Do you cook rice?",
    )

    assert result == "false"


def test_suggest_screening_answer_fails_closed_on_unexpected_value():
    completions = FakeCompletions(json.dumps({"value": "maybe"}))
    adapter = make_adapter(client=FakeClient(completions))

    result = adapter.suggest_screening_answer(
        business_description="We cook rice every day.",
        question_text="Do you cook rice?",
    )

    assert result == "false"
