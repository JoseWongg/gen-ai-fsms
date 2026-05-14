import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from gen_ai_fsms.api.deps import get_db, require_admin
from gen_ai_fsms.db.models import User
from gen_ai_fsms.db.models.business_profile import BusinessProfile
from gen_ai_fsms.db.models.condition_value import ConditionValue
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
        "clarification_attempts": 0,
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

    adapter = get_llm_adapter()
    result = adapter.interpret_screening_answer(question_text, answer, conversation)

    action = result.get("action")
    if action == "clear":
        value = result.get("value")
        if value in ("true", "false", "unknown", "not_asked"):
            
            # Update in-memory state
            for cond in conditions_to_set:
                state.setdefault("condition_values", {})[cond] = value

            # Persist to condition_values table
            for cond in conditions_to_set:
                existing_cv = db.query(ConditionValue).filter_by(
                    business_profile_id=profile.id,
                    condition_id=cond
                ).first()
                if existing_cv:
                    existing_cv.value = value
                    existing_cv.last_updated_at = None  # let SQLAlchemy auto-update
                else:
                    new_cv = ConditionValue(
                        business_profile_id=profile.id,
                        condition_id=cond,
                        value=value,
                        source="user_answer"
                    )
                    db.add(new_cv)
            db.commit()

        state["answered_question_ids"].append(state["current_question_id"])
        state["conversation_history"] = []
        state["clarification_attempts"] = 0
        next_q = get_next_question(state["condition_values"], set(state["answered_question_ids"]))
        if next_q:
            state["current_question_id"] = next_q["question_id"]
            state["current_question_text"] = next_q["text"]
            state["conditions_to_set"] = next_q["sets_conditions"]
            state["next_action"] = "next_question"
        else:
            state["next_action"] = "complete"
            update_session(db, session_obj.id, json.dumps(state), "completed")
            return {"action": "complete", "message": "Screening completed"}

    elif action == "ambiguous":
        attempts = state.get("clarification_attempts", 0)
        if attempts < 3:
            state["clarification_attempts"] = attempts + 1
            state["conversation_history"].append({"role": "user", "content": answer})
            state["conversation_history"].append({"role": "assistant", "content": result.get("clarification_question")})
            update_session(db, session_obj.id, json.dumps(state), "in_progress")
            return {
                "action": "clarify",
                "clarification_question": result.get("clarification_question"),
                "session_id": session_obj.id
            }
        else:
            for cond in conditions_to_set:
                state.setdefault("condition_values", {})[cond] = "unknown"
            state["answered_question_ids"].append(state["current_question_id"])
            state["conversation_history"] = []
            state["clarification_attempts"] = 0
            next_q = get_next_question(state["condition_values"], set(state["answered_question_ids"]))
            if next_q:
                state["current_question_id"] = next_q["question_id"]
                state["current_question_text"] = next_q["text"]
                state["conditions_to_set"] = next_q["sets_conditions"]
                state["next_action"] = "next_question"
            else:
                state["next_action"] = "complete"
                update_session(db, session_obj.id, json.dumps(state), "completed")
                return {"action": "complete", "message": "Screening completed"}

    elif action == "unrelated":
        state["next_action"] = "retry"
        update_session(db, session_obj.id, json.dumps(state), "in_progress")
        return {
            "action": "retry",
            "message": "Please answer the question directly."
        }

    update_session(db, session_obj.id, json.dumps(state), "in_progress")
    return {
        "action": "next_question",
        "question_id": state["current_question_id"],
        "question_text": state["current_question_text"],
        "session_id": session_obj.id
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
