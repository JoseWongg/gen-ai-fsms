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
    condition_values: Dict[str, str]
    active_condition_count: int
    completed_active_condition_count: int
    relevant_safety_point_count: int


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
            "pending_additional_questions": [],
            "current_additional_question": None,
            "progress": progress,
        }

    current_additional_question = _get_current_additional_question(state)
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

    state["pending_additional_questions"] = required_questions

    if required_questions:
        current_question_index = state.get("current_additional_question_index")

        if (
            current_question_index is None
            or current_question_index < 0
            or current_question_index >= len(required_questions)
        ):
            state["current_additional_question_index"] = 0
    else:
        state["current_additional_question_index"] = None

    state["current_additional_question"] = _get_current_additional_question(state)
    state["current_safety_point_view"] = _build_current_safety_point_view(state)

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
        finally:
            db.close()

        state["condition_values"] = condition_values
        state["safety_points_list"] = relevant_safety_points
        state["relevant_safety_point_count"] = len(relevant_safety_points)
        state.setdefault("current_safety_point_index", 0)
        state.setdefault("approved_safety_point_ids", [])
        state.setdefault("current_q_and_a_messages", [])
        state.setdefault("additional_answers", {})

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
        return state

    def interpret_safety_point_response(
        state: SafetyPointApprovalState,
    ) -> SafetyPointApprovalState:
        """Classify the admin's free-text response for workflow routing."""
        user_message = state.get("last_user_message")
        current_safety_point = state.get("current_safety_point")
        current_additional_question = state.get("current_additional_question")

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
                    "version. Approval can only be recorded if the business "
                    "follows the displayed SFBB safety point."
                )
            )

        if intent == "unclear" and not state.get("assistant_message"):
            state["assistant_message"] = (
                "Please clarify whether you are approving the displayed safety "
                "point, asking a question, answering a required additional "
                "question, or stating that the business uses a different method."
            )

        return state

    def answer_clarification(
        state: SafetyPointApprovalState,
    ) -> SafetyPointApprovalState:
        """Placeholder node for clarification answer handling."""
        state["next_action"] = "awaiting_user_message"
        return state

    def collect_additional_answers(
        state: SafetyPointApprovalState,
    ) -> SafetyPointApprovalState:
        """Placeholder node for required additional answer collection."""
        state["next_action"] = "awaiting_user_message"
        return state

    def record_approval(
        state: SafetyPointApprovalState,
    ) -> SafetyPointApprovalState:
        """Placeholder node for recording standard-method approval."""
        state["next_action"] = "move_to_next_safety_point"
        return state

    def move_to_next_safety_point(
        state: SafetyPointApprovalState,
    ) -> SafetyPointApprovalState:
        """Placeholder node for advancing after approval."""
        state["next_action"] = "present_safety_point"
        return state

    def complete_approval(
        state: SafetyPointApprovalState,
    ) -> SafetyPointApprovalState:
        """Mark the workflow state as completed."""
        state["status"] = "completed"
        state["next_action"] = "complete"
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
            return END

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
            END: END,
        },
    )

    graph.add_edge("answer_clarification", END)
    graph.add_edge("collect_additional_answers", END)
    graph.add_edge("record_approval", "move_to_next_safety_point")
    graph.add_edge("move_to_next_safety_point", END)
    graph.add_edge("complete_approval", END)

    return graph.compile()


safety_point_graph = create_safety_point_graph()