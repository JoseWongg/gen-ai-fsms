"""
LangGraph workflow for the safety point approval flow.

This graph coordinates the approval workflow for safety points selected from
the completed Food Safety Profile screening. It is designed as a controlled
workflow: the LLM may classify free-text responses and answer clarification
questions, but it must not approve safety points or assess alternative methods.
"""

from typing import Any, Dict, List, Optional, TypedDict
from langgraph.graph import END, StateGraph

from gen_ai_fsms.ai.adapter import get_llm_adapter
from gen_ai_fsms.db.session import SessionLocal

from gen_ai_fsms.services.safety_point_approval_service import (
    get_condition_values_for_profile,
    get_relevant_safety_points_for_profile,
    get_screening_completion_status,
    record_approved_safety_point,
)


MAX_CLARIFICATION_TURNS_PER_SAFETY_POINT = 3


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
    active_condition_count: int
    completed_active_condition_count: int
    relevant_safety_point_count: int
    last_approved_safety_point_record: Dict[str, Any]


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

    return {
        "safety_point_id": current_safety_point.get("safety_point_id"),
        "safety_point_text": (
            current_safety_point.get("text")
            or current_safety_point.get("safety_point_text")
        ),
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
        state["current_additional_question_index"] = None

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
        finally:
            db.close()

        state["condition_values"] = condition_values
        state["safety_points_list"] = relevant_safety_points
        state["relevant_safety_point_count"] = len(relevant_safety_points)
        state.setdefault("current_safety_point_index", 0)
        state.setdefault("approved_safety_point_ids", [])
        state.setdefault("current_q_and_a_messages", [])
        state.setdefault("approval_chat_history", [])
        state.setdefault("clarification_turn_counts", {})
        state.setdefault("additional_answers", {})
        state.setdefault("awaiting_additional_answers", False)

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
            safety_point_prompt = (
                "Please confirm that the business will follow this safety point, "
                "ask a clarification question, provide an answer to a required "
                "additional question, or state that the business follows a different method."
            )

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
            answer = adapter.answer_safety_point_question(
                safety_point_text=safety_point_text,
                safe_method_name=current_safety_point.get("safe_method_name", ""),
                section_name=current_safety_point.get("section_name", ""),
                condition_values=state.get("condition_values", {}),
                user_question=user_message,
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
            state["assistant_message"] = (
                "Before approval can be recorded, please answer this required "
                f"additional question: {question_text}"
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
            state["assistant_message"] = (
                "Additional information recorded. Please answer this next "
                f"required additional question: {question_text}"
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

            question_text = pending_questions[0].get(
                "question_text",
                "Please answer the required additional question before approval.",
            )
            state["assistant_message"] = (
                "Before approval can be recorded, please answer this required "
                f"additional question: {question_text}"
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