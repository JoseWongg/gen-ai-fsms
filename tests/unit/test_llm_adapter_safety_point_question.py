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
                        content="Use the fridge temperature checks to confirm control."
                    )
                )
            ]
        )


class FakeClient:
    def __init__(self):
        self.completions = FakeCompletions()
        self.chat = SimpleNamespace(completions=self.completions)


def test_answer_safety_point_question_uses_yaml_prompt_context():
    fake_client = FakeClient()

    adapter = object.__new__(LLMAdapter)
    adapter.client = fake_client
    adapter.model = "test-model"

    answer = adapter.answer_safety_point_question(
        safety_point_text="Original combined SFBB text.",
        safe_method_name="Chilled Storage",
        section_name="Chilling",
        condition_values={"chills_food": "true"},
        user_question="Do we need to check the fridge every day?",
        safety_point_instruction="Fridge temperatures are checked daily.",
        safety_point_rationale=(
            "Regular checks confirm chilled food is kept at a safe temperature."
        ),
        business_context={
            "business_name": "Test Bakery",
            "business_type_label": "Bakery",
            "business_description": "Makes celebration cakes.",
            "screening_activities": ["uses chilled storage"],
        },
        relevant_facts=[
            {
                "fact_type": "monitoring_or_recording_practice",
                "fact_text": "The business records fridge checks in a diary.",
            }
        ],
    )

    assert answer == "Use the fridge temperature checks to confirm control."

    call = fake_client.completions.calls[0]
    messages = call["messages"]
    combined_prompt = "\n".join(message["content"] for message in messages)

    assert call["model"] == "test-model"
    assert call["temperature"] == 0.5
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"

    assert "Respond as a food safety adviser" not in combined_prompt
    assert "Fixed safety point instruction: Fridge temperatures are checked daily." in combined_prompt
    assert (
        "Official rationale: Regular checks confirm chilled food is kept at a safe temperature."
        in combined_prompt
    )
    assert "Business name: Test Bakery" in combined_prompt
    assert "Business type: Bakery" in combined_prompt
    assert "uses chilled storage" in combined_prompt
    assert "The business records fridge checks in a diary." in combined_prompt
