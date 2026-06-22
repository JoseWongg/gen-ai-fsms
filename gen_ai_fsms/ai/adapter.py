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



_adapter = None


def get_llm_adapter() -> LLMAdapter:
    """Return a singleton instance of LLMAdapter."""
    global _adapter
    if _adapter is None:
        _adapter = LLMAdapter()
    return _adapter
