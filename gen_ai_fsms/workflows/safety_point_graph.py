"""
LangGraph workflow for the safety point approval flow.

This graph coordinates the approval workflow for safety points selected from
the completed Food Safety Profile screening. It is designed as a controlled
workflow: the LLM may classify free-text responses and answer clarification
questions, but it must not approve safety points or assess alternative methods.
"""

from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph


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
    pass


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
        """
        Placeholder node for screening completion checks.

        The full database-backed check will be implemented in a later Step 8
        increment. For now, this node keeps the graph structure explicit.
        """
        state.setdefault("status", "in_progress")
        state.setdefault("next_action", None)
        return state

    def load_relevant_safety_points(
        state: SafetyPointApprovalState,
    ) -> SafetyPointApprovalState:
        """
        Placeholder node for relevant safety point loading.

        The database-backed loading logic will be added in the next increment.
        """
        state.setdefault("safety_points_list", [])
        state.setdefault("current_safety_point_index", 0)
        state.setdefault("approved_safety_point_ids", [])
        state.setdefault("current_q_and_a_messages", [])
        state.setdefault("additional_answers", {})
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

    graph.add_edge("check_screening_complete", "load_relevant_safety_points")
    graph.add_edge("load_relevant_safety_points", "present_safety_point")

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