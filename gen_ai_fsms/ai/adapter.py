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
                    "You classify the latest admin user's free-text response in a "
                    "food safety safety-point approval workflow.\n"
                    "Use the current safety point, pending additional question, and "
                    "conversation history as context, but classify only the latest "
                    "admin message.\n"
                    "You must return a JSON object with exactly these fields:\n"
                    "{\n"
                    '  "action": "approval" | "clarification_request" | '
                    '"different_method_declared" | "additional_answer" | "unclear",\n'
                    '  "reason": string,\n'
                    '  "assistant_message": string or null\n'
                    "}\n"
                    "Rules:\n"
                    "- Use action 'approval' when the user clearly confirms, accepts, "
                    "agrees to follow, or directly asks the system to approve, confirm, "
                    "record approval for, or proceed with the displayed SFBB safety point. "
                    "The user does not need to repeat the full safety point wording if "
                    "their approval intention is clear from the conversation. The workflow "
                    "will separately decide whether required additional questions must be "
                    "answered before approval can be recorded.\n"
                    "- Use action 'additional_answer' when there is a pending additional "
                    "question and the latest message appears to answer that active "
                    "additional question.\n"
                    "- Use action 'approval' when the latest message clearly confirms, "
                    "accepts, agrees to follow, or asks to proceed with the displayed "
                    "safety point, even if required additional questions may still need "
                    "to be asked before approval is recorded. The workflow will separately "
                    "decide whether final approval can be recorded or whether required "
                    "additional questions must be asked first.\n"
                    "- If there is a pending additional question and the latest message "
                    "does not answer that active additional question, does not ask a "
                    "clarification question, and does not clearly express approval intent, "
                    "use action 'unclear'. The assistant_message should ask the user to "
                    "answer the required additional question or clarify their intention.\n"
                    "- Example: if the assistant has just asked whether the business wants "
                    "to proceed with or approve the safety point, and the latest user "
                    "message is a clear affirmative response, use action 'approval'.\n"
                    "- Example: if the assistant has just asked a required additional "
                    "question such as which dishes contain pork, and the latest user "
                    "message does not answer that question, use action 'unclear'.\n"
                    "- Use action 'clarification_request' when the user asks a question, "
                    "asks for explanation, asks for advice, or makes a relevant operational "
                    "or implementation statement that needs guidance before approval can "
                    "be confirmed. Examples include statements about training employees, "
                    "changing procedures, checking labels, correcting current practice, "
                    "or asking what evidence would be acceptable.\n"
                    "- Treat implementation comments such as 'we need to train employees "
                    "to follow this rule' as 'clarification_request', not as approval and "
                    "not as different_method_declared.\n"
                    "- Use action 'different_method_declared' only when the user clearly "
                    "states that the business will not follow the displayed SFBB safety "
                    "point and will instead use a different method. Do not use it for "
                    "comments about actions needed to comply with the displayed safety "
                    "point.\n"
                    "- Use action 'unclear' only when the user's intention is too vague "
                    "or not relevant enough to route safely.\n"
                    "- Do not assess whether an alternative method is safe, compliant, "
                    "or equivalent.\n"
                    "- Do not approve any safety point.\n"
                    "- For 'different_method_declared', assistant_message should explain "
                    "that this workflow can record approval only if the business follows "
                    "the displayed SFBB safety point, and that the safety point will remain "
                    "unapproved until the business confirms it will follow a compliant "
                    "approach.\n"
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
                    "Current workflow context:\n"
                    f"Safety point:\n{safety_point_text}\n\n"
                    f"Pending additional question key: {pending_question_key}\n"
                    f"Pending additional question text: {pending_question_text}\n\n"
                    "The conversation history, if provided, follows this context. "
                    "The latest admin message to classify will be provided after "
                    "the history."
                ),
            },
        ]

        if conversation_history:
            messages.extend(conversation_history)

        messages.append(
            {
                "role": "user",
                "content": f"Latest admin message to classify:\n{user_message}",
            }
        )

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
            f"User message: {user_question}\n\n"
            "Respond as a food safety adviser for this safety point. "
            "Answer concisely and accurately based on the guidance above. "
            "If the user makes a relevant operational or implementation statement "
            "rather than asking a direct question, explain the practical implication "
            "of that statement. "
            "If the statement suggests an action needed to follow the safety point, "
            "state that action clearly and ask whether the user wants to approve the "
            "safety point on the basis that the business will follow it. "
            "When you ask this approval question, put it in a separate final paragraph "
            "after a blank line. "
            "Do not record approval yourself. "
            "Do not formally assess alternative methods as safe, compliant, or equivalent."
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

    def answer_additional_question_clarification(
        self,
        safety_point_text: str,
        safe_method_name: str,
        section_name: str,
        condition_values: Dict[str, str],
        additional_question_text: str,
        user_question: str,
    ) -> str:
        """Answer a clarification question about a required additional question."""
        if not self.client:
            return "LLM not configured. Please check OPENAI_API_KEY."

        true_conditions = [k for k, v in condition_values.items() if v == "true"]
        context = (
            f"Section: {section_name}\n"
            f"Safe Method: {safe_method_name}\n"
            f"Safety Point: {safety_point_text}\n\n"
            f"Required additional question: {additional_question_text}\n\n"
            f"Restaurant context (true conditions): {', '.join(true_conditions)}"
        )

        prompt = (
            f"{context}\n\n"
            f"User message: {user_question}\n\n"
            "Respond as a food safety adviser, but focus only on helping the user "
            "answer the required additional question. "
            "If the user asks to repeat options, repeat the options stated in the "
            "required additional question and only add safety-point context if it is "
            "directly necessary. "
            "Do not ask whether the user wants to approve the safety point, because "
            "approval has already been attempted and is waiting for this required "
            "additional answer. "
            "End by asking the user to answer the required additional question by "
            "stating what the business does."
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            content = response.choices[0].message.content
            if content is None:
                return "Sorry, I could not answer your question at this time."
            return content.strip()
        except Exception as e:
            logger.error("LLM error in answer_additional_question_clarification: %s", e)
            return "Sorry, I couldn't answer your question at this time."



_adapter = None


def get_llm_adapter() -> LLMAdapter:
    """Return a singleton instance of LLMAdapter."""
    global _adapter
    if _adapter is None:
        _adapter = LLMAdapter()
    return _adapter
