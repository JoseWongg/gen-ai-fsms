import pytest

from gen_ai_fsms.prompts import render_prompt
from gen_ai_fsms.prompts.renderer import PromptRenderError


def test_safety_point_review_message_renders_with_business_context():
    prompt = render_prompt(
        "safety_point_review_message",
        {
            "business_name": "Test Bakery",
            "user_first_name": "Jose",
            "business_type_label": "Bakery",
            "business_description": "Celebration cakes and cupcakes",
            "screening_activities": ["chills food", "cooks food"],
            "relevant_facts": [
                "The business checks fridge temperatures every day."
            ],
            "section_name": "Chilling",
            "safe_method_name": "Chilled storage and display",
            "rationale": (
                "Keeping food cold slows the growth of harmful bacteria."
            ),
        },
    )

    assert prompt["system"]
    assert prompt["user"]
    assert "Test Bakery" in prompt["user"]
    assert "Celebration cakes and cupcakes" in prompt["user"]
    assert "before the fixed safety point instruction" in prompt["user"]
    assert "no more than 70 words" in prompt["user"]
    assert "complete, coherent review message" in prompt["user"]


def test_prompt_renderer_allows_missing_optional_context():
    prompt = render_prompt("approval_confirmation", {})

    assert prompt["system"]
    assert prompt["user"]
    assert "the business" in prompt["user"]


def test_prompt_renderer_rejects_unknown_prompt_key():
    with pytest.raises(PromptRenderError, match="Unknown prompt key"):
        render_prompt("not_a_prompt", {})


def test_fact_extraction_prompt_renders_allowed_categories_and_message():
    prompt = render_prompt(
        "fact_extraction",
        {
            "user_message": (
                "We check fridge temperatures every morning and write them down."
            ),
            "safety_point_id": "4.1.1.1",
            "section_name": "Chilling",
            "safe_method_name": "Chilled storage",
        },
    )

    assert "monitoring_or_recording_practice" in prompt["system"]
    assert "strict JSON only" in prompt["system"]
    assert "every morning" in prompt["user"]
