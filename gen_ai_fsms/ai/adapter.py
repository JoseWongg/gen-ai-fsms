import os
import json
import logging
from typing import Dict, Any, Optional, List
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class LLMAdapter:
    """Central adapter for all LLM interactions."""
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("OPENAI_API_KEY not set. LLM features will not work.")
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None
        self.model = "gpt-4o"
    
    def interpret_screening_answer(
        self,
        question: str,
        answer: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Interpret a free‑text screening answer.
        Returns a dict with action, value, clarification_question, reason.
        """
        if not self.client:
            return {
                "action": "clear",
                "value": "unknown",
                "clarification_question": None,
                "reason": "LLM not configured"
            }
        
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an assistant that interprets answers to food safety screening questions.\n"
                    "You must return a JSON object with exactly these fields:\n"
                    '{\n'
                    '  "action": "clear" | "ambiguous" | "unrelated",\n'
                    '  "value": "true" | "false" | "unknown" | "not_asked" | null,\n'
                    '  "clarification_question": string or null,\n'
                    '  "reason": string\n'
                    '}\n'
                    "Rules:\n"
                    "- clear: answer directly answers -> map to true/false/unknown/not_asked.\n"
                    "- ambiguous: answer unclear -> provide a clarification_question.\n"
                    "- unrelated: answer off-topic -> politely ask to answer the question.\n"
                    "Return only valid JSON."
                )
            },
            {
                "role": "user",
                "content": f"Question: {question}\nUser answer: {answer}"
            }
        ]
        if conversation_history:
            messages.extend(conversation_history)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            if content is None:
                return {
                    "action": "unrelated",
                    "value": None,
                    "clarification_question": "Sorry, I could not process your answer. Please try again.",
                    "reason": "Empty response from LLM"
                }
            return json.loads(content)
        except Exception as e:
            logger.error("LLM error in interpret_screening_answer: %s", e)
            return {
                "action": "unrelated",
                "value": None,
                "clarification_question": "Could you please rephrase your answer?",
                "reason": f"API error: {e}"
            }
    
    def answer_screening_clarification(self, question: str, user_question: str) -> str:
        """Explain the meaning of a screening question."""
        if not self.client:
            return "LLM not configured. Please check OPENAI_API_KEY."
        prompt = (
            f"User asks: '{user_question}' about the screening question: '{question}'. "
            "Provide a helpful, concise explanation."
        )
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5
            )
            content = response.choices[0].message.content
            if content is None:
                return "Sorry, I could not generate an explanation at this time."
            return content.strip()
        except Exception as e:
            logger.error("LLM error in answer_screening_clarification: %s", e)
            return "Sorry, I couldn't process your request at this time."
    
    def answer_safety_point_question(
        self,
        safety_point_text: str,
        safe_method_name: str,
        section_name: str,
        condition_values: Dict[str, str],
        user_question: str
    ) -> str:
        """Answer an admin's question about a safety point."""
        if not self.client:
            return "LLM not configured. Please check OPENAI_API_KEY."
        true_conditions = [k for k, v in condition_values.items() if v == "true"]
        context = (
            f"Section: {section_name}\n"
            f"Safe Method: {safe_method_name}\n"
            f"Safety Point: {safety_point_text}\n\n"
            f"Restaurant context (true conditions): {', '.join(true_conditions)}"
        )
        prompt = (
            f"{context}\n\n"
            f"User question: {user_question}\n\n"
            "Answer concisely and accurately based on the guidance above."
        )
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5
            )
            content = response.choices[0].message.content
            if content is None:
                return "Sorry, I could not answer your question at this time."
            return content.strip()
        except Exception as e:
            logger.error("LLM error in answer_safety_point_question: %s", e)
            return "Sorry, I couldn't answer your question at this time."


_adapter = None


def get_llm_adapter() -> LLMAdapter:
    """Return a singleton instance of LLMAdapter."""
    global _adapter
    if _adapter is None:
        _adapter = LLMAdapter()
    return _adapter
