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
                    "- If the user's answer directly answers the original question, use action 'clear'.\n"
                    "- The question asks whether an activity occurs at all, not how frequently it occurs. "
                    "If the answer states that the activity occurs sometimes, occasionally, only on certain days, "
                    "only in certain circumstances, or for some foods, use action 'clear' with value 'true'.\n"
                    "- Examples that must be interpreted as action 'clear' with value 'true': "
                    "'only on Tuesdays', 'sometimes', 'occasionally', 'only when we have leftovers', "
                    "'only during busy periods', 'only for some dishes'.\n"
                    "- Examples that must be interpreted as action 'clear' with value 'false': "
                    "'not anymore', 'we used to but no longer do', 'never', 'we do not do that'.\n"
                    "- If the user's answer is a clear affirmative (e.g., 'yes', 'yeah', 'correct', 'that's right') to a clarification question, treat it as 'clear' for the original question.\n"
                    "- If the user's answer is a clear negative (e.g., 'no', 'nope', 'incorrect') to a clarification question, treat it as 'clear' with value 'false'.\n"
                    "- If the answer is unclear or ambiguous, use action 'ambiguous' and provide a short clarification question.\n"
                    "- If the answer is completely unrelated to the question or clarification, use action 'unrelated'.\n"
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
    


    def interpret_safety_point_response(
        self,
        safety_point_text: str,
        user_message: str,
        pending_additional_question: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Classify an admin's free-text response to a safety point.

        This method only decides the workflow route. It must not approve safety
        points or assess whether an alternative method is safe or compliant.
        """
        if not self.client:
            return {
                "action": "unclear",
                "reason": "LLM not configured",
                "assistant_message": (
                    "I could not classify your response. Please clarify whether you "
                    "are approving the displayed safety point, asking a question, "
                    "answering the required additional question, or stating that "
                    "your business follows a different method."
                ),
            }

        pending_question_text = None
        pending_question_key = None

        if pending_additional_question:
            pending_question_text = pending_additional_question.get("question_text")
            pending_question_key = pending_additional_question.get("question_key")

        messages = [
            {
                "role": "system",
                "content": (
                    "You classify an admin user's free-text response in a food safety "
                    "safety-point approval workflow.\n"
                    "You must return a JSON object with exactly these fields:\n"
                    "{\n"
                    '  "action": "approval" | "clarification_request" | '
                    '"different_method_declared" | "additional_answer" | "unclear",\n'
                    '  "reason": string,\n'
                    '  "assistant_message": string or null\n'
                    "}\n"
                    "Rules:\n"
                    "- Use action 'approval' only when the user clearly confirms that "
                    "the business follows, accepts, or will use the displayed SFBB "
                    "safety point.\n"
                    "- Use action 'clarification_request' when the user asks a question "
                    "or shows they need an explanation about the safety point.\n"
                    "- Use action 'different_method_declared' when the user says or "
                    "implies that the business does something differently from the "
                    "displayed safety point.\n"
                    "- Use action 'additional_answer' when there is a pending additional "
                    "question and the user appears to be answering that question.\n"
                    "- Use action 'unclear' when the user's intention is not clear.\n"
                    "- Do not assess whether an alternative method is safe, compliant, "
                    "or equivalent.\n"
                    "- Do not approve any safety point.\n"
                    "- For 'different_method_declared', assistant_message should explain "
                    "that alternative-method assessment is not available in this version "
                    "and that approval can only be recorded if the business follows the "
                    "displayed SFBB safety point.\n"
                    "- For 'unclear', assistant_message should ask the user to clarify "
                    "whether they are approving the safety point, asking a question, "
                    "answering a required additional question, or stating that the "
                    "business uses a different method.\n"
                    "- For other actions, assistant_message should be null.\n"
                    "Return only valid JSON."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Safety point:\n{safety_point_text}\n\n"
                    f"Pending additional question key: {pending_question_key}\n"
                    f"Pending additional question text: {pending_question_text}\n\n"
                    f"Admin message:\n{user_message}"
                ),
            },
        ]

        if conversation_history:
            messages.extend(conversation_history)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content

            if content is None:
                return {
                    "action": "unclear",
                    "reason": "Empty response from LLM",
                    "assistant_message": (
                        "I could not classify your response. Please clarify whether you "
                        "are approving the displayed safety point, asking a question, "
                        "answering the required additional question, or stating that "
                        "your business follows a different method."
                    ),
                }

            result = json.loads(content)
            action = result.get("action")

            if action not in (
                "approval",
                "clarification_request",
                "different_method_declared",
                "additional_answer",
                "unclear",
            ):
                return {
                    "action": "unclear",
                    "reason": "LLM returned an unsupported action",
                    "assistant_message": (
                        "I could not classify your response. Please clarify whether you "
                        "are approving the displayed safety point, asking a question, "
                        "answering the required additional question, or stating that "
                        "your business follows a different method."
                    ),
                }

            return {
                "action": action,
                "reason": result.get("reason", ""),
                "assistant_message": result.get("assistant_message"),
            }

        except Exception as e:
            logger.error("LLM error in interpret_safety_point_response: %s", e)
            return {
                "action": "unclear",
                "reason": f"API error: {e}",
                "assistant_message": (
                    "I could not classify your response. Please clarify whether you "
                    "are approving the displayed safety point, asking a question, "
                    "answering the required additional question, or stating that "
                    "your business follows a different method."
                ),
            }







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
