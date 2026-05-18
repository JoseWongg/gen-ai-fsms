import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from gen_ai_fsms.api.deps import get_db, require_admin
from gen_ai_fsms.db.models import User
from gen_ai_fsms.db.models.business_profile import BusinessProfile
from gen_ai_fsms.db.models.condition_value import ConditionValue
from gen_ai_fsms.db.models.condition import Condition
from gen_ai_fsms.services.session_service import create_session, load_session, update_session
from gen_ai_fsms.services.screening_questions import get_next_question
from gen_ai_fsms.ai.adapter import get_llm_adapter

router = APIRouter(prefix="/onboarding/screening", tags=["Onboarding - Screening"])

class AnswerRequest(BaseModel):
    answer: str

@router.post("/start")
def start_screening(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    profile = db.query(BusinessProfile).first()
    # This creates a default business profile if none exists, which is necessary for the screening process.
    # Functionality to update the business name and details can be added later in the application flow.
    # Multiple profiles and user associations can be implemented in the future as needed.
    # This version supports only a single business profile for proof of concept purposes.
    if not profile:
        profile = BusinessProfile(
            business_name="My Restaurant",
            status="active"
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

    existing = load_session(db, profile.id, "screening")
    if existing:
        state = json.loads(existing.state_json) if existing.state_json else {}
        return {
            "session_id": existing.id,
            "question_id": state.get("current_question_id"),
            "question_text": state.get("current_question_text"),
            "progress": state.get("answered_question_ids", [])
        }

    session_obj = create_session(db, profile.id, current_user.id, "screening")
    first_q = get_next_question({}, set())
    if not first_q:
        raise HTTPException(status_code=500, detail="No screening questions defined")

    state = {
        "current_question_id": first_q["question_id"],
        "current_question_text": first_q["text"],
        "conditions_to_set": first_q["sets_conditions"],
        "answered_question_ids": [],
        "condition_values": {},
        "conversation_history": [],
        "failed_answer_attempts": 0,
        "next_action": None
    }
    update_session(db, session_obj.id, json.dumps(state), "in_progress")
    return {
        "session_id": session_obj.id,
        "question_id": first_q["question_id"],
        "question_text": first_q["text"],
        "progress": []
    }

@router.get("/current")
def current_screening(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    profile = db.query(BusinessProfile).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Business profile not found")
    session_obj = load_session(db, profile.id, "screening")
    if not session_obj:
        raise HTTPException(status_code=404, detail="No active screening session")
    state = json.loads(session_obj.state_json) if session_obj.state_json else {}
    return {
        "session_id": session_obj.id,
        "question_id": state.get("current_question_id"),
        "question_text": state.get("current_question_text"),
        "progress": state.get("answered_question_ids", [])
    }

@router.post("/answer")
def submit_answer(
    req: AnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    answer = req.answer

    profile = db.query(BusinessProfile).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Business profile not found")

    session_obj = load_session(db, profile.id, "screening")
    if not session_obj:
        raise HTTPException(status_code=404, detail="No active screening session")

    state = json.loads(session_obj.state_json) if session_obj.state_json else {}
    question_text = state.get("current_question_text", "")
    conditions_to_set = state.get("conditions_to_set", [])
    conversation = state.get("conversation_history", [])

    conversation.append({"role": "user", "content": answer})

    adapter = get_llm_adapter()
    result = adapter.interpret_screening_answer(question_text, answer, conversation)

    action = result.get("action")
    value = result.get("value")

    def build_parent_child_condition_map():
        from gen_ai_fsms.services.screening_questions import screening_questions

        parent_to_children = {}

        for question in screening_questions:
            ask_if = question.get("ask_if")
            if not ask_if:
                continue

            for parent_condition in ask_if:
                parent_to_children.setdefault(parent_condition, set())

                for child_condition in question.get("sets_conditions", []):
                    parent_to_children[parent_condition].add(child_condition)

        return parent_to_children

    def apply_false_propagation(values_dict):
        """
        If a parent condition is false, all dependent child conditions are false.
        Parent true does not change child values.
        Parent unknown does not change child values.
        """
        parent_to_children = build_parent_child_condition_map()
        expanded_values = dict(values_dict)

        stack = [
            condition_id
            for condition_id, condition_value in values_dict.items()
            if condition_value == "false"
        ]

        while stack:
            parent_condition = stack.pop()

            for child_condition in parent_to_children.get(parent_condition, set()):
                if expanded_values.get(child_condition) != "false":
                    expanded_values[child_condition] = "false"
                    stack.append(child_condition)

        return expanded_values

    def persist_condition_values(values_dict):
        values_to_persist = apply_false_propagation(values_dict)

        for cond, val in values_to_persist.items():
            state.setdefault("condition_values", {})[cond] = val

            existing = db.query(ConditionValue).filter_by(
                business_profile_id=profile.id,
                condition_id=cond
            ).first()

            if existing:
                existing.value = val
            else:
                new_cv = ConditionValue(
                    business_profile_id=profile.id,
                    condition_id=cond,
                    value=val,
                    source="user_answer"
                )
                db.add(new_cv)

        db.commit()

    def get_next_or_unresolved_question(answered_question_ids):
        """
        First, try the normal deterministic next-question flow.
        If no new eligible question remains, re-ask questions already answered as unknown.
        If none are unknown, screening is complete.
        """
        from gen_ai_fsms.services.screening_questions import screening_questions

        next_question = get_next_question(
            state.get("condition_values", {}),
            set(answered_question_ids)
        )

        if next_question:
            return next_question, "next_question"

        for question in screening_questions:
            if question["question_id"] not in answered_question_ids:
                continue

            question_conditions = question.get("sets_conditions", [])
            has_unknown_condition = any(
                state.get("condition_values", {}).get(condition_id) == "unknown"
                for condition_id in question_conditions
            )

            if has_unknown_condition:
                return question, "reask_unknown"

        return None, "complete"

    def set_current_question(next_question):
        state["current_question_id"] = next_question["question_id"]
        state["current_question_text"] = next_question["text"]
        state["conditions_to_set"] = next_question["sets_conditions"]
        state["next_action"] = "next_question"

    if action == "clear":
        if value in ("true", "false", "unknown", "not_asked"):
            values_to_set = {cond: value for cond in conditions_to_set}
            persist_condition_values(values_to_set)

        answered = state.get("answered_question_ids", [])
        if state["current_question_id"] not in answered:
            answered.append(state["current_question_id"])
            state["answered_question_ids"] = answered

        state["conversation_history"] = []
        state["failed_answer_attempts"] = 0
        state["clarification_attempts"] = 0
        state["unrelated_attempts"] = 0

        next_question, next_mode = get_next_or_unresolved_question(answered)

        if next_question:
            set_current_question(next_question)
            update_session(db, session_obj.id, json.dumps(state), "in_progress")

            if next_mode == "reask_unknown":
                message = (
                    f"Your response has been recorded as {value}. "
                    "Some responses still need to be clarified before screening can finish. "
                    "I will ask those questions again."
                )
            else:
                message = f"Your response has been recorded as {value}."

            return {
                "action": "next_question",
                "question_id": next_question["question_id"],
                "question_text": next_question["text"],
                "message": message,
                "session_id": session_obj.id
            }

        update_session(db, session_obj.id, json.dumps(state), "completed")
        return {
            "action": "complete",
            "message": (
                "Screening completed. Your responses have been recorded. "
                "You will be able to review the recorded condition values in the profile view later."
            )
        }

    elif action in ("ambiguous", "unrelated"):
        attempts = state.get("failed_answer_attempts", 0)

        if attempts < 2:
            state["failed_answer_attempts"] = attempts + 1
            state["conversation_history"] = conversation

            update_session(db, session_obj.id, json.dumps(state), "in_progress")

            return {
                "action": "ask_again",
                "message": (
                    "I could not identify a clear answer. "
                    "Please answer the question directly.\n\n"
                    f"{question_text}"
                ),
                "session_id": session_obj.id
            }

        values_to_set = {cond: "unknown" for cond in conditions_to_set}
        persist_condition_values(values_to_set)

        answered = state.get("answered_question_ids", [])
        if state["current_question_id"] not in answered:
            answered.append(state["current_question_id"])
            state["answered_question_ids"] = answered

        state["conversation_history"] = []
        state["failed_answer_attempts"] = 0
        state["clarification_attempts"] = 0
        state["unrelated_attempts"] = 0

        next_question, next_mode = get_next_or_unresolved_question(answered)

        if next_question:
            set_current_question(next_question)
            update_session(db, session_obj.id, json.dumps(state), "in_progress")

            if next_mode == "reask_unknown":
                message = (
                    "I am unable to identify an unambiguous response from you. "
                    "I will record your response as unknown. "
                    "Some responses still need to be clarified before screening can finish. "
                    "I will ask those questions again."
                )
            else:
                message = (
                    "I am unable to identify an unambiguous response from you. "
                    "I will record your response as unknown. "
                    "We need to move on."
                )

            return {
                "action": "next_question",
                "question_id": next_question["question_id"],
                "question_text": next_question["text"],
                "message": message,
                "session_id": session_obj.id
            }

        update_session(db, session_obj.id, json.dumps(state), "completed")
        return {
            "action": "complete",
            "message": (
                "Screening completed. Your responses have been recorded. "
                "You will be able to review the recorded condition values in the profile view later."
            )
        }

    update_session(db, session_obj.id, json.dumps(state), "in_progress")
    return {
        "action": "ask_again",
        "message": (
            "I could not process your answer clearly. "
            "Please answer the question directly.\n\n"
            f"{question_text}"
        ),
        "session_id": session_obj.id
    }








@router.get("/condition-values")
def get_screening_condition_values(
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_admin) # FastAPI dependency to ensure only admin users can access this endpoint.
):
    profile = db.query(BusinessProfile).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Business profile not found")

    rows = (
        db.query(ConditionValue, Condition)
        .join(Condition, ConditionValue.condition_id == Condition.condition_id)
        .filter(ConditionValue.business_profile_id == profile.id)
        .order_by(Condition.condition_id)
        .all()
    )

    return {
        "business_profile_id": profile.id,
        "condition_values": [
            {
                "condition_id": condition.condition_id,
                "condition_name": condition.condition_name,
                "value": condition_value.value,
                "source": condition_value.source,
            }
            for condition_value, condition in rows
        ],
    }



























@router.post("/reset")
def reset_screening(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    profile = db.query(BusinessProfile).first()

    if not profile:
        raise HTTPException(status_code=404, detail="Business profile not found")
    
    # Delete the active screening session
    session_obj = load_session(db, profile.id, "screening")

    if session_obj:
        db.delete(session_obj)
        db.commit()
    
    # Delete all condition values for this profile
    db.query(ConditionValue).filter_by(business_profile_id=profile.id).delete()
    db.commit()

    return {"message": "Screening reset successfully"}


@router.post("/resume")
def resume_screening(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    profile = db.query(BusinessProfile).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Business profile not found")
    session_obj = load_session(db, profile.id, "screening")
    if not session_obj:
        raise HTTPException(status_code=404, detail="No active screening session")
    state = json.loads(session_obj.state_json) if session_obj.state_json else {}
    return {
        "session_id": session_obj.id,
        "question_id": state.get("current_question_id"),
        "question_text": state.get("current_question_text"),
        "progress": state.get("answered_question_ids", [])
    }


