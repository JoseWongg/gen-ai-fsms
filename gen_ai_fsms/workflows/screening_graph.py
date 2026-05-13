"""
LangGraph workflow for screening questions.
Handles:
- Presenting the current question
- Interpreting free‑text answers with LLM
- Clarification loop (max 3 attempts)
- Storing condition values in the database
- Determining the next question (deterministic)
- Persisting state in onboarding_sessions
"""

import json
from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, END
from sqlalchemy.orm import Session

from gen_ai_fsms.services.screening_questions import get_next_question
from gen_ai_fsms.ai.adapter import get_llm_adapter
from gen_ai_fsms.db.session import SessionLocal
from gen_ai_fsms.db.models.condition_value import ConditionValue
from gen_ai_fsms.services.session_service import load_session, update_session


class ScreeningState(Dict[str, Any]):
    """
    State schema for the screening workflow.
    Keys:
    - business_profile_id: int
    - user_id: int
    - current_question_id: str
    - current_question_text: str
    - conditions_to_set: List[str]
    - current_answer: Optional[str]
    - conversation_history: List[dict] (for current question only)
    - clarification_attempts: int
    - condition_values: Dict[str, str] (accumulated)
    - answered_question_ids: List[str]
    - llm_result: Optional[dict]
    - next_action: str  # "next_question", "ask_clarification", "ask_again", "complete"
    - clarification_question: Optional[str]
    - session_id: Optional[int]  # onboarding_sessions row id
    """
    pass


def create_screening_graph():
    """Build and return the compiled LangGraph workflow."""
    graph = StateGraph(ScreeningState)

    # ------------------------------------------------------------------
    # Node: present_question
    # ------------------------------------------------------------------
    def present_question(state: ScreeningState) -> ScreeningState:
        """
        This node is a no-op for the backend. The frontend will display
        the question via the API; the state already contains the current
        question text and ID. We simply return the state unchanged.
        """
        #This node does not perform any action; the frontend retrieves the question via the API using the state.
        return state

    # ------------------------------------------------------------------
    # Node: llm_interpret_answer
    # ------------------------------------------------------------------
    def llm_interpret_answer(state: ScreeningState) -> ScreeningState:
        """Call the LLM adapter to interpret the user's free‑text answer."""
        question_text = state.get("current_question_text", "")
        user_answer = state.get("current_answer")
        if not user_answer:
            # No answer provided – treat as unrelated
            state["llm_result"] = {
                "action": "unrelated",
                "value": None,
                "clarification_question": None,
                "reason": "No answer provided"
            }
            return state

        conversation = state.get("conversation_history", [])
        adapter = get_llm_adapter()
        result = adapter.interpret_screening_answer(
            question=question_text,
            answer=user_answer,
            conversation_history=conversation
        )
        state["llm_result"] = result
        return state

    # ------------------------------------------------------------------
    # Node: handle_clarification
    # ------------------------------------------------------------------
    def handle_clarification(state: ScreeningState) -> ScreeningState:
        """Process the LLM result and determine the next action."""
        result = state.get("llm_result")
        if result is None:
            # Should not happen if llm_interpret_answer was called
            state["next_action"] = "ask_again"
            return state

        action = result.get("action")
        if action == "clear":
            # Store the corresponding condition values
            value = result.get("value")
            if value in ("true", "false", "unknown", "not_asked"):
                conditions_to_set = state.get("conditions_to_set", [])
                for cond in conditions_to_set:
                    state.setdefault("condition_values", {})[cond] = value
            # Clear the current answer and move on
            state["current_answer"] = None
            state["clarification_attempts"] = 0
            state["next_action"] = "next_question"

        elif action == "ambiguous":
            attempts = state.get("clarification_attempts", 0)
            if attempts < 3:
                state["clarification_attempts"] = attempts + 1
                state["clarification_question"] = result.get("clarification_question")
                state["next_action"] = "ask_clarification"
            else:
                # Max attempts reached – store as unknown
                conditions_to_set = state.get("conditions_to_set", [])
                for cond in conditions_to_set:
                    state.setdefault("condition_values", {})[cond] = "unknown"
                state["current_answer"] = None
                state["next_action"] = "next_question"

        elif action == "unrelated":
            state["next_action"] = "ask_again"

        else:
            # Unknown action – fallback to asking again
            state["next_action"] = "ask_again"

        return state

    # ------------------------------------------------------------------
    # Node: update_condition_values
    # ------------------------------------------------------------------
    def update_condition_values(state: ScreeningState) -> ScreeningState:
        """Write accumulated condition values to the `condition_values` table."""
        business_profile_id = state.get("business_profile_id")
        if not business_profile_id:
            # Cannot update without a business profile
            return state

        condition_vals = state.get("condition_values", {})
        if not condition_vals:
            return state

        db: Session = SessionLocal()
        try:
            for cond_id, value in condition_vals.items():
                # Find existing record or create new
                existing = db.query(ConditionValue).filter_by(
                    business_profile_id=business_profile_id,
                    condition_id=cond_id
                ).first()
                if existing:
                    existing.value = value
                    #existing.last_updated_at = None  # The column is auto‑updated by SQLAlchemy when the row is committed.
                else:
                    new_cv = ConditionValue(
                        business_profile_id=business_profile_id,
                        condition_id=cond_id,
                        value=value,
                        source="user_answer"
                    )
                    db.add(new_cv)
            db.commit()
        finally:
            db.close()
        return state

    # ------------------------------------------------------------------
    # Node: next_question
    # ------------------------------------------------------------------
    def next_question(state: ScreeningState) -> ScreeningState:
        """Determine the next question or mark completion."""
        condition_vals = state.get("condition_values", {})
        answered_ids = set(state.get("answered_question_ids", []))
        next_q = get_next_question(condition_vals, answered_ids)
        if next_q:
            state["current_question_id"] = next_q["question_id"]
            state["current_question_text"] = next_q["text"]
            state["conditions_to_set"] = next_q["sets_conditions"]
            state["next_action"] = "next_question"
        else:
            state["next_action"] = "complete"
        return state

    # ------------------------------------------------------------------
    # Node: persist_state (save to onboarding_sessions)
    # ------------------------------------------------------------------
    def persist_state(state: ScreeningState) -> ScreeningState:
        """Save the current state to the `onboarding_sessions` table."""
        session_id = state.get("session_id")
        if not session_id:
            return state
        # Build JSON‑serializable state (exclude non‑serializable objects)
        serializable_state = {
            "current_question_id": state.get("current_question_id"),
            "current_question_text": state.get("current_question_text"),
            "conditions_to_set": state.get("conditions_to_set", []),
            "conversation_history": state.get("conversation_history", []),
            "clarification_attempts": state.get("clarification_attempts", 0),
            "condition_values": state.get("condition_values", {}),
            "answered_question_ids": state.get("answered_question_ids", []),
            "next_action": state.get("next_action"),
        }
        db = SessionLocal()
        try:
            update_session(db, session_id, json.dumps(serializable_state), "in_progress")
        finally:
            db.close()
        return state

    # ------------------------------------------------------------------
    # Build the graph
    # ------------------------------------------------------------------
    graph.add_node("present_question", present_question)
    graph.add_node("llm_interpret_answer", llm_interpret_answer)
    graph.add_node("handle_clarification", handle_clarification)
    graph.add_node("update_condition_values", update_condition_values)
    graph.add_node("next_question", next_question)
    graph.add_node("persist_state", persist_state)

    graph.set_entry_point("present_question")
    graph.add_edge("present_question", "llm_interpret_answer")
    graph.add_edge("llm_interpret_answer", "handle_clarification")

    graph.add_conditional_edges(
        "handle_clarification",
        lambda state: state.get("next_action", "ask_again"),
        {
            "next_question": "update_condition_values",
            "ask_clarification": "present_question",
            "ask_again": "present_question",
            "complete": END
        }
    )
    graph.add_edge("update_condition_values", "persist_state")
    graph.add_edge("persist_state", "next_question")
    graph.add_edge("next_question", END)

    return graph.compile()
