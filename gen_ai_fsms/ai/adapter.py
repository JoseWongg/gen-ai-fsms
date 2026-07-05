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


    def extract_chilling_equipment_names(
        self,
        user_message: str,
    ) -> Dict[str, Any]:
        """
        Extract chilling equipment names from the user's response.

        This method is used only for safety point 4.1.1.3.
        It does not collect equipment details.
        """
        fallback_message = (
            "I need the names of the chilling equipment items used by the "
            "business, such as Fridge 1, Freezer 1, or Chilled Display Unit 1. "
            "Please list the equipment names only."
        )

        if not self.client:
            return {
                "has_usable_equipment_names": False,
                "no_chilling_equipment_declared": False,
                "equipment_names": [],
                "reason": "LLM not configured",
                "assistant_message": fallback_message,
            }

        messages = [
            {
                "role": "system",
                "content": (
                    "You extract chilling equipment names for a food safety "
                    "workflow.\n"
                    "Return only a JSON object with exactly these fields:\n"
                    "{\n"
                    '  "has_usable_equipment_names": boolean,\n'
                    '  "no_chilling_equipment_declared": boolean,\n'
                    '  "equipment_names": array of strings,\n'
                    '  "reason": string,\n'
                    '  "assistant_message": string or null\n'
                    "}\n"
                    "Rules:\n"
                    "- The expected input is a list of chilling equipment names.\n"
                    "- Chilling equipment includes fridges, freezers, chilled "
                    "display units, chilled cabinets, walk-in fridges, walk-in "
                    "freezers, and similar cold-holding equipment.\n"
                    "- Extract only names explicitly stated or clearly implied by "
                    "the user, such as Fridge 1, Freezer 1, Chilled Display Unit 1.\n"
                    "- Do not invent equipment names.\n"
                    "- If the user clearly states that the business has no chilling "
                    "equipment, set no_chilling_equipment_declared to true and "
                    "equipment_names to an empty array.\n"
                    "- If the response is unrelated, nonsensical, or does not contain "
                    "usable equipment names, set has_usable_equipment_names to false, "
                    "equipment_names to an empty array, and assistant_message to a "
                    "short request for equipment names only.\n"
                    "- If one or more usable equipment names are present, set "
                    "has_usable_equipment_names to true and assistant_message to null.\n"
                    "- Remove duplicates while preserving the user's wording."
                ),
            },
            {
                "role": "user",
                "content": f"User response:\n{user_message}",
            },
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content

            if content is None:
                return {
                    "has_usable_equipment_names": False,
                    "no_chilling_equipment_declared": False,
                    "equipment_names": [],
                    "reason": "Empty response from LLM",
                    "assistant_message": fallback_message,
                }

            result = json.loads(content)
            raw_names = result.get("equipment_names") or []
            equipment_names = []
            seen_names = set()

            for name in raw_names:
                if not isinstance(name, str):
                    continue

                cleaned_name = name.strip()

                if not cleaned_name:
                    continue

                lookup_key = cleaned_name.lower()

                if lookup_key not in seen_names:
                    equipment_names.append(cleaned_name)
                    seen_names.add(lookup_key)

            no_chilling_equipment_declared = bool(
                result.get("no_chilling_equipment_declared")
            )
            has_usable_equipment_names = (
                bool(equipment_names)
                and not no_chilling_equipment_declared
            )

            return {
                "has_usable_equipment_names": has_usable_equipment_names,
                "no_chilling_equipment_declared": no_chilling_equipment_declared,
                "equipment_names": equipment_names,
                "reason": result.get("reason", ""),
                "assistant_message": (
                    result.get("assistant_message")
                    if not has_usable_equipment_names
                    and not no_chilling_equipment_declared
                    else None
                ),
            }

        except Exception as e:
            logger.error("LLM error in extract_chilling_equipment_names: %s", e)
            return {
                "has_usable_equipment_names": False,
                "no_chilling_equipment_declared": False,
                "equipment_names": [],
                "reason": f"API error: {e}",
                "assistant_message": fallback_message,
            }

    def interpret_chilling_equipment_name_confirmation(
        self,
        captured_equipment_names: List[str],
        user_message: str,
    ) -> Dict[str, Any]:
        """
        Interpret whether the user confirms the captured equipment-name list.

        If the user says the list is wrong and provides a corrected full list,
        this method extracts that corrected list.
        """
        fallback_message = (
            "Please confirm whether the captured chilling equipment list is "
            "correct. If it is not correct, provide the full corrected list."
        )

        if not self.client:
            return {
                "confirmed": False,
                "corrected_equipment_names": [],
                "reason": "LLM not configured",
                "assistant_message": fallback_message,
            }

        messages = [
            {
                "role": "system",
                "content": (
                    "You interpret whether a user confirms a captured list of "
                    "chilling equipment names.\n"
                    "Return only a JSON object with exactly these fields:\n"
                    "{\n"
                    '  "confirmed": boolean,\n'
                    '  "corrected_equipment_names": array of strings,\n'
                    '  "reason": string,\n'
                    '  "assistant_message": string or null\n'
                    "}\n"
                    "Rules:\n"
                    "- If the user clearly confirms that the captured list is "
                    "correct, set confirmed to true.\n"
                    "- If the user says the list is wrong and provides a full "
                    "corrected list, set confirmed to false and extract the corrected "
                    "equipment names.\n"
                    "- If the user says the list is wrong but does not provide a "
                    "corrected list, set confirmed to false and return an empty "
                    "corrected_equipment_names array.\n"
                    "- Do not invent equipment names.\n"
                    "- Remove duplicates while preserving the user's wording.\n"
                    "- Use assistant_message only when the user has not confirmed "
                    "and has not provided a usable corrected list."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Captured equipment names:\n"
                    f"{json.dumps(captured_equipment_names)}\n\n"
                    f"User response:\n{user_message}"
                ),
            },
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content

            if content is None:
                return {
                    "confirmed": False,
                    "corrected_equipment_names": [],
                    "reason": "Empty response from LLM",
                    "assistant_message": fallback_message,
                }

            result = json.loads(content)
            raw_names = result.get("corrected_equipment_names") or []
            corrected_names = []
            seen_names = set()

            for name in raw_names:
                if not isinstance(name, str):
                    continue

                cleaned_name = name.strip()

                if not cleaned_name:
                    continue

                lookup_key = cleaned_name.lower()

                if lookup_key not in seen_names:
                    corrected_names.append(cleaned_name)
                    seen_names.add(lookup_key)

            confirmed = bool(result.get("confirmed"))

            return {
                "confirmed": confirmed,
                "corrected_equipment_names": corrected_names,
                "reason": result.get("reason", ""),
                "assistant_message": (
                    result.get("assistant_message")
                    if not confirmed and not corrected_names
                    else None
                ),
            }

        except Exception as e:
            logger.error(
                "LLM error in interpret_chilling_equipment_name_confirmation: %s",
                e,
            )
            return {
                "confirmed": False,
                "corrected_equipment_names": [],
                "reason": f"API error: {e}",
                "assistant_message": fallback_message,
            }

    def interpret_chilling_equipment_details(
        self,
        equipment_name: str,
        user_message: str,
        existing_details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Interpret the required details for one chilling equipment item.
        """
        fallback_message = (
            f"For {equipment_name}, please indicate whether it is a fridge or "
            "freezer, whether it is used for storage or display, and whether its "
            "temperature is checked using a permanent digital/dial display or a "
            "food probe thermometer between packs of chilled food."
        )

        if not self.client:
            return {
                "equipment_type": None,
                "equipment_use": None,
                "temperature_check_method": None,
                "missing_fields": [
                    "equipment_type",
                    "equipment_use",
                    "temperature_check_method",
                ],
                "invalid_fields": [],
                "is_complete": False,
                "reason": "LLM not configured",
                "assistant_message": fallback_message,
            }

        details_context = existing_details or {}

        messages = [
            {
                "role": "system",
                "content": (
                    "You extract required details for one chilling equipment item "
                    "in a food safety workflow.\n"
                    "Return only a JSON object with exactly these fields:\n"
                    "{\n"
                    '  "equipment_type": "fridge" | "freezer" | null,\n'
                    '  "equipment_use": "storage" | "display" | null,\n'
                    '  "temperature_check_method": '
                    '"digital_or_dial_display" | "probe_between_packs" | null,\n'
                    '  "missing_fields": array of strings,\n'
                    '  "invalid_fields": array of strings,\n'
                    '  "is_complete": boolean,\n'
                    '  "reason": string,\n'
                    '  "assistant_message": string or null\n'
                    "}\n"
                    "Rules:\n"
                    "- Extract details only for the named equipment item.\n"
                    "- Use existing details if already provided and not contradicted.\n"
                    "- equipment_type must be fridge or freezer.\n"
                    "- equipment_use must be storage or display.\n"
                    "- The word display in digital display or dial display is not "
                    "equipment_use. It is part of the temperature checking method.\n"
                    "- Set equipment_use to display only when the user clearly says "
                    "the equipment is used to display food, show food to customers, "
                    "or is a chilled display cabinet/unit/counter.\n"
                    "- If the user says the equipment is used for storage, "
                    "equipment_use must be storage even if the temperature is checked "
                    "with a digital display.\n"
                    "- temperature_check_method must be one of exactly two values.\n"
                    "- Map permanent digital display, dial display, fridge thermometer, "
                    "freezer thermometer, or a thermometer/display kept inside the unit "
                    "to digital_or_dial_display.\n"
                    "- Map checking between packs of chilled food with a food probe "
                    "thermometer to probe_between_packs.\n"
                    "- Do not accept touching food, guessing, smelling, general daily "
                    "checking, or unspecified visual checking as a valid temperature "
                    "check method.\n"
                    "- If a required field is missing, include it in missing_fields.\n"
                    "- If a required field is invalid, include it in invalid_fields.\n"
                    "- is_complete must be true only when all three required fields "
                    "are valid.\n"
                    "- assistant_message should ask only for missing or invalid fields."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Equipment name:\n{equipment_name}\n\n"
                    "Existing details, if any:\n"
                    f"{json.dumps(details_context)}\n\n"
                    f"User response:\n{user_message}"
                ),
            },
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content

            if content is None:
                return {
                    "equipment_type": details_context.get("equipment_type"),
                    "equipment_use": details_context.get("equipment_use"),
                    "temperature_check_method": details_context.get(
                        "temperature_check_method"
                    ),
                    "missing_fields": [
                        "equipment_type",
                        "equipment_use",
                        "temperature_check_method",
                    ],
                    "invalid_fields": [],
                    "is_complete": False,
                    "reason": "Empty response from LLM",
                    "assistant_message": fallback_message,
                }

            result = json.loads(content)

            valid_equipment_types = {"fridge", "freezer"}
            valid_equipment_uses = {"storage", "display"}
            valid_methods = {
                "digital_or_dial_display",
                "probe_between_packs",
            }

            equipment_type = result.get("equipment_type")
            equipment_use = result.get("equipment_use")
            temperature_check_method = result.get("temperature_check_method")

            if equipment_type not in valid_equipment_types:
                equipment_type = None

            if equipment_use not in valid_equipment_uses:
                equipment_use = None

            if temperature_check_method not in valid_methods:
                temperature_check_method = None

            missing_fields = []

            if equipment_type is None:
                missing_fields.append("equipment_type")

            if equipment_use is None:
                missing_fields.append("equipment_use")

            if temperature_check_method is None:
                missing_fields.append("temperature_check_method")

            raw_invalid_fields = result.get("invalid_fields") or []
            invalid_fields = [
                field
                for field in raw_invalid_fields
                if field in {
                    "equipment_type",
                    "equipment_use",
                    "temperature_check_method",
                }
            ]

            is_complete = (
                equipment_type is not None
                and equipment_use is not None
                and temperature_check_method is not None
                and not invalid_fields
            )

            return {
                "equipment_type": equipment_type,
                "equipment_use": equipment_use,
                "temperature_check_method": temperature_check_method,
                "missing_fields": missing_fields,
                "invalid_fields": invalid_fields,
                "is_complete": is_complete,
                "reason": result.get("reason", ""),
                "assistant_message": (
                    result.get("assistant_message")
                    if not is_complete
                    else None
                ),
            }

        except Exception as e:
            logger.error("LLM error in interpret_chilling_equipment_details: %s", e)
            return {
                "equipment_type": details_context.get("equipment_type"),
                "equipment_use": details_context.get("equipment_use"),
                "temperature_check_method": details_context.get(
                    "temperature_check_method"
                ),
                "missing_fields": [
                    "equipment_type",
                    "equipment_use",
                    "temperature_check_method",
                ],
                "invalid_fields": [],
                "is_complete": False,
                "reason": f"API error: {e}",
                "assistant_message": fallback_message,
            }









    """
    This method extracts corrective-action facts from a manager's narrative about a fridge-temperature incident.
    It does not decide compliance and does not invent missing facts. It returns a dictionary of extracted facts,
    with null values for any facts that are missing or unclear. The 'reason' field explains why any facts are missing or unclear.
    """
    def extract_fridge_corrective_action_facts(
        self,
        user_message: str,
        existing_state: Optional[Dict[str, Any]] = None,
        current_issues: Optional[List[Dict[str, Any]]] = None,
        last_assistant_message: Optional[str] = None,
        recent_conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Extract corrective-action facts from a user's narrative.

        This method extracts facts only. It must not decide compliance and must
        not invent missing facts.
        """

        empty_facts = {
            "food_probed": None,
            "fish_present": None,
            "non_fish_food_present": None,
            "food_temperature_c": None,
            "out_of_range_duration": None,
            "fish_decision": None,
            "non_fish_decision": None,
            "destination_fridge_temperature_c": None,
            "fridge_issue_type": None,
            "transient_issue_description": None,
            "corrective_action_taken": None,
            "follow_up_temperature_c": None,
            "food_returned_to_fridge": None,
            "maintenance_logged": None,
            "maintenance_reference": None,
            "reason": "LLM not configured",
        }

        if not self.client:
            return empty_facts

        existing_state = existing_state or {}
        current_issues = current_issues or []
        recent_conversation_history = recent_conversation_history or []

        messages = [
            {
                "role": "system",
                "content": (
                    "You extract facts from a manager's corrective-action "
                    "narrative for an open fridge-temperature incident.\n"
                    "Return only a JSON object with exactly these fields:\n"
                    "{\n"
                    '  "food_probed": boolean or null,\n'
                    '  "fish_present": boolean or null,\n'
                    '  "non_fish_food_present": boolean or null,\n'
                    '  "food_temperature_c": number or null,\n'
                    '  "out_of_range_duration": "le_4h" | "gt_4h" | "uncertain" | null,\n'
                    '  "fish_decision": "discarded" | "kept_moved_to_compliant_fridge" | null,\n'
                    '  "non_fish_decision": "discarded" | "kept_moved_to_compliant_fridge" | null,\n'
                    '  "destination_fridge_temperature_c": number or null,\n'
                    '  "fridge_issue_type": "transient" | "maintenance" | null,\n'
                    '  "transient_issue_description": string or null,\n'
                    '  "corrective_action_taken": string or null,\n'
                    '  "follow_up_temperature_c": number or null,\n'
                    '  "food_returned_to_fridge": boolean or null,\n'
                    '  "maintenance_logged": boolean or null,\n'
                    '  "maintenance_reference": string or null,\n'
                    '  "reason": string\n'
                    "}\n"
                    "Rules:\n"
                    "- Extract only facts explicitly stated or clearly implied "
                    "by the user's message.\n"
                    "- Do not decide whether the corrective action is compliant. "
                    "A deterministic validator will decide that.\n"
                    "- Do not invent missing facts.\n"
                    "- The food probe temperature is one shared temperature for "
                    "the affected fridge incident. Do not ask for or infer separate "
                    "fish and non-fish temperatures.\n"
                    "- The out-of-range duration is one shared duration for the "
                    "affected fridge incident. Do not create category-specific "
                    "duration values.\n"
                    "- Use fish_present true when the user says fish was present "
                    "in the affected fridge. Use fish_present false when the "
                    "user says there was no fish in the affected fridge.\n"
                    "- Use non_fish_food_present true when the user says other "
                    "chilled food, meat, chicken, dairy, cooked food, prepared "
                    "food, or non-fish food was present in the affected fridge.\n"
                    "- Use non_fish_food_present false only when the user clearly "
                    "says there was no other chilled food or only fish was affected.\n"
                    "- If the assistant asks whether there was any fish in "
                    "the affected fridge and the user answers yes, extract "
                    "fish_present as true. If the user answers no, extract "
                    "fish_present as false.\n"
                    "- If the assistant asks whether there was other chilled food "
                    "and the user answers yes, extract non_fish_food_present as true. "
                    "If the user answers no, extract non_fish_food_present as false.\n"
                    "- Use fish_decision only for what happened to fish.\n"
                    "- Use non_fish_decision only for what happened to other chilled food.\n"
                    "- If the previous assistant question asked only about fish, "
                    "and the user gives a short contextual answer such as discarded, "
                    "it was discarded, moved it, or it was moved, extract only "
                    "fish_decision and leave non_fish_decision as null.\n"
                    "- If the previous assistant question asked only about other "
                    "chilled food, and the user gives a short contextual answer "
                    "such as discarded, it was discarded, moved it, or it was moved, "
                    "extract only non_fish_decision and leave fish_decision as null.\n"
                    "- Do not fill both fish_decision and non_fish_decision from "
                    "a short pronoun answer such as it was discarded.\n"
                    "- Fill both category decisions only when the user explicitly "
                    "says both, all affected food, fish and other chilled food, "
                    "or equivalent wording.\n"
                    "- If the user says all affected food was discarded, and both "
                    "fish and other chilled food require a decision, extract both "
                    "fish_decision and non_fish_decision as discarded.\n"
                    "- If the user says all affected food was moved to a compliant fridge, "
                    "and both fish and other chilled food require a decision, extract both "
                    "fish_decision and non_fish_decision as kept_moved_to_compliant_fridge.\n"
                    "- Do not infer a destination fridge temperature from the "
                    "phrase 'moved to a compliant fridge'.\n"
                    "- Extract destination_fridge_temperature_c only when the "
                    "user explicitly states the destination fridge temperature.\n"
                    "- For duration, use le_4h when the user clearly says no "
                    "more than four hours, within four hours, about two hours, "
                    "or similar.\n"
                    "- Use gt_4h when the user clearly says more than four "
                    "hours.\n"
                    "- Use uncertain when the user says they do not know, are "
                    "not sure, or cannot confirm the duration.\n"
                    "- Use fridge_issue_type transient when the issue was "
                    "corrected without maintenance or repair, such as closing "
                    "a door, adjusting a setting, reducing loading, or restoring "
                    "power.\n"
                    "- Use fridge_issue_type maintenance when the fridge was "
                    "logged for repair, engineer callout, service, or "
                    "maintenance.\n"
                    "- Preserve existing facts unless the latest user message "
                    "clearly corrects them.\n"
                    "- Use the active validator issues and previous assistant question "
                    "to interpret short contextual replies such as yes, no, "
                    "yes it was, no it was not, I did, or we did.\n"
                    "- If the previous assistant question asked whether a specific "
                    "boolean fact is true, and the latest user message clearly "
                    "confirms or denies it, extract that specific boolean fact.\n"
                    "- Do not use a short yes/no reply to fill open-ended fields "
                    "such as temperatures, category decisions, issue type, or corrective "
                    "action taken. Those require the user to state the actual fact.\n"
                    "- Extract facts across the full corrective-action schema, not only "
                    "the field currently listed in the unresolved validator issue.\n"
                    "- The unresolved validator issues and previous assistant question "
                    "provide conversation context; they do not limit which fields can "
                    "be extracted from the latest user response.\n"
                    "- If the latest user response clearly states information relevant "
                    "to any corrective-action field, extract it, even if the current "
                    "assistant question was focused on a different field.\n"
                    "- Keep cause and action separate. For example, if the user says "
                    "a fridge or freezer door was left open and then says they closed "
                    "it, extract the door-left-open detail as the issue description "
                    "and extract closing the door as corrective_action_taken.\n"
                    "- If the user gives an equipment temperature after the corrective "
                    "action, extract it as follow_up_temperature_c.\n"
                    "Return only valid JSON."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Existing extracted state:\n"
                    f"{json.dumps(existing_state)}\n\n"
                    "Current unresolved validator issues:\n"
                    f"{json.dumps(current_issues)}\n\n"
                    "Previous assistant question:\n"
                    f"{last_assistant_message}\n\n"
                    "Recent conversation history:\n"
                    f"{json.dumps(recent_conversation_history)}\n\n"
                    "Latest user message:\n"
                    f"{user_message}"
                ),
            },
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            if content is None:
                return {
                    **empty_facts,
                    "reason": "Empty response from LLM",
                }

            result = json.loads(content)

            allowed_durations = {"le_4h", "gt_4h", "uncertain"}
            allowed_food_decisions = {
                "discarded",
                "kept_moved_to_compliant_fridge",
            }
            allowed_issue_types = {"transient", "maintenance"}

            def clean_enum(value, allowed_values):
                return value if value in allowed_values else None

            def clean_bool(value):
                return value if isinstance(value, bool) else None

            def clean_float(value):
                if value is None:
                    return None
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return None

            def clean_string(value):
                if not isinstance(value, str):
                    return None
                cleaned = value.strip()
                return cleaned or None

            cleaned_facts = {
                "food_probed": clean_bool(result.get("food_probed")),
                "fish_present": clean_bool(result.get("fish_present")),
                "non_fish_food_present": clean_bool(
                    result.get("non_fish_food_present")
                ),
                "food_temperature_c": clean_float(
                    result.get("food_temperature_c")
                ),
                "out_of_range_duration": clean_enum(
                    result.get("out_of_range_duration"),
                    allowed_durations,
                ),
                "fish_decision": clean_enum(
                    result.get("fish_decision"),
                    allowed_food_decisions,
                ),
                "non_fish_decision": clean_enum(
                    result.get("non_fish_decision"),
                    allowed_food_decisions,
                ),
                "destination_fridge_temperature_c": clean_float(
                    result.get("destination_fridge_temperature_c")
                ),
                "fridge_issue_type": clean_enum(
                    result.get("fridge_issue_type"),
                    allowed_issue_types,
                ),
                "transient_issue_description": clean_string(
                    result.get("transient_issue_description")
                ),
                "corrective_action_taken": clean_string(
                    result.get("corrective_action_taken")
                ),
                "follow_up_temperature_c": clean_float(
                    result.get("follow_up_temperature_c")
                ),
                "food_returned_to_fridge": clean_bool(
                    result.get("food_returned_to_fridge")
                ),
                "maintenance_logged": clean_bool(
                    result.get("maintenance_logged")
                ),
                "maintenance_reference": clean_string(
                    result.get("maintenance_reference")
                ),
                "reason": result.get("reason", ""),
            }

            latest_message = user_message.lower().strip()
            latest_words = latest_message.replace(".", "").replace(",", "").split()
            previous_question = (last_assistant_message or "").lower()
            current_issue_fields = {
                issue.get("field")
                for issue in current_issues
                if isinstance(issue, dict)
            }

            explicit_multi_category_decision = any(
                phrase in latest_message
                for phrase in (
                    "both",
                    "all affected food",
                    "all the affected food",
                    "fish and other chilled food",
                    "fish and the other chilled food",
                    "fish and non-fish",
                    "fish and non fish",
                    "fish and the non-fish",
                    "fish and the non fish",
                )
            )

            short_contextual_decision_reply = (
                len(latest_words) <= 5
                and not explicit_multi_category_decision
                and (
                    cleaned_facts.get("fish_decision") is not None
                    or cleaned_facts.get("non_fish_decision") is not None
                )
            )

            focused_on_fish_decision = (
                "fish_decision" in current_issue_fields
                and "fish" in previous_question
                and "other chilled" not in previous_question
                and "non-fish" not in previous_question
                and "non fish" not in previous_question
            )

            focused_on_non_fish_decision = (
                "non_fish_decision" in current_issue_fields
                and (
                    "other chilled" in previous_question
                    or "non-fish" in previous_question
                    or "non fish" in previous_question
                )
            )

            if short_contextual_decision_reply:
                if focused_on_fish_decision:
                    cleaned_facts["non_fish_decision"] = None

                if focused_on_non_fish_decision:
                    cleaned_facts["fish_decision"] = None

            return cleaned_facts
        except Exception as e:
            logger.error(
                "LLM error in extract_fridge_corrective_action_facts: %s",
                e,
            )
            return {
                **empty_facts,
                "reason": f"API error: {e}",
            }

    def generate_fridge_corrective_action_question(
        self,
        issue: Dict[str, Any],
        current_state: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate a natural-language question for one validator issue.

        The validator decides what is missing or contradictory. This method only
        phrases the question. It must not add extra requirements.
        """

        fallback_questions = {
            "food_probed": (
                "Was the food inside the fridge probed with a thermometer?"
            ),
            "fish_present": "Was there any fish in the affected fridge?",
            "non_fish_food_present": (
                "Was there any other chilled food in the affected fridge?"
            ),
            "food_temperature_c": (
                "What temperature was recorded when the food was probed?"
            ),
            "out_of_range_duration": (
                "Was the food outside the safe range for no more than four "
                "hours, more than four hours, or is the duration uncertain?"
            ),
            "fish_decision": (
                "Was the fish discarded, or was it moved to another compliant "
                "fridge?"
            ),
            "non_fish_decision": (
                "Was the other chilled food discarded, or was it moved to "
                "another compliant fridge?"
            ),
            "fridge_issue_type": (
                "Was the fridge issue corrected as a temporary issue, or was "
                "it logged for maintenance or repair?"
            ),
            "corrective_action_taken": (
                "What corrective action was taken to correct the fridge issue?"
            ),
            "follow_up_temperature_c": (
                "What was the follow-up fridge temperature after the corrective "
                "action was taken?"
            ),
            "maintenance_logged": (
                "Was the fridge logged for maintenance or repair?"
            ),
        }

        field = issue.get("field")
        fallback_question = fallback_questions.get(
            field,
            issue.get("message", "Please provide the missing information."),
        )

        if not self.client:
            return fallback_question

        messages = [
            {
                "role": "system",
                "content": (
                    "You phrase one concise clarification question for a food "
                    "safety corrective-action workflow.\n"
                    "The deterministic validator has already decided what is "
                    "missing or contradictory. You must not add any extra "
                    "requirements.\n"
                    "Return only a JSON object with exactly this field:\n"
                    '{ "question": string }\n'
                    "Rules:\n"
                    "- Ask only about the validator issue provided.\n"
                    "- Ask one shared duration question for the fridge incident; "
                    "do not ask category-specific duration questions.\n"
                    "- Do not ask for destination fridge name.\n"
                    "- Do not ask for destination fridge temperature.\n"
                    "- Do not ask for evidence beyond the validator issue.\n"
                    "- Keep the question short and practical.\n"
                    "- In user-facing wording, say temporary issue rather than transient issue.\n"
                    "Return only valid JSON."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Validator issue:\n"
                    f"{json.dumps(issue)}\n\n"
                    "Current extracted state:\n"
                    f"{json.dumps(current_state or {})}"
                ),
            },
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            if content is None:
                return fallback_question

            result = json.loads(content)
            question = result.get("question")
            if not isinstance(question, str) or not question.strip():
                return fallback_question

            return question.strip()
        except Exception as e:
            logger.error(
                "LLM error in generate_fridge_corrective_action_question: %s",
                e,
            )
            return fallback_question

    def generate_fridge_corrective_action_summary(
        self,
        state: Dict[str, Any],
    ) -> str:
        """
        Draft a final corrective-action summary from validator-approved facts.

        The workflow should call this only after deterministic validation passes.
        """

        fallback_summary = (
            "Corrective action was recorded and validated. Please review the "
            "approved corrective-action facts before confirming."
        )

        if not self.client:
            return fallback_summary

        messages = [
            {
                "role": "system",
                "content": (
                    "You draft a concise final corrective-action summary for a "
                    "food safety shift diary.\n"
                    "The deterministic validator has already approved the "
                    "facts. Do not decide compliance.\n"
                    "Return only a JSON object with exactly this field:\n"
                    '{ "summary": string }\n'
                    "Rules:\n"
                    "- Use only facts present in the provided state.\n"
                    "- Always mention food_temperature_c when it is present in "
                    "the state.\n"
                    "- Do not state that fish was discarded or moved unless "
                    "fish_decision is present in the state.\n"
                    "- Do not state that other chilled food was discarded or "
                    "moved unless non_fish_decision is present in the state.\n"
                    "- If other chilled food was present but non_fish_decision "
                    "is absent, do not imply that any action was taken for that "
                    "category.\n"
                    "- Do not invent destination fridge name or destination "
                    "fridge temperature.\n"
                    "- Mention destination fridge temperature only if it is "
                    "present in the state.\n"
                    "- Mention maintenance reference only if it is present in "
                    "the state.\n"
                    "- Write in clear audit-style English.\n"
                    "- Use temporary issue instead of transient issue in user-facing text.\n"
                    "- Do not expose internal field names such as fish_present, "
                    "non_fish_food_present, fish_decision, or non_fish_decision.\n"
                    "- food_temperature_c is one shared probed food temperature "
                    "for the affected fridge incident.\n"
                    "- out_of_range_duration is one shared duration for the "
                    "affected fridge incident.\n"
                    "- Always mention out_of_range_duration when it is present "
                    "in the state. If it is uncertain, say the duration was uncertain.\n"
                    "- follow_up_temperature_c is the fridge temperature after "
                    "corrective action, not the food temperature.\n"
                    "- If fish_present is true, say fish was present in the affected fridge.\n"
                    "- If fish_present is false, say no fish was reported in the affected fridge.\n"
                    "- If non_fish_food_present is true, say other chilled food was present in the affected fridge.\n"
                    "- If fish_decision and non_fish_decision are both present, "
                    "distinguish the action taken for fish from the action taken "
                    "for other chilled food.\n"
                    "- If a category did not require action because it was within "
                    "its threshold, say that plainly and do not imply it was discarded.\n"
                    "- Do not include bullet points.\n"
                    "Return only valid JSON."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Validator-approved corrective-action state:\n"
                    f"{json.dumps(state)}"
                ),
            },
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            if content is None:
                return fallback_summary

            result = json.loads(content)
            summary = result.get("summary")
            if not isinstance(summary, str) or not summary.strip():
                return fallback_summary

            return summary.strip()
        except Exception as e:
            logger.error(
                "LLM error in generate_fridge_corrective_action_summary: %s",
                e,
            )
            return fallback_summary


    def extract_freezer_corrective_action_facts(
        self,
        user_message: str,
        existing_state: Optional[Dict[str, Any]] = None,
        current_issues: Optional[List[Dict[str, Any]]] = None,
        last_assistant_message: Optional[str] = None,
        recent_conversation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Extract corrective-action facts from a user's freezer incident narrative.

        This method extracts facts only. It must not decide compliance and must
        not invent missing facts. A deterministic validator decides whether the
        extracted facts are sufficient and compliant.
        """
        empty_facts = {
            "food_checked_for_thawing_signs": None,
            "thawing_signs_present": None,
            "food_decision": None,
            "destination_freezer_temperature_c": None,
            "freezer_issue_type": None,
            "transient_issue_description": None,
            "corrective_action_taken": None,
            "follow_up_temperature_c": None,
            "food_returned_to_freezer": None,
            "maintenance_logged": None,
            "maintenance_reference": None,
            "reason": "LLM not configured",
        }

        if not self.client:
            return empty_facts

        existing_state = existing_state or {}
        current_issues = current_issues or []
        recent_conversation_history = recent_conversation_history or []

        messages = [
            {
                "role": "system",
                "content": (
                    "You extract facts from a manager's corrective-action "
                    "narrative for an open freezer-temperature incident.\n"
                    "Return only a JSON object with exactly these fields:\n"
                    "{\n"
                    '  "food_checked_for_thawing_signs": boolean or null,\n'
                    '  "thawing_signs_present": boolean or null,\n'
                    '  "food_decision": "discarded" | '
                    '"moved_to_compliant_freezer" | null,\n'
                    '  "destination_freezer_temperature_c": number or null,\n'
                    '  "freezer_issue_type": "transient" | "maintenance" | null,\n'
                    '  "transient_issue_description": string or null,\n'
                    '  "corrective_action_taken": string or null,\n'
                    '  "follow_up_temperature_c": number or null,\n'
                    '  "food_returned_to_freezer": boolean or null,\n'
                    '  "maintenance_logged": boolean or null,\n'
                    '  "maintenance_reference": string or null,\n'
                    '  "reason": string\n'
                    "}\n"
                    "Rules:\n"
                    "- Extract only facts explicitly stated or clearly implied "
                    "by the user's message.\n"
                    "- Do not decide whether the corrective action is compliant. "
                    "A deterministic validator will decide that.\n"
                    "- Do not invent missing facts.\n"
                    "- Do not infer a destination freezer temperature from the "
                    "phrase 'moved to a compliant freezer'.\n"
                    "- Extract destination_freezer_temperature_c only when the "
                    "user explicitly states the destination freezer temperature.\n"
                    "- If the user says food was moved to a compliant freezer, "
                    "set food_decision to moved_to_compliant_freezer, but leave "
                    "destination_freezer_temperature_c as null unless a "
                    "temperature is explicitly stated.\n"
                    "- Use food_checked_for_thawing_signs true when the user says "
                    "they checked, inspected, assessed, or looked at the frozen "
                    "food for signs of thawing.\n"
                    "- Use thawing_signs_present true when the user says the food "
                    "had started to thaw, was softening, defrosting, partially "
                    "defrosted, wet, slushy, or otherwise showed thawing signs.\n"
                    "- Use thawing_signs_present false when the user says the food "
                    "was still fully frozen, hard frozen, had no signs of thawing, "
                    "or was not thawing.\n"
                    "- If the user says they discarded, threw away, disposed of, "
                    "or binned the food, set food_decision to discarded.\n"
                    "- If the user says they moved the food to another compliant "
                    "freezer, set food_decision to moved_to_compliant_freezer.\n"
                    "- Use freezer_issue_type transient when the issue was corrected "
                    "without maintenance or repair, such as closing a door, adjusting "
                    "a setting, reducing loading, or restoring power.\n"
                    "- Use freezer_issue_type maintenance when the freezer was logged "
                    "for repair, engineer callout, service, or maintenance.\n"
                    "- Preserve existing facts unless the latest user message clearly "
                    "corrects them.\n"
                    "- Use the active validator issues and previous assistant question "
                    "to interpret short contextual replies such as yes, no, "
                    "yes it was, no it was not, I did, or we did.\n"
                    "- If the previous assistant question asked whether a specific "
                    "boolean fact is true, and the latest user message clearly "
                    "confirms or denies it, extract that specific boolean fact.\n"
                    "- Do not use a short yes/no reply to fill open-ended fields "
                    "such as temperatures, food decisions, issue type, or corrective "
                    "action taken. Those require the user to state the actual fact.\n"
                    "- Extract facts across the full corrective-action schema, not only "
                    "the field currently listed in the unresolved validator issue.\n"
                    "- The unresolved validator issues and previous assistant question "
                    "provide conversation context; they do not limit which fields can "
                    "be extracted from the latest user response.\n"
                    "- If the latest user response clearly states information relevant "
                    "to any corrective-action field, extract it, even if the current "
                    "assistant question was focused on a different field.\n"
                    "- Keep cause and action separate. For example, if the user says "
                    "a fridge or freezer door was left open and then says they closed "
                    "it, extract the door-left-open detail as the issue description "
                    "and extract closing the door as corrective_action_taken.\n"
                    "- If the user gives an equipment temperature after the corrective "
                    "action, extract it as follow_up_temperature_c.\n"
                    "Return only valid JSON."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Existing extracted state:\n"
                    f"{json.dumps(existing_state)}\n\n"
                    "Current unresolved validator issues:\n"
                    f"{json.dumps(current_issues)}\n\n"
                    "Previous assistant question:\n"
                    f"{last_assistant_message}\n\n"
                    "Recent conversation history:\n"
                    f"{json.dumps(recent_conversation_history)}\n\n"
                    "Latest user message:\n"
                    f"{user_message}"
                ),
            },
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if content is None:
                return {
                    **empty_facts,
                    "reason": "Empty response from LLM",
                }

            result = json.loads(content)

            allowed_food_decisions = {
                "discarded",
                "moved_to_compliant_freezer",
            }
            allowed_issue_types = {"transient", "maintenance"}

            def clean_enum(value, allowed_values):
                return value if value in allowed_values else None

            def clean_bool(value):
                return value if isinstance(value, bool) else None

            def clean_float(value):
                if value is None:
                    return None
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return None

            def clean_string(value):
                if not isinstance(value, str):
                    return None
                cleaned = value.strip()
                return cleaned or None

            food_checked_for_thawing_signs = clean_bool(
                result.get("food_checked_for_thawing_signs")
            )
            thawing_signs_present = clean_bool(
                result.get("thawing_signs_present")
            )
            freezer_issue_type = clean_enum(
                result.get("freezer_issue_type"),
                allowed_issue_types,
            )
            maintenance_logged = clean_bool(
                result.get("maintenance_logged")
            )

            if (
                food_checked_for_thawing_signs is None
                and thawing_signs_present is not None
            ):
                food_checked_for_thawing_signs = True

            if (
                freezer_issue_type != "maintenance"
                and maintenance_logged is False
            ):
                maintenance_logged = None

            return {
                "food_checked_for_thawing_signs": food_checked_for_thawing_signs,
                "thawing_signs_present": thawing_signs_present,
                "food_decision": clean_enum(
                    result.get("food_decision"),
                    allowed_food_decisions,
                ),
                "destination_freezer_temperature_c": clean_float(
                    result.get("destination_freezer_temperature_c")
                ),
                "freezer_issue_type": freezer_issue_type,
                "transient_issue_description": clean_string(
                    result.get("transient_issue_description")
                ),
                "corrective_action_taken": clean_string(
                    result.get("corrective_action_taken")
                ),
                "follow_up_temperature_c": clean_float(
                    result.get("follow_up_temperature_c")
                ),
                "food_returned_to_freezer": clean_bool(
                    result.get("food_returned_to_freezer")
                ),
                "maintenance_logged": maintenance_logged,
                "maintenance_reference": clean_string(
                    result.get("maintenance_reference")
                ),
                "reason": result.get("reason", ""),
            }

        except Exception as e:
            logger.error(
                "LLM error in extract_freezer_corrective_action_facts: %s",
                e,
            )
            return {
                **empty_facts,
                "reason": f"API error: {e}",
            }

    def generate_freezer_corrective_action_question(
        self,
        issue: Dict[str, Any],
        current_state: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate a natural-language question for one freezer validator issue.

        The validator decides what is missing or contradictory. This method only
        phrases the question. It must not add extra requirements.
        """
        fallback_questions = {
            "food_checked_for_thawing_signs": (
                "Was the frozen food checked for signs of thawing?"
            ),
            "thawing_signs_present": (
                "Did the frozen food show any signs of thawing?"
            ),
            "food_decision": (
                "Was the food discarded, or was it moved to compliant freezer "
                "equipment?"
            ),
            "freezer_issue_type": (
                "Was the freezer issue corrected as a transient issue, or was "
                "it logged for maintenance or repair?"
            ),
            "corrective_action_taken": (
                "What corrective action was taken to correct the freezer issue?"
            ),
            "follow_up_temperature_c": (
                "What was the follow-up freezer temperature after the corrective "
                "action was taken?"
            ),
            "maintenance_logged": (
                "Was the freezer logged for maintenance or repair?"
            ),
            "destination_freezer_temperature_c": (
                "What was the temperature of the destination freezer?"
            ),
        }

        field = issue.get("field")
        fallback_question = fallback_questions.get(
            field,
            issue.get("message", "Please provide the missing information."),
        )

        if not self.client:
            return fallback_question

        messages = [
            {
                "role": "system",
                "content": (
                    "You phrase one concise clarification question for a food "
                    "safety freezer corrective-action workflow.\n"
                    "The deterministic validator has already decided what is "
                    "missing or contradictory. You must not add any extra "
                    "requirements.\n"
                    "Return only a JSON object with exactly this field:\n"
                    '{ "question": string }\n'
                    "Rules:\n"
                    "- Ask only about the validator issue provided.\n"
                    "- Do not ask for destination freezer name.\n"
                    "- Do not ask for destination freezer temperature unless the "
                    "validator issue is specifically about a volunteered "
                    "destination_freezer_temperature_c contradiction.\n"
                    "- Do not ask for evidence beyond the validator issue.\n"
                    "- Keep the question short and practical.\n"
                    "- In user-facing wording, say temporary issue rather than transient issue.\n"
                    "Return only valid JSON."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Validator issue:\n"
                    f"{json.dumps(issue)}\n\n"
                    "Current extracted state:\n"
                    f"{json.dumps(current_state or {})}"
                ),
            },
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if content is None:
                return fallback_question

            result = json.loads(content)
            question = result.get("question")

            if not isinstance(question, str) or not question.strip():
                return fallback_question

            return question.strip()

        except Exception as e:
            logger.error(
                "LLM error in generate_freezer_corrective_action_question: %s",
                e,
            )
            return fallback_question

    def generate_freezer_corrective_action_summary(
        self,
        state: Dict[str, Any],
    ) -> str:
        """
        Draft a final freezer corrective-action summary from validator-approved facts.

        The workflow should call this only after deterministic validation passes.
        """
        fallback_summary = (
            "Freezer corrective action was recorded and validated. Please review "
            "the approved corrective-action facts before confirming."
        )

        if not self.client:
            return fallback_summary

        messages = [
            {
                "role": "system",
                "content": (
                    "You draft a concise final corrective-action summary for a "
                    "food safety shift diary.\n"
                    "The deterministic validator has already approved the facts. "
                    "Do not decide compliance.\n"
                    "Return only a JSON object with exactly this field:\n"
                    '{ "summary": string }\n'
                    "Rules:\n"
                    "- Use only facts present in the provided state.\n"
                    "- Do not invent destination freezer name or destination "
                    "freezer temperature.\n"
                    "- Mention destination freezer temperature only if it is "
                    "present in the state.\n"
                    "- Mention maintenance reference only if it is present in "
                    "the state.\n"
                    "- Write in clear audit-style English.\n"
                    "- Use temporary issue instead of transient issue in user-facing text.\n"
                    "- Do not include bullet points.\n"
                    "Return only valid JSON."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Validator-approved freezer corrective-action state:\n"
                    f"{json.dumps(state)}"
                ),
            },
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.2,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            if content is None:
                return fallback_summary

            result = json.loads(content)
            summary = result.get("summary")

            if not isinstance(summary, str) or not summary.strip():
                return fallback_summary

            return summary.strip()

        except Exception as e:
            logger.error(
                "LLM error in generate_freezer_corrective_action_summary: %s",
                e,
            )
            return fallback_summary

    def classify_freezer_corrective_action_approval(
        self,
        user_message: str,
    ) -> Dict[str, Any]:
        """
        Classify whether the user approves the freezer corrective-action summary.

        Approval intent is not fridge/freezer-specific, so this delegates to the
        existing corrective-action approval classifier.
        """
        return self.classify_fridge_corrective_action_approval(
            user_message=user_message,
        )


    def classify_fridge_corrective_action_approval(
        self,
        user_message: str,
    ) -> Dict[str, Any]:
        """
        Classify whether the user approves the final corrective-action summary.
        """

        fallback = {
            "action": "unclear",
            "reason": "LLM not configured",
            "assistant_message": (
                "Please confirm whether you approve the corrective-action "
                "summary, or provide the correction needed."
            ),
        }

        if not self.client:
            return fallback

        messages = [
            {
                "role": "system",
                "content": (
                    "You classify the user's response to a final "
                    "corrective-action summary.\n"
                    "Return only a JSON object with exactly these fields:\n"
                    "{\n"
                    '  "action": "approve" | "correction" | "unclear",\n'
                    '  "reason": string,\n'
                    '  "assistant_message": string or null\n'
                    "}\n"
                    "Rules:\n"
                    "- Use approve when the user clearly approves, accepts, "
                    "confirms, or says the summary is correct.\n"
                    "- Use correction when the user provides a correction, "
                    "extra detail, or says the summary is wrong/incomplete.\n"
                    "- Use unclear when the intention is not clear.\n"
                    "- Do not decide compliance.\n"
                    "Return only valid JSON."
                ),
            },
            {
                "role": "user",
                "content": f"User response:\n{user_message}",
            },
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            if content is None:
                return {
                    **fallback,
                    "reason": "Empty response from LLM",
                }

            result = json.loads(content)
            action = result.get("action")
            if action not in ("approve", "correction", "unclear"):
                return {
                    **fallback,
                    "reason": "LLM returned an unsupported action",
                }

            return {
                "action": action,
                "reason": result.get("reason", ""),
                "assistant_message": result.get("assistant_message"),
            }
        except Exception as e:
            logger.error(
                "LLM error in classify_fridge_corrective_action_approval: %s",
                e,
            )
            return {
                **fallback,
                "reason": f"API error: {e}",
            }


















_adapter = None


def get_llm_adapter() -> LLMAdapter:
    """Return a singleton instance of LLMAdapter."""
    global _adapter
    if _adapter is None:
        _adapter = LLMAdapter()
    return _adapter
