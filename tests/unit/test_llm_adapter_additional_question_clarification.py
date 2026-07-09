from types import SimpleNamespace

from gen_ai_fsms.ai.adapter import LLMAdapter


class FakeCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="Use the option that matches what the business does."
                    )
                )
            ]
        )


class FakeClient:
    def __init__(self):
        self.completions = FakeCompletions()
        self.chat = SimpleNamespace(completions=self.completions)


def test_answer_additional_question_clarification_uses_yaml_prompt():
    fake_client = FakeClient()

    adapter = object.__new__(LLMAdapter)
    adapter.client = fake_client
    adapter.model = "test-model"

    answer = adapter.answer_additional_question_clarification(
        safety_point_text="Food should be kept chilled.",
        safe_method_name="Chilled storage",
        section_name="Chilling",
        condition_values={
            "handles_raw_fish": "true",
            "hot_holds_food": "false",
        },
        additional_question_text="Where do you keep chilled food?",
        user_question="Can you repeat the question?",
    )

    assert answer == "Use the option that matches what the business does."

    call = fake_client.completions.calls[0]
    assert call["model"] == "test-model"
    assert call["temperature"] == 0.3

    system_message = call["messages"][0]["content"]
    user_message = call["messages"][1]["content"]

    assert "required additional question" in system_message
    assert "Do not call the user" in system_message
    assert "Respond as a food safety adviser" not in system_message
    assert "You are a food safety adviser" not in system_message
    assert "You are a food safety advisor" not in system_message

    assert "Can you repeat the question?" in user_message
    assert "Where do you keep chilled food?" in user_message
    assert "Food should be kept chilled." in user_message
    assert "handles_raw_fish" in user_message
    assert "hot_holds_food" not in user_message
