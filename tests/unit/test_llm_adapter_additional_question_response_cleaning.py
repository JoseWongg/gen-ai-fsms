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


class FakeClient:
    def __init__(self, content):
        self.completions = FakeCompletions(content)
        self.chat = SimpleNamespace(completions=self.completions)


def _adapter_with_response(content):
    adapter = object.__new__(LLMAdapter)
    adapter.client = FakeClient(content)
    adapter.model = "test-model"
    return adapter


def test_clean_additional_question_response_returns_document_wording():
    adapter = _adapter_with_response(
        json.dumps(
            {
                "document_response_text": (
                    "A bain-marie and a heated display unit are used during busy services for hot holding."
                ),
                "reason": "Removed conversational filler.",
            }
        )
    )

    result = adapter.clean_additional_question_response(
        additional_question_text=(
            "What equipment does the business use for hot holding?"
        ),
        raw_response_text=(
            "We normally use the bain-marie, but there is also a heated "
            "display unit for busy services."
        ),
    )

    assert result == {
        "success": True,
        "document_response_text": (
            "A bain-marie and a heated display unit are used during busy services for hot holding."
        ),
        "reason": "Removed conversational filler.",
    }

    call = adapter.client.completions.calls[0]

    assert call["model"] == "test-model"
    assert call["temperature"] == 0.2
    assert call["response_format"] == {"type": "json_object"}

    system_message = call["messages"][0]["content"]
    user_message = call["messages"][1]["content"]

    assert "Do not add facts" in system_message
    assert "Do not infer facts" in system_message
    assert "supplied required additional question" in system_message
    assert "internal FSMS document" in system_message
    assert "Use impersonal or passive wording" in system_message
    assert "A bain-marie is used" not in system_message
    assert (
        "What equipment does the business use for hot holding?"
        in user_message
    )
    assert "hot holding" in user_message
    assert "bain-marie" in user_message


def test_clean_additional_question_response_rejects_null_wording():
    adapter = _adapter_with_response(
        json.dumps(
            {
                "document_response_text": None,
                "reason": "The response does not contain a usable answer.",
            }
        )
    )

    result = adapter.clean_additional_question_response(
        additional_question_text="Which dishes contain eggs?",
        raw_response_text="It depends.",
    )

    assert result == {
        "success": False,
        "document_response_text": None,
        "reason": "The response does not contain a usable answer.",
    }


def test_clean_additional_question_response_handles_invalid_json():
    adapter = _adapter_with_response("not valid json")

    result = adapter.clean_additional_question_response(
        additional_question_text="Which dishes contain eggs?",
        raw_response_text="Omelettes and cakes.",
    )

    assert result["success"] is False
    assert result["document_response_text"] is None
    assert result["reason"].startswith("API error:")