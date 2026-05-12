import os
import pytest
from dotenv import load_dotenv
from gen_ai_fsms.ai.adapter import get_llm_adapter

# Skip this test unless RUN_LLM_TESTS=true is set
RUN_LLM_TESTS = os.getenv("RUN_LLM_TESTS", "").lower() == "true"

@pytest.mark.skipif(not RUN_LLM_TESTS, reason="Set RUN_LLM_TESTS=true to run OpenAI integration tests")
def test_llm_adapter():
    load_dotenv()
    adapter = get_llm_adapter()
    
    # Test interpretation
    question = "Do you keep any food chilled in fridges or chilled display units?"
    answer = "Yes, we have a walk-in fridge and a display chiller."
    result = adapter.interpret_screening_answer(question, answer)
    assert result["action"] == "clear"
    assert result["value"] == "true"
    
    # Test clarification
    clarification = adapter.answer_screening_clarification(question, "What does 'display chilled food' mean?")
    assert isinstance(clarification, str)
    assert len(clarification) > 10
