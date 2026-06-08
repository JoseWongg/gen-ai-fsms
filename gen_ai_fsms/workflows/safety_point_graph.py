"""
LangGraph workflow for the safety point approval flow.

This graph coordinates the approval workflow for safety points selected from
the completed Food Safety Profile screening. It is designed as a controlled
workflow: the LLM may classify free-text responses and answer clarification
questions, but it must not approve safety points or assess alternative methods.
"""

from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from gen_ai_fsms.db.models.condition import Condition
from gen_ai_fsms.db.models.condition_value import ConditionValue
from gen_ai_fsms.db.session import SessionLocal
from gen_ai_fsms.services.content_service import ContentService
from gen_ai_fsms.services.screening_questions import screening_questions


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
    condition_values: Dict[str, str]
    active_condition_count: int
    completed_active_condition_count: int
    relevant_safety_point_count: int


def _get_screening_completion_status(business_profile_id: int) -> Dict[str, Any]:
    db = SessionLocal()

    try:
        rows = (
            db.query(ConditionValue, Condition)
            .join(Condition, ConditionValue.condition_id == Condition.condition_id)
            .filter(ConditionValue.business_profile_id == business_profile_id)
            .all()
        )

        values_by_condition_id = {
            condition.condition_id: condition_value.value
            for condition_value, condition in rows
        }

        active_condition_ids = {
            condition_id
            for question in screening_questions
            for condition_id in question.get("sets_conditions", [])
        }

        completed_active_conditions = {
            condition_id
            for condition_id in active_condition_ids
            if values_by_condition_id.get(condition_id) in ("true", "false")
        }

        is_complete = (
            len(active_condition_ids) > 0
            and completed_active_conditions == active_condition_ids
        )

        return {
            "is_complete": is_complete,
            "active_condition_count": len(active_condition_ids),
            "completed_active_condition_count": len(completed_active_conditions),
        }

    finally:
        db.close()


def _get_condition_values_for_profile(business_profile_id: int) -> Dict[str, str]:
    db = SessionLocal()

    try:
        rows = (
            db.query(ConditionValue)
            .filter(ConditionValue.business_profile_id == business_profile_id)
            .all()
        )

        return {
            row.condition_id: row.value
            for row in rows
        }

    finally:
        db.close()


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


def _set_current_safety_point_context(
    state: SafetyPointApprovalState,
) -> SafetyPointApprovalState:
    current_safety_point = _get_current_safety_point(state)
    state["current_safety_point"] = current_safety_point

    if current_safety_point is None:
        state["pending_additional_questions"] = []
        state["current_additional_question_index"] = None
        return state

    additional_questions = current_safety_point.get("additional_questions", [])
    required_questions = [
        question for question in additional_questions
        if question.get("required") is True
    ]

    state["pending_additional_questions"] = required_questions

    if required_questions and state.get("current_additional_question_index") is None:
        state["current_additional_question_index"] = 0

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

        status = _get_screening_completion_status(business_profile_id)

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

        condition_values = _get_condition_values_for_profile(business_profile_id)
        relevant_safety_points = ContentService().get_safety_points_by_conditions(
            condition_values
        )

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
        state["assistant_message"] = None
        return state

    def interpret_safety_point_response(
        state: SafetyPointApprovalState,
    ) -> SafetyPointApprovalState:
        """
        Placeholder node for free-text response classification.

        The LLMAdapter classification call will be added in a later increment.
        """
        state["current_response_intent"] = state.get("current_response_intent")
        state["next_action"] = state.get("current_response_intent") or "unclear"
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