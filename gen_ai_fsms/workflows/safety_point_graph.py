"""
LangGraph workflow for the safety point approval flow.

This graph coordinates the approval workflow for safety points selected from
the completed Food Safety Profile screening. It is designed as a controlled
workflow: the LLM may classify free-text responses and answer clarification
questions, but it must not approve safety points or assess alternative methods.
"""

import random
from typing import Any, Dict, List, Optional, TypedDict
from langgraph.graph import END, StateGraph

from gen_ai_fsms.ai.adapter import get_llm_adapter
from gen_ai_fsms.db.session import SessionLocal

from gen_ai_fsms.services.business_context_service import get_business_context
from gen_ai_fsms.services.context_relevance_service import build_relevant_prompt_context
from gen_ai_fsms.services.safety_point_approval_service import (
    get_condition_values_for_profile,
    get_relevant_safety_points_for_profile,
    get_screening_completion_status,
    record_approved_safety_point,
    save_chilling_equipment_items_for_profile,
)


MAX_CLARIFICATION_TURNS_PER_SAFETY_POINT = 3
CHILLING_EQUIPMENT_QUESTION_KEY = "chilling_equipment_temperature_checks"
CHILLING_EQUIPMENT_SOURCE_SAFETY_POINT_ID = "4.1.1.3"
MAX_CHILLING_EQUIPMENT_NAME_ATTEMPTS = 3
MAX_CHILLING_EQUIPMENT_DETAIL_ATTEMPTS = 3


SAFETY_POINT_PROMPT_INTROS = [
    "Please now confirm if",
    "State now whether",
    "Let me know now if",
    "I now need to know if",
    "Now, indicate if",
    "To continue, please respond whether",
    "I now need you to tell me if",
    "Now please confirm whether",
    "Next, I need you to indicate whether",
    "What I need next from you is to state if",
]

SAFETY_POINT_COMPLIANCE_VERBS = [
    "follows",
    "adheres to",
    "observes",
    "abides by",
]


def _select_non_repeating_index(
    options: List[str],
    previous_index: Optional[int],
) -> int:
    available_indexes = [
        index
        for index in range(len(options))
        if index != previous_index
    ]

    return random.choice(
        available_indexes or list(range(len(options)))
    )


def _build_safety_point_prompt(
    state: "SafetyPointApprovalState",
) -> str:
    previous_intro_index = state.get("last_safety_point_prompt_intro_index")
    selected_intro_index = _select_non_repeating_index(
        SAFETY_POINT_PROMPT_INTROS,
        previous_intro_index,
    )
    state["last_safety_point_prompt_intro_index"] = selected_intro_index

    previous_verb_index = state.get("last_safety_point_prompt_verb_index")
    selected_verb_index = _select_non_repeating_index(
        SAFETY_POINT_COMPLIANCE_VERBS,
        previous_verb_index,
    )
    state["last_safety_point_prompt_verb_index"] = selected_verb_index

    intro = SAFETY_POINT_PROMPT_INTROS[selected_intro_index]
    verb = SAFETY_POINT_COMPLIANCE_VERBS[selected_verb_index]

    return (
        f"{intro} the business {verb} the safety point above. "
        "Alternatively, you can ask clarification questions."
    )


def _build_additional_question_prompt(
    question_text: str,
    is_next_question: bool = False,
) -> str:
    prefix = (
        "Additional information recorded. Please answer this next required "
        "additional question:"
        if is_next_question
        else "Before approval can be recorded, please answer this required "
        "additional question:"
    )

    return (
        f"{prefix}\n\n"
        f"{question_text}\n\n"
        "You can respond to the question or ask clarification questions."
    )




class SafetyPointApprovalState(TypedDict, total=False):
    """
    State schema for the safety point approval workflow.
    """

    business_profile_id: int
    user_id: int
    current_safety_point_index: int
    safety_points_list: List[Dict[str, Any]]
    current_safety_point: Optional[Dict[str, Any]]
    current_q_and_a_messages: List[Dict[str, Any]]
    approval_chat_history: List[Dict[str, Any]]
    clarification_turn_counts: Dict[str, int]
    last_user_message: Optional[str]
    current_response_intent: Optional[str]
    pending_additional_questions: List[Dict[str, Any]]
    current_additional_question_index: Optional[int]
    additional_answers: Dict[str, str]
    different_method_declared_message: Optional[str]
    approved_safety_point_ids: List[str]
    status: str
    next_action: Optional[str]
    assistant_message: Optional[str]
    current_safety_point_view: Dict[str, Any]
    approval_progress: Dict[str, int]
    current_additional_question: Optional[Dict[str, Any]]
    awaiting_additional_answers: bool
    condition_values: Dict[str, str]
    business_context: Dict[str, Any]
    last_review_message: Optional[str]
    last_confirmation_message: Optional[str]
    active_condition_count: int
    completed_active_condition_count: int
    relevant_safety_point_count: int
    last_approved_safety_point_record: Dict[str, Any]
    last_safety_point_prompt_intro_index: Optional[int]
    chilling_equipment_flow: Dict[str, Any]


def _get_current_safety_point(
    state: SafetyPointApprovalState,
) -> Optional[Dict[str, Any]]:
    safety_points = state.get("safety_points_list", [])
    current_index = state.get("current_safety_point_index", 0)

    if not safety_points:
        return None

    if current_index < 0 or current_index >= len(safety_points):
        return None

    return safety_points[current_index]

def _get_current_additional_question(
    state: SafetyPointApprovalState,
) -> Optional[Dict[str, Any]]:
    pending_questions = state.get("pending_additional_questions", [])
    current_index = state.get("current_additional_question_index")

    if current_index is None:
        return None

    if current_index < 0 or current_index >= len(pending_questions):
        return None

    return pending_questions[current_index]



def _build_provenance_references(
    safety_point: Optional[Dict[str, Any]],
) -> List[str]:
    """Build ordered provenance references for a safety point."""
    if safety_point is None:
        return []

    provenance_references: List[str] = []

    section_name = safety_point.get("section_name")
    safe_method_name = safety_point.get("safe_method_name")

    if section_name and safe_method_name:
        provenance_references.append(
            f"SFBB Pack > {section_name} > {safe_method_name}"
        )

    for reference in safety_point.get("source_references", []):
        if reference and reference not in provenance_references:
            provenance_references.append(reference)

    return provenance_references


def _build_current_safety_point_view(
    state: SafetyPointApprovalState,
) -> Dict[str, Any]:
    current_safety_point = state.get("current_safety_point")
    safety_points = state.get("safety_points_list", [])
    current_index = state.get("current_safety_point_index", 0)
    approved_ids = state.get("approved_safety_point_ids", [])

    total_count = len(safety_points)

    progress = {
        "current_index": current_index,
        "current_number": current_index + 1 if total_count else 0,
        "total_count": total_count,
        "approved_count": len(approved_ids),
        "remaining_count": max(total_count - len(approved_ids), 0),
    }

    state["approval_progress"] = progress

    if current_safety_point is None:
        return {
            "safety_point_id": None,
            "safety_point_text": None,
            "original_safety_point_text": None,
            "safety_point_instruction": None,
            "safety_point_rationale": None,
            "section_id": None,
            "section_name": None,
            "safe_method_id": None,
            "safe_method_name": None,
            "source_references": [],
            "additional_source_references": [],
            "provenance_references": [],
            "pending_additional_questions": [],
            "current_additional_question": None,
            "progress": progress,
        }

    current_additional_question = (
        _get_current_additional_question(state)
        if state.get("awaiting_additional_answers")
        else None
    )
    state["current_additional_question"] = current_additional_question

    original_safety_point_text = (
        current_safety_point.get("text")
        or current_safety_point.get("safety_point_text")
    )
    safety_point_instruction = (
        current_safety_point.get("instruction")
        or original_safety_point_text
    )
    safety_point_rationale = current_safety_point.get("rationale", "")

    return {
        "safety_point_id": current_safety_point.get("safety_point_id"),
        "safety_point_text": original_safety_point_text,
        "original_safety_point_text": original_safety_point_text,
        "safety_point_instruction": safety_point_instruction,
        "safety_point_rationale": safety_point_rationale,
        "section_id": current_safety_point.get("section_id"),
        "section_name": current_safety_point.get("section_name"),
        "safe_method_id": current_safety_point.get("safe_method_id"),
        "safe_method_name": current_safety_point.get("safe_method_name"),
        "source_references": current_safety_point.get("source_references", []),
        "additional_source_references": current_safety_point.get(
            "additional_source_references",
            [],
        ),
        "provenance_references": _build_provenance_references(
            current_safety_point
        ),
        "pending_additional_questions": state.get(
            "pending_additional_questions",
            [],
        ),
        "current_additional_question": current_additional_question,
        "progress": progress,
    }

def _set_current_safety_point_context(
    state: SafetyPointApprovalState,
) -> SafetyPointApprovalState:
    current_safety_point = _get_current_safety_point(state)
    state["current_safety_point"] = current_safety_point

    if current_safety_point is None:
        state["pending_additional_questions"] = []
        state["current_additional_question_index"] = None
        state["current_additional_question"] = None
        state["current_safety_point_view"] = _build_current_safety_point_view(state)
        return state

    additional_questions = current_safety_point.get("additional_questions", [])
    required_questions = [
        question for question in additional_questions
        if question.get("required") is True
    ]

    additional_answers = state.get("additional_answers", {})

    unanswered_required_questions = [
        question for question in required_questions
        if question.get("question_key") not in additional_answers
    ]

    state["pending_additional_questions"] = unanswered_required_questions

    if unanswered_required_questions:
        current_question_index = state.get("current_additional_question_index")

        if (
            current_question_index is None
            or current_question_index < 0
            or current_question_index >= len(unanswered_required_questions)
        ):
            state["current_additional_question_index"] = 0
    else:
        state["awaiting_additional_answers"] = False
        state["current_additional_question_index"] = None
        state["current_additional_question"] = None

    state["current_additional_question"] = (
        _get_current_additional_question(state)
        if state.get("awaiting_additional_answers")
        else None
    )
    state["current_safety_point_view"] = _build_current_safety_point_view(state)

    return state



def _append_approval_chat_message(
    state: SafetyPointApprovalState,
    role: str,
    content: Optional[str],
    message_type: str,
    safety_point_id: Optional[str] = None,
    safety_point_view: Optional[Dict[str, Any]] = None,
) -> None:
    """Append a display message to the persistent approval chat history."""
    if not content:
        return

    if safety_point_id is None:
        current_safety_point = state.get("current_safety_point") or {}
        safety_point_id = current_safety_point.get("safety_point_id")

    history = list(state.get("approval_chat_history", []))

    entry = {
        "role": role,
        "content": content,
        "message_type": message_type,
        "safety_point_id": safety_point_id,
    }

    if safety_point_view is not None:
        entry["safety_point_view"] = safety_point_view

    if history and history[-1] == entry:
        state["approval_chat_history"] = history
        return

    history.append(entry)
    state["approval_chat_history"] = history

def _is_chilling_equipment_question(
    question: Optional[Dict[str, Any]],
) -> bool:
    if not question:
        return False

    return question.get("question_key") == CHILLING_EQUIPMENT_QUESTION_KEY


def _build_chilling_equipment_name_prompt() -> str:
    return (
        "Please list all chilling equipment currently used by the business, "
        "such as Fridge 1, Freezer 1, or Chilled Display Unit 1. At this "
        "stage, provide only the equipment names."
    )


def _build_chilling_equipment_confirmation_message(
    equipment_names: List[str],
) -> str:
    numbered_names = "\n".join(
        f"{index}. {equipment_name}"
        for index, equipment_name in enumerate(equipment_names, start=1)
    )

    return (
        "I have captured these chilling equipment units:\n\n"
        f"{numbered_names}\n\n"
        "If this is correct, I will proceed to request the required "
        "information for each of them."
    )


def _build_chilling_equipment_corrected_list_prompt() -> str:
    return (
        "Please provide the full corrected list of chilling equipment names. "
        "Include all units that should be considered, such as Fridge 1, "
        "Freezer 1, or Chilled Display Unit 1."
    )


def _build_chilling_equipment_no_names_message() -> str:
    return (
        "No pieces of chilling equipment have been captured at this time. "
        "We need to move on, so no chilling equipment items will be recorded "
        "from this safety point at this stage."
    )


def _build_chilling_equipment_detail_prompt(
    equipment_name: str,
) -> str:
    return (
        f"For {equipment_name}, please indicate:\n"
        "1. whether it is a fridge or freezer\n"
        "2. whether it is used for storage or display\n"
        "3. whether its temperature is checked using a permanent digital/dial "
        "display or using a food probe thermometer between packs of chilled food"
    )


def _build_chilling_equipment_missing_detail_prompt(
    equipment_name: str,
    assistant_message: Optional[str] = None,
) -> str:
    if assistant_message:
        return assistant_message

    return (
        f"For {equipment_name}, I still need the missing required information. "
        "Please state whether it is a fridge or freezer, whether it is used "
        "for storage or display, and whether its temperature is checked using "
        "a permanent digital/dial display or a food probe thermometer between "
        "packs of chilled food."
    )


def _build_chilling_equipment_item_skipped_message(
    equipment_name: str,
) -> str:
    return (
        f"We need to move on. The information for {equipment_name} is still "
        "incomplete, so this item will not be recorded in the chilling "
        "equipment setup at this stage."
    )


def _build_chilling_equipment_items(
    equipment_names: List[str],
) -> List[Dict[str, Any]]:
    return [
        {
            "equipment_name": equipment_name,
            "equipment_type": None,
            "equipment_use": None,
            "temperature_check_method": None,
            "attempt_count": 0,
            "is_complete": False,
        }
        for equipment_name in equipment_names
    ]


def _get_or_create_chilling_equipment_flow(
    state: SafetyPointApprovalState,
) -> Dict[str, Any]:
    flow = state.setdefault(
        "chilling_equipment_flow",
        {
            "question_key": CHILLING_EQUIPMENT_QUESTION_KEY,
            "source_safety_point_id": CHILLING_EQUIPMENT_SOURCE_SAFETY_POINT_ID,
            "phase": "collect_names",
            "name_attempt_count": 0,
            "captured_equipment_names": [],
            "confirmed_equipment_names": [],
            "items": [],
            "current_item_index": 0,
            "saved_result": None,
        },
    )

    flow.setdefault("question_key", CHILLING_EQUIPMENT_QUESTION_KEY)
    flow.setdefault(
        "source_safety_point_id",
        CHILLING_EQUIPMENT_SOURCE_SAFETY_POINT_ID,
    )
    flow.setdefault("phase", "collect_names")
    flow.setdefault("name_attempt_count", 0)
    flow.setdefault("captured_equipment_names", [])
    flow.setdefault("confirmed_equipment_names", [])
    flow.setdefault("items", [])
    flow.setdefault("current_item_index", 0)
    flow.setdefault("saved_result", None)

    return flow


def _get_incomplete_chilling_equipment_items(
    flow: Dict[str, Any],
) -> List[Dict[str, Any]]:
    return [
        item
        for item in flow.get("items", [])
        if not item.get("is_complete")
    ]


def _get_complete_chilling_equipment_items(
    flow: Dict[str, Any],
) -> List[Dict[str, Any]]:
    return [
        item
        for item in flow.get("items", [])
        if item.get("is_complete")
    ]


def _find_next_incomplete_chilling_equipment_index(
    flow: Dict[str, Any],
) -> Optional[int]:
    items = flow.get("items", [])
    current_index = flow.get("current_item_index", 0)

    for index in range(current_index, len(items)):
        if (
            not items[index].get("is_complete")
            and not items[index].get("skipped_in_current_pass")
        ):
            return index

    for index, item in enumerate(items):
        if (
            not item.get("is_complete")
            and not item.get("skipped_in_current_pass")
        ):
            return index

    return None

def _build_chilling_equipment_summary(
    complete_items: List[Dict[str, Any]],
    incomplete_items: List[Dict[str, Any]],
) -> str:
    if complete_items:
        recorded_lines = "\n".join(
            f"{index}. {item.get('equipment_name')}"
            for index, item in enumerate(complete_items, start=1)
        )
    else:
        recorded_lines = "None"

    if incomplete_items:
        incomplete_lines = "\n".join(
            f"{index}. {item.get('equipment_name')}"
            for index, item in enumerate(incomplete_items, start=1)
        )
    else:
        incomplete_lines = "None"

    return (
        "The following chilling equipment items will be recorded:\n"
        f"{recorded_lines}\n\n"
        "The following chilling equipment items will not be recorded because "
        "required information is incomplete:\n"
        f"{incomplete_lines}"
    )


def _build_chilling_equipment_additional_answer_summary(
    complete_items: List[Dict[str, Any]],
) -> str:
    if not complete_items:
        return "No chilling equipment items were recorded."

    lines = []

    for item in complete_items:
        lines.append(
            "- "
            f"{item.get('equipment_name')}: "
            f"{item.get('equipment_type')}, "
            f"{item.get('equipment_use')}, "
            f"{item.get('temperature_check_method')}"
        )

    return "Chilling equipment recorded:\n" + "\n".join(lines)


def _reset_incomplete_chilling_equipment_attempts(
    flow: Dict[str, Any],
) -> None:
    for item in flow.get("items", []):
        if not item.get("is_complete"):
            item["attempt_count"] = 0
            item["skipped_in_current_pass"] = False


def _finalize_chilling_equipment_flow(
    state: SafetyPointApprovalState,
    flow: Dict[str, Any],
) -> SafetyPointApprovalState:
    complete_items = _get_complete_chilling_equipment_items(flow)
    incomplete_items = _get_incomplete_chilling_equipment_items(flow)

    state["assistant_message"] = _build_chilling_equipment_summary(
        complete_items=complete_items,
        incomplete_items=incomplete_items,
    )

    db = SessionLocal()

    try:
        saved_result = save_chilling_equipment_items_for_profile(
            db=db,
            business_profile_id=state["business_profile_id"],
            equipment_items=complete_items,
            source_safety_point_id=(
                CHILLING_EQUIPMENT_SOURCE_SAFETY_POINT_ID
            ),
            changed_by_user_id=state.get("user_id"),
        )
        db.commit()
        flow["saved_result"] = saved_result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    if incomplete_items:
        _reset_incomplete_chilling_equipment_attempts(flow)
        _append_approval_chat_message(
            state=state,
            role="assistant",
            content=state.get("assistant_message"),
            message_type="chilling_equipment_incomplete_summary",
        )
        state["last_user_message"] = None
        state["current_response_intent"] = None
        state["next_action"] = "move_to_next_safety_point"
        return state

    additional_answers = state.setdefault("additional_answers", {})
    additional_answers[CHILLING_EQUIPMENT_QUESTION_KEY] = (
        _build_chilling_equipment_additional_answer_summary(complete_items)
    )

    _append_approval_chat_message(
        state=state,
        role="assistant",
        content=state.get("assistant_message"),
        message_type="chilling_equipment_complete_summary",
    )
    state["last_user_message"] = None
    state["current_response_intent"] = None
    state["next_action"] = "record_approval"
    return state


def create_safety_point_graph():
    """Build and return the compiled safety point approval graph."""
    graph = StateGraph(SafetyPointApprovalState)

    def check_screening_complete(
        state: SafetyPointApprovalState,
    ) -> SafetyPointApprovalState:
        """Confirm that Food Safety Profile screening is complete."""
        business_profile_id = state.get("business_profile_id")

        if business_profile_id is None:
            state["status"] = "blocked"
            state["next_action"] = "missing_business_profile"
            state["assistant_message"] = (
                "No business profile is linked to this approval workflow."
            )
            return state

        db = SessionLocal()

        try:
            status = get_screening_completion_status(db, business_profile_id)
        finally:
            db.close()

        state["active_condition_count"] = status["active_condition_count"]
        state["completed_active_condition_count"] = (
            status["completed_active_condition_count"]
        )

        if not status["is_complete"]:
            state["status"] = "blocked"
            state["next_action"] = "screening_incomplete"
            state["assistant_message"] = (
                "Complete the Food Safety Profile screening before starting the "
                "safety point approval workflow."
            )
            return state

        state["status"] = "in_progress"
        state["next_action"] = "load_relevant_safety_points"
        state["assistant_message"] = None
        return state

    def load_relevant_safety_points(
        state: SafetyPointApprovalState,
    ) -> SafetyPointApprovalState:
        """Load relevant safety points using stored screening condition values."""
        if state.get("status") == "blocked":
            return state

        business_profile_id = state.get("business_profile_id")

        if business_profile_id is None:
            state["status"] = "blocked"
            state["next_action"] = "missing_business_profile"
            state["assistant_message"] = (
                "No business profile is linked to this approval workflow."
            )
            return state

        db = SessionLocal()

        try:
            condition_values = get_condition_values_for_profile(db, business_profile_id)
            relevant_safety_points = get_relevant_safety_points_for_profile(
                db,
                business_profile_id,
            )
            business_context = get_business_context(
                db=db,
                business_profile_id=business_profile_id,
                user_id=state.get("user_id"),
            )
        finally:
            db.close()

        state["condition_values"] = condition_values
        state["business_context"] = business_context
        state["safety_points_list"] = relevant_safety_points
        state["relevant_safety_point_count"] = len(relevant_safety_points)
        state.setdefault("current_safety_point_index", 0)
        state.setdefault("approved_safety_point_ids", [])
        state.setdefault("current_q_and_a_messages", [])
        state.setdefault("approval_chat_history", [])
        state.setdefault("clarification_turn_counts", {})
        state.setdefault("additional_answers", {})
        state.setdefault("awaiting_additional_answers", False)
        state.setdefault("last_safety_point_prompt_intro_index", None)
        state.setdefault("last_safety_point_prompt_verb_index", None)
        state.setdefault("last_review_message", None)
        state.setdefault("last_confirmation_message", None)

        if not relevant_safety_points:
            state["status"] = "completed"
            state["next_action"] = "complete_approval"
            state["assistant_message"] = (
                "No relevant safety points were found for this Food Safety Profile."
            )
            return state

        state["status"] = "in_progress"
        state["next_action"] = "present_safety_point"
        state["assistant_message"] = None
        return state

    def present_safety_point(
        state: SafetyPointApprovalState,
    ) -> SafetyPointApprovalState:
        """Prepare the current safety point for presentation."""
        _set_current_safety_point_context(state)

        current_safety_point = state.get("current_safety_point")
        if current_safety_point is None:
            state["status"] = "completed"
            state["next_action"] = "complete_approval"
            state["assistant_message"] = (
                "There are no more safety points to approve."
            )
            return state

        state["status"] = "in_progress"
        state["next_action"] = "awaiting_user_message"
        state["assistant_message"] = "Review the current safety point."

        safety_point_id = current_safety_point.get("safety_point_id")
        safety_point_text = (
            current_safety_point.get("text")
            or current_safety_point.get("safety_point_text")
        )

        if not state.get("last_user_message"):
            safety_point_prompt = _build_safety_point_prompt(state)

            state["assistant_message"] = safety_point_prompt

            _append_approval_chat_message(
                state=state,
                role="assistant",
                content=safety_point_prompt,
                message_type="safety_point_presented",
                safety_point_id=safety_point_id,
                safety_point_view=state.get("current_safety_point_view"),
            )

        return state

    def interpret_safety_point_response(
        state: SafetyPointApprovalState,
    ) -> SafetyPointApprovalState:
        """Classify the admin's free-text response for workflow routing."""
        user_message = state.get("last_user_message")
        current_safety_point = state.get("current_safety_point")
        current_additional_question = (
            state.get("current_additional_question")
            if state.get("awaiting_additional_answers")
            else None
        )

        _append_approval_chat_message(
            state=state,
            role="user",
            content=user_message,
            message_type="user_message",
        )

        if not user_message:
            state["current_response_intent"] = "unclear"
            state["next_action"] = "unclear"
            state["assistant_message"] = (
                "Please clarify whether you are approving the displayed safety "
                "point, asking a question, answering a required additional "
                "question, or stating that the business uses a different method."
            )
            return state

        if current_safety_point is None:
            state["current_response_intent"] = "unclear"
            state["next_action"] = "unclear"
            state["assistant_message"] = (
                "There is no current safety point to process."
            )
            return state

        safety_point_text = (
            current_safety_point.get("text")
            or current_safety_point.get("safety_point_text")
            or ""
        )

        if _is_chilling_equipment_question(current_additional_question):
            state["current_response_intent"] = "additional_answer"
            state["next_action"] = "additional_answer"
            return state

        adapter = get_llm_adapter()
        result = adapter.interpret_safety_point_response(
            safety_point_text=safety_point_text,
            user_message=user_message,
            pending_additional_question=current_additional_question,
            conversation_history=state.get("current_q_and_a_messages", []),
        )

        intent = result.get("action", "unclear")

        state["current_response_intent"] = intent
        state["next_action"] = intent
        state["assistant_message"] = result.get("assistant_message")

        if intent == "different_method_declared":
            state["different_method_declared_message"] = user_message
            state["assistant_message"] = (
                result.get("assistant_message")
                or (
                    "Alternative-method assessment is not available in this "
                    "version. This safety point will remain unapproved and "
                    "will be shown again later."
                )
            )
            _append_approval_chat_message(
                state=state,
                role="assistant",
                content=state.get("assistant_message"),
                message_type="different_method_declared",
            )

        if intent == "unclear" and not state.get("assistant_message"):
            state["assistant_message"] = (
                "Please clarify whether you are approving the displayed safety "
                "point, asking a question, answering a required additional "
                "question, or stating that the business uses a different method."
            )

        if intent == "unclear":
            _append_approval_chat_message(
                state=state,
                role="assistant",
                content=state.get("assistant_message"),
                message_type="unclear_response",
            )

        return state


    def answer_clarification(
        state: SafetyPointApprovalState,
    ) -> SafetyPointApprovalState:
        """Answer an admin's clarification question in the current workflow context."""
        user_message = state.get("last_user_message")
        current_safety_point = state.get("current_safety_point")
        awaiting_additional_answers = state.get("awaiting_additional_answers", False)
        current_additional_question = state.get("current_additional_question")

        if not user_message:
            state["assistant_message"] = (
                "Please ask a question about the current safety point or required "
                "additional question."
            )
            state["next_action"] = "awaiting_user_message"
            return state

        if current_safety_point is None:
            state["assistant_message"] = (
                "There is no current safety point to explain."
            )
            state["next_action"] = "awaiting_user_message"
            return state

        safety_point_id = current_safety_point.get("safety_point_id")
        clarification_turn_counts = state.setdefault(
            "clarification_turn_counts",
            {},
        )

        clarification_key = safety_point_id
        if awaiting_additional_answers and current_additional_question:
            question_key = current_additional_question.get("question_key")
            if question_key:
                clarification_key = f"{safety_point_id}:{question_key}"

        current_clarification_count = clarification_turn_counts.get(
            clarification_key,
            0,
        )

        if current_clarification_count >= MAX_CLARIFICATION_TURNS_PER_SAFETY_POINT:
            if awaiting_additional_answers:
                state["assistant_message"] = (
                    "This required additional question still needs an answer, but "
                    "the clarification limit for this pass has been reached. The "
                    "safety point will remain unapproved and will be shown again later."
                )
            else:
                state["assistant_message"] = (
                    "This safety point still needs approval, but the clarification "
                    "limit for this pass has been reached. It will remain "
                    "unapproved and will be shown again later."
                )

            _append_approval_chat_message(
                state=state,
                role="assistant",
                content=state.get("assistant_message"),
                message_type="clarification_limit_reached",
            )
            state["last_user_message"] = None
            state["next_action"] = "move_to_next_safety_point"
            state["current_response_intent"] = "clarification_limit_reached"
            return state

        safety_point_text = (
            current_safety_point.get("text")
            or current_safety_point.get("safety_point_text")
            or ""
        )

        adapter = get_llm_adapter()

        if awaiting_additional_answers and current_additional_question:
            additional_question_text = current_additional_question.get(
                "question_text",
                "Please answer the required additional question.",
            )
            answer = adapter.answer_additional_question_clarification(
                safety_point_text=safety_point_text,
                safe_method_name=current_safety_point.get("safe_method_name", ""),
                section_name=current_safety_point.get("section_name", ""),
                condition_values=state.get("condition_values", {}),
                additional_question_text=additional_question_text,
                user_question=user_message,
            )
        else:
            safety_point_instruction = (
                current_safety_point.get("instruction")
                or safety_point_text
            )
            safety_point_rationale = current_safety_point.get("rationale", "")
            business_context = build_relevant_prompt_context(
                state.get("business_context", {}),
                current_safety_point,
            )
            answer = adapter.answer_safety_point_question(
                safety_point_text=safety_point_text,
                safe_method_name=current_safety_point.get("safe_method_name", ""),
                section_name=current_safety_point.get("section_name", ""),
                condition_values=state.get("condition_values", {}),
                user_question=user_message,
                safety_point_instruction=safety_point_instruction,
                safety_point_rationale=safety_point_rationale,
                business_context=business_context,
                relevant_facts=business_context.get("relevant_facts", []),
            )

        messages = state.setdefault("current_q_and_a_messages", [])
        messages.append(
            {
                "role": "user",
                "content": user_message,
            }
        )
        messages.append(
            {
                "role": "assistant",
                "content": answer,
            }
        )

        clarification_turn_counts[clarification_key] = (
            current_clarification_count + 1
        )

        state["assistant_message"] = answer
        _append_approval_chat_message(
            state=state,
            role="assistant",
            content=answer,
            message_type="clarification_answer",
        )
        state["last_user_message"] = None
        state["next_action"] = "awaiting_user_message"
        state["current_response_intent"] = None

        _set_current_safety_point_context(state)

        return state    

    def collect_chilling_equipment(
        state: SafetyPointApprovalState,
    ) -> SafetyPointApprovalState:
        """Collect chilling equipment details for safety point 4.1.1.3."""
        user_message = state.get("last_user_message")
        current_question = state.get("current_additional_question")

        if not _is_chilling_equipment_question(current_question):
            state["assistant_message"] = (
                "The current additional question is not a chilling equipment "
                "setup question."
            )
            state["last_user_message"] = None
            state["next_action"] = "awaiting_user_message"
            state["current_response_intent"] = None
            return state

        flow = _get_or_create_chilling_equipment_flow(state)
        adapter = get_llm_adapter()

        if not user_message:
            if flow.get("confirmed_equipment_names"):
                flow["phase"] = "collect_details"
                next_index = _find_next_incomplete_chilling_equipment_index(flow)

                if next_index is not None:
                    flow["current_item_index"] = next_index
                    current_item = flow["items"][next_index]
                    state["assistant_message"] = _build_chilling_equipment_detail_prompt(
                        current_item["equipment_name"]
                    )
                else:
                    return _finalize_chilling_equipment_flow(
                        state=state,
                        flow=flow,
                    )
            else:
                flow["phase"] = "collect_names"
                state["assistant_message"] = _build_chilling_equipment_name_prompt()

            _append_approval_chat_message(
                state=state,
                role="assistant",
                content=state.get("assistant_message"),
                message_type="chilling_equipment_question",
            )
            state["next_action"] = "awaiting_user_message"
            state["current_response_intent"] = None
            return state

        phase = flow.get("phase", "collect_names")

        if phase == "collect_names":
            result = adapter.extract_chilling_equipment_names(user_message)

            if result.get("no_chilling_equipment_declared"):
                additional_answers = state.setdefault("additional_answers", {})
                additional_answers[CHILLING_EQUIPMENT_QUESTION_KEY] = (
                    "The business stated that it does not use chilling equipment."
                )

                state["awaiting_additional_answers"] = False
                state["current_additional_question_index"] = None
                state["current_additional_question"] = None
                state["assistant_message"] = (
                    "No chilling equipment items will be recorded because the "
                    "business stated that it does not use chilling equipment."
                )
                _append_approval_chat_message(
                    state=state,
                    role="assistant",
                    content=state.get("assistant_message"),
                    message_type="chilling_equipment_no_equipment_declared",
                )
                state["last_user_message"] = None
                state["current_response_intent"] = None
                state["next_action"] = "record_approval"
                return state

            flow["name_attempt_count"] = flow.get("name_attempt_count", 0) + 1

            if result.get("has_usable_equipment_names"):
                captured_names = result.get("equipment_names", [])
                flow["captured_equipment_names"] = captured_names
                flow["phase"] = "confirm_names"

                state["assistant_message"] = (
                    _build_chilling_equipment_confirmation_message(captured_names)
                )
                _append_approval_chat_message(
                    state=state,
                    role="assistant",
                    content=state.get("assistant_message"),
                    message_type="chilling_equipment_names_captured",
                )
                state["last_user_message"] = None
                state["current_response_intent"] = None
                state["next_action"] = "awaiting_user_message"
                return state

            if flow["name_attempt_count"] >= MAX_CHILLING_EQUIPMENT_NAME_ATTEMPTS:
                state["assistant_message"] = _build_chilling_equipment_no_names_message()
                flow["phase"] = "collect_names"
                flow["name_attempt_count"] = 0
                flow["captured_equipment_names"] = []
                flow["confirmed_equipment_names"] = []
                flow["items"] = []

                _append_approval_chat_message(
                    state=state,
                    role="assistant",
                    content=state.get("assistant_message"),
                    message_type="chilling_equipment_names_failed",
                )
                state["last_user_message"] = None
                state["current_response_intent"] = None
                state["next_action"] = "move_to_next_safety_point"
                return state

            state["assistant_message"] = (
                result.get("assistant_message")
                or _build_chilling_equipment_name_prompt()
            )
            _append_approval_chat_message(
                state=state,
                role="assistant",
                content=state.get("assistant_message"),
                message_type="chilling_equipment_names_retry",
            )
            state["last_user_message"] = None
            state["current_response_intent"] = None
            state["next_action"] = "awaiting_user_message"
            return state

        if phase == "confirm_names":
            captured_names = flow.get("captured_equipment_names", [])
            result = adapter.interpret_chilling_equipment_name_confirmation(
                captured_equipment_names=captured_names,
                user_message=user_message,
            )

            if result.get("confirmed") and captured_names:
                flow["confirmed_equipment_names"] = captured_names
                flow["items"] = _build_chilling_equipment_items(captured_names)
                flow["current_item_index"] = 0
                flow["phase"] = "collect_details"

                current_item = flow["items"][0]
                state["assistant_message"] = _build_chilling_equipment_detail_prompt(
                    current_item["equipment_name"]
                )
                _append_approval_chat_message(
                    state=state,
                    role="assistant",
                    content=state.get("assistant_message"),
                    message_type="chilling_equipment_detail_question",
                )
                state["last_user_message"] = None
                state["current_response_intent"] = None
                state["next_action"] = "awaiting_user_message"
                return state

            flow["name_attempt_count"] = flow.get("name_attempt_count", 0) + 1

            corrected_names = result.get("corrected_equipment_names", [])

            if corrected_names and flow["name_attempt_count"] < MAX_CHILLING_EQUIPMENT_NAME_ATTEMPTS:
                flow["captured_equipment_names"] = corrected_names
                state["assistant_message"] = (
                    _build_chilling_equipment_confirmation_message(corrected_names)
                )
                _append_approval_chat_message(
                    state=state,
                    role="assistant",
                    content=state.get("assistant_message"),
                    message_type="chilling_equipment_names_corrected",
                )
                state["last_user_message"] = None
                state["current_response_intent"] = None
                state["next_action"] = "awaiting_user_message"
                return state

            if flow["name_attempt_count"] >= MAX_CHILLING_EQUIPMENT_NAME_ATTEMPTS:
                state["assistant_message"] = _build_chilling_equipment_no_names_message()
                flow["phase"] = "collect_names"
                flow["name_attempt_count"] = 0
                flow["captured_equipment_names"] = []
                flow["confirmed_equipment_names"] = []
                flow["items"] = []

                _append_approval_chat_message(
                    state=state,
                    role="assistant",
                    content=state.get("assistant_message"),
                    message_type="chilling_equipment_names_failed",
                )
                state["last_user_message"] = None
                state["current_response_intent"] = None
                state["next_action"] = "move_to_next_safety_point"
                return state

            state["assistant_message"] = (
                result.get("assistant_message")
                or _build_chilling_equipment_corrected_list_prompt()
            )
            _append_approval_chat_message(
                state=state,
                role="assistant",
                content=state.get("assistant_message"),
                message_type="chilling_equipment_names_confirmation_retry",
            )
            state["last_user_message"] = None
            state["current_response_intent"] = None
            state["next_action"] = "awaiting_user_message"
            return state

        if phase == "collect_details":
            next_index = _find_next_incomplete_chilling_equipment_index(flow)

            if next_index is None:
                return _finalize_chilling_equipment_flow(
                    state=state,
                    flow=flow,
                )

            flow["current_item_index"] = next_index
            current_item = flow["items"][next_index]
            current_item["attempt_count"] = current_item.get("attempt_count", 0) + 1

            result = adapter.interpret_chilling_equipment_details(
                equipment_name=current_item["equipment_name"],
                user_message=user_message,
                existing_details=current_item,
            )

            for field_name in (
                "equipment_type",
                "equipment_use",
                "temperature_check_method",
            ):
                if result.get(field_name):
                    current_item[field_name] = result[field_name]

            current_item["is_complete"] = bool(result.get("is_complete"))

            if current_item["is_complete"]:
                following_index = _find_next_incomplete_chilling_equipment_index(flow)

                if following_index is not None:
                    flow["current_item_index"] = following_index
                    following_item = flow["items"][following_index]
                    state["assistant_message"] = _build_chilling_equipment_detail_prompt(
                        following_item["equipment_name"]
                    )
                    _append_approval_chat_message(
                        state=state,
                        role="assistant",
                        content=state.get("assistant_message"),
                        message_type="chilling_equipment_detail_question",
                    )
                    state["last_user_message"] = None
                    state["current_response_intent"] = None
                    state["next_action"] = "awaiting_user_message"
                    return state

                state["last_user_message"] = None
                state["current_response_intent"] = None
                state["next_action"] = "collect_chilling_equipment"
                return state

            if current_item["attempt_count"] >= MAX_CHILLING_EQUIPMENT_DETAIL_ATTEMPTS:
                current_item["skipped_in_current_pass"] = True
                following_index = _find_next_incomplete_chilling_equipment_index(flow)

                skipped_message = _build_chilling_equipment_item_skipped_message(
                    current_item["equipment_name"]
                )

                if following_index is not None:
                    flow["current_item_index"] = following_index
                    following_item = flow["items"][following_index]
                    state["assistant_message"] = (
                        f"{skipped_message}\n\n"
                        f"{_build_chilling_equipment_detail_prompt(following_item['equipment_name'])}"
                    )
                    _append_approval_chat_message(
                        state=state,
                        role="assistant",
                        content=state.get("assistant_message"),
                        message_type="chilling_equipment_item_skipped",
                    )
                    state["last_user_message"] = None
                    state["current_response_intent"] = None
                    state["next_action"] = "awaiting_user_message"
                    return state

                state["assistant_message"] = skipped_message
                _append_approval_chat_message(
                    state=state,
                    role="assistant",
                    content=state.get("assistant_message"),
                    message_type="chilling_equipment_item_skipped",
                )
                state["last_user_message"] = None
                state["current_response_intent"] = None
                state["next_action"] = "collect_chilling_equipment"
                return state

            state["assistant_message"] = _build_chilling_equipment_missing_detail_prompt(
                equipment_name=current_item["equipment_name"],
                assistant_message=result.get("assistant_message"),
            )
            _append_approval_chat_message(
                state=state,
                role="assistant",
                content=state.get("assistant_message"),
                message_type="chilling_equipment_detail_retry",
            )
            state["last_user_message"] = None
            state["current_response_intent"] = None
            state["next_action"] = "awaiting_user_message"
            return state

        state["assistant_message"] = _build_chilling_equipment_name_prompt()
        flow["phase"] = "collect_names"
        state["last_user_message"] = None
        state["current_response_intent"] = None
        state["next_action"] = "awaiting_user_message"
        return state


    def collect_additional_answers(
        state: SafetyPointApprovalState,
    ) -> SafetyPointApprovalState:
        """Collect an admin's answer to a required additional question."""
        user_message = state.get("last_user_message")
        current_question = state.get("current_additional_question")
        pending_questions = state.get("pending_additional_questions", [])

        if not state.get("awaiting_additional_answers"):
            state["assistant_message"] = (
                "There is no required additional question awaiting an answer."
            )
            state["last_user_message"] = None
            state["next_action"] = "awaiting_user_message"
            state["current_response_intent"] = None
            return state

        if not pending_questions:
            state["awaiting_additional_answers"] = False
            state["current_additional_question_index"] = None
            state["current_additional_question"] = None
            state["last_user_message"] = None
            state["next_action"] = "record_approval"
            state["current_response_intent"] = None
            return state

        if current_question is None:
            state["current_additional_question_index"] = 0
            state["current_additional_question"] = pending_questions[0]
            current_question = state["current_additional_question"]

        if not user_message:
            question_text = current_question.get(
                "question_text",
                "Please answer the required additional question.",
            )
            state["assistant_message"] = _build_additional_question_prompt(
                question_text=question_text,
            )
            _append_approval_chat_message(
                state=state,
                role="assistant",
                content=state.get("assistant_message"),
                message_type="additional_question",
            )
            state["next_action"] = "awaiting_user_message"
            return state

        question_key = current_question.get("question_key")

        if not question_key:
            state["assistant_message"] = (
                "The current additional question is missing a question key."
            )
            state["last_user_message"] = None
            state["next_action"] = "awaiting_user_message"
            state["current_response_intent"] = None
            return state

        additional_answers = state.setdefault("additional_answers", {})
        additional_answers[question_key] = user_message

        _set_current_safety_point_context(state)

        remaining_questions = state.get("pending_additional_questions", [])

        if remaining_questions:
            state["awaiting_additional_answers"] = True
            state["current_additional_question_index"] = 0
            state["current_additional_question"] = remaining_questions[0]

            question_text = remaining_questions[0].get(
                "question_text",
                "Please answer the next required additional question.",
            )
            state["assistant_message"] = _build_additional_question_prompt(
                question_text=question_text,
                is_next_question=True,
            )
            _append_approval_chat_message(
                state=state,
                role="assistant",
                content=state.get("assistant_message"),
                message_type="additional_question",
            )
            state["next_action"] = "awaiting_user_message"
        else:
            state["awaiting_additional_answers"] = False
            state["current_additional_question_index"] = None
            state["current_additional_question"] = None
            state["assistant_message"] = "Additional information recorded."
            _append_approval_chat_message(
                state=state,
                role="assistant",
                content=state.get("assistant_message"),
                message_type="additional_answer_recorded",
            )
            state["next_action"] = "record_approval"

        state["last_user_message"] = None
        state["current_response_intent"] = None
        return state

    def record_approval(
        state: SafetyPointApprovalState,
    ) -> SafetyPointApprovalState:
        """Record approval of the displayed standard SFBB safety point."""
        business_profile_id = state.get("business_profile_id")
        user_id = state.get("user_id")
        current_safety_point = state.get("current_safety_point")

        if state.get("different_method_declared_message"):
            state["assistant_message"] = (
                "Approval cannot be recorded because the business has stated "
                "that it uses a different method. Alternative-method assessment "
                "is not available in this version."
            )
            state["next_action"] = "awaiting_user_message"
            state["current_response_intent"] = None
            return state

        if current_safety_point is None:
            state["assistant_message"] = (
                "There is no current safety point to approve."
            )
            state["next_action"] = "awaiting_user_message"
            state["current_response_intent"] = None
            return state

        if business_profile_id is None or user_id is None:
            state["assistant_message"] = (
                "Approval cannot be recorded because the business profile or "
                "user context is missing."
            )
            state["next_action"] = "awaiting_user_message"
            state["current_response_intent"] = None
            return state

        _set_current_safety_point_context(state)
        pending_questions = state.get("pending_additional_questions", [])

        if pending_questions:
            state["awaiting_additional_answers"] = True
            state["current_additional_question_index"] = 0
            state["current_additional_question"] = pending_questions[0]
            state["current_safety_point_view"] = _build_current_safety_point_view(state)

            current_question = pending_questions[0]

            if _is_chilling_equipment_question(current_question):
                flow = _get_or_create_chilling_equipment_flow(state)

                if flow.get("confirmed_equipment_names"):
                    flow["phase"] = "collect_details"
                    next_index = _find_next_incomplete_chilling_equipment_index(
                        flow
                    )

                    if next_index is not None:
                        flow["current_item_index"] = next_index
                        current_item = flow["items"][next_index]
                        confirmed_lines = "\n".join(
                            f"{index}. {equipment_name}"
                            for index, equipment_name in enumerate(
                                flow.get("confirmed_equipment_names", []),
                                start=1,
                            )
                        )

                        state["assistant_message"] = (
                            "The following chilling equipment units were "
                            "previously confirmed for this safety point:\n\n"
                            f"{confirmed_lines}\n\n"
                            "Some required information is still missing. I will "
                            "ask only for the missing details for the remaining "
                            "equipment items.\n\n"
                            f"{_build_chilling_equipment_detail_prompt(current_item['equipment_name'])}"
                        )
                    else:
                        state["assistant_message"] = (
                            "All previously confirmed chilling equipment items "
                            "appear to have complete details. Please send your "
                            "approval again so the safety point can be recorded."
                        )
                else:
                    flow["phase"] = "collect_names"
                    state["assistant_message"] = (
                        _build_chilling_equipment_name_prompt()
                    )

                _append_approval_chat_message(
                    state=state,
                    role="assistant",
                    content=state.get("assistant_message"),
                    message_type="chilling_equipment_question",
                )
                state["last_user_message"] = None
                state["next_action"] = "awaiting_user_message"
                state["current_response_intent"] = None
                return state

            question_text = current_question.get(
                "question_text",
                "Please answer the required additional question before approval.",
            )
            state["assistant_message"] = _build_additional_question_prompt(
                question_text=question_text,
            )
            _append_approval_chat_message(
                state=state,
                role="assistant",
                content=state.get("assistant_message"),
                message_type="additional_question",
            )
            state["last_user_message"] = None
            state["next_action"] = "awaiting_user_message"
            state["current_response_intent"] = None
            return state

        db = SessionLocal()

        try:
            approval_record = record_approved_safety_point(
                db=db,
                business_profile_id=business_profile_id,
                user_id=user_id,
                safety_point=current_safety_point,
                additional_answers=state.get("additional_answers", {}),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        approved_ids = state.setdefault("approved_safety_point_ids", [])
        safety_point_id = current_safety_point.get("safety_point_id")

        if safety_point_id and safety_point_id not in approved_ids:
            approved_ids.append(safety_point_id)

        state["last_approved_safety_point_record"] = approval_record
        state["assistant_message"] = "Safety point approval recorded."
        _append_approval_chat_message(
            state=state,
            role="assistant",
            content=state.get("assistant_message"),
            message_type="approval_recorded",
        )

        state["awaiting_additional_answers"] = False
        state["last_user_message"] = None
        state["current_response_intent"] = None
        state["next_action"] = "move_to_next_safety_point"
        return state

    def move_to_next_safety_point(
        state: SafetyPointApprovalState,
    ) -> SafetyPointApprovalState:
        """Advance to the next unapproved safety point."""
        safety_points = state.get("safety_points_list", [])
        current_index = state.get("current_safety_point_index", 0)
        approved_ids = state.get("approved_safety_point_ids", [])

        state["last_user_message"] = None
        state["current_response_intent"] = None
        state["current_q_and_a_messages"] = []
        state["additional_answers"] = {}
        state["pending_additional_questions"] = []
        state["current_additional_question_index"] = None
        state["current_additional_question"] = None
        state["awaiting_additional_answers"] = False
        state["different_method_declared_message"] = None

        next_unapproved_index = None

        for index in range(current_index + 1, len(safety_points)):
            safety_point_id = safety_points[index].get("safety_point_id")

            if safety_point_id not in approved_ids:
                next_unapproved_index = index
                break

        if next_unapproved_index is None:
            for index, safety_point in enumerate(safety_points):
                safety_point_id = safety_point.get("safety_point_id")

                if safety_point_id not in approved_ids:
                    next_unapproved_index = index
                    break

        if next_unapproved_index is None:
            state["current_safety_point_index"] = len(safety_points)
            state["current_safety_point"] = None
            state["current_safety_point_view"] = _build_current_safety_point_view(
                state
            )
            state["status"] = "completed"
            state["next_action"] = "complete_approval"
            state["assistant_message"] = (
                "All relevant safety points have been approved."
            )
            return state

        if next_unapproved_index <= current_index:
            clarification_turn_counts = state.setdefault(
                "clarification_turn_counts",
                {},
            )

            for safety_point in safety_points:
                safety_point_id = safety_point.get("safety_point_id")

                if safety_point_id not in approved_ids:
                    clarification_turn_counts[safety_point_id] = 0

        state["current_safety_point_index"] = next_unapproved_index
        _set_current_safety_point_context(state)

        state["status"] = "in_progress"
        state["next_action"] = "awaiting_user_message"
        state["assistant_message"] = (
            "Review the current safety point."
        )

        return state


    def complete_approval(
        state: SafetyPointApprovalState,
    ) -> SafetyPointApprovalState:
        """Mark the workflow state as completed."""
        state["status"] = "completed"
        state["next_action"] = "complete"
        if not state.get("assistant_message"):
            state["assistant_message"] = (
                "All relevant safety points have been approved."
            )
        _append_approval_chat_message(
            state=state,
            role="assistant",
            content=state.get("assistant_message"),
            message_type="workflow_completed",
            safety_point_id=None,
        )
        return state

    def route_after_screening_check(state: SafetyPointApprovalState) -> str:
        if state.get("status") == "blocked":
            return END

        return "load_relevant_safety_points"

    def route_after_relevant_safety_points_loaded(
        state: SafetyPointApprovalState,
    ) -> str:
        if state.get("status") == "completed":
            return "complete_approval"

        return "present_safety_point"

    def route_after_present(state: SafetyPointApprovalState) -> str:
        if state.get("status") == "completed":
            return "complete_approval"

        if state.get("last_user_message"):
            return "interpret_safety_point_response"

        return END

    def route_after_interpret(state: SafetyPointApprovalState) -> str:
        intent = state.get("current_response_intent")

        if intent == "clarification_request":
            return "answer_clarification"

        if intent == "additional_answer":
            current_question = state.get("current_additional_question")
            if _is_chilling_equipment_question(current_question):
                return "collect_chilling_equipment"

            return "collect_additional_answers"

        if intent == "approval":
            return "record_approval"

        if intent == "different_method_declared":
            return "move_to_next_safety_point"

        return END


    def route_after_answer_clarification(state: SafetyPointApprovalState) -> str:
        if state.get("next_action") == "move_to_next_safety_point":
            return "move_to_next_safety_point"

        return END


    def route_after_collect_additional_answers(
        state: SafetyPointApprovalState,
    ) -> str:
        if state.get("next_action") == "record_approval":
            return "record_approval"

        return END

    def route_after_collect_chilling_equipment(
        state: SafetyPointApprovalState,
    ) -> str:
        next_action = state.get("next_action")

        if next_action == "record_approval":
            return "record_approval"

        if next_action == "move_to_next_safety_point":
            return "move_to_next_safety_point"

        if next_action == "collect_chilling_equipment":
            return "collect_chilling_equipment"

        return END

    def route_after_record_approval(state: SafetyPointApprovalState) -> str:
        if state.get("next_action") == "move_to_next_safety_point":
            return "move_to_next_safety_point"

        return END


    graph.add_node("check_screening_complete", check_screening_complete)
    graph.add_node("load_relevant_safety_points", load_relevant_safety_points)
    graph.add_node("present_safety_point", present_safety_point)
    graph.add_node("interpret_safety_point_response", interpret_safety_point_response)
    graph.add_node("answer_clarification", answer_clarification)
    graph.add_node("collect_additional_answers", collect_additional_answers)
    graph.add_node("collect_chilling_equipment", collect_chilling_equipment)
    graph.add_node("record_approval", record_approval)
    graph.add_node("move_to_next_safety_point", move_to_next_safety_point)
    graph.add_node("complete_approval", complete_approval)

    graph.set_entry_point("check_screening_complete")

    graph.add_conditional_edges(
        "check_screening_complete",
        route_after_screening_check,
        {
            "load_relevant_safety_points": "load_relevant_safety_points",
            END: END,
        },
    )

    graph.add_conditional_edges(
        "load_relevant_safety_points",
        route_after_relevant_safety_points_loaded,
        {
            "present_safety_point": "present_safety_point",
            "complete_approval": "complete_approval",
        },
    )

    graph.add_conditional_edges(
        "present_safety_point",
        route_after_present,
        {
            "interpret_safety_point_response": "interpret_safety_point_response",
            "complete_approval": "complete_approval",
            END: END,
        },
    )

    graph.add_conditional_edges(
        "interpret_safety_point_response",
        route_after_interpret,
        {
            "answer_clarification": "answer_clarification",
            "collect_additional_answers": "collect_additional_answers",
            "collect_chilling_equipment": "collect_chilling_equipment",
            "record_approval": "record_approval",
            "move_to_next_safety_point": "move_to_next_safety_point",
            END: END,
        },
    )

    graph.add_conditional_edges(
        "answer_clarification",
        route_after_answer_clarification,
        {
            "move_to_next_safety_point": "move_to_next_safety_point",
            END: END,
        },
    )
    graph.add_conditional_edges(
        "collect_additional_answers",
        route_after_collect_additional_answers,
        {
            "record_approval": "record_approval",
            END: END,
        },
    )

    graph.add_conditional_edges(
        "collect_chilling_equipment",
        route_after_collect_chilling_equipment,
        {
            "record_approval": "record_approval",
            "move_to_next_safety_point": "move_to_next_safety_point",
            "collect_chilling_equipment": "collect_chilling_equipment",
            END: END,
        },
    )

    graph.add_conditional_edges(
        "record_approval",
        route_after_record_approval,
        {
            "move_to_next_safety_point": "move_to_next_safety_point",
            END: END,
        },
    )
    graph.add_conditional_edges(
        "move_to_next_safety_point",
        route_after_relevant_safety_points_loaded,
        {
            "present_safety_point": "present_safety_point",
            "complete_approval": "complete_approval",
        },
    )
    graph.add_edge("complete_approval", END)

    return graph.compile()


safety_point_graph = create_safety_point_graph()