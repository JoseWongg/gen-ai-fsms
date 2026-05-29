import json
import random

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from gen_ai_fsms.ai.adapter import get_llm_adapter
from gen_ai_fsms.api.deps import get_db, require_admin
from gen_ai_fsms.db.models import User
from gen_ai_fsms.db.models.business_profile import BusinessProfile
from gen_ai_fsms.db.models.condition import Condition
from gen_ai_fsms.db.models.condition_value import ConditionValue
from gen_ai_fsms.services.screening_questions import get_next_question
from gen_ai_fsms.services.session_service import (
    create_session,
    load_session,
    update_session,
)


router = APIRouter(prefix="/onboarding/screening", tags=["Onboarding - Screening"])


class AnswerRequest(BaseModel):
    answer: str


def get_current_user_profile(db: Session, current_user: User) -> BusinessProfile:
    """
    Return the venue workspace linked to the authenticated user.

    Each user must only access screening data belonging to their own
    BusinessProfile.
    """
    if current_user.business_profile_id is None:
        raise HTTPException(
            status_code=404,
            detail="No business profile is linked to the current user",
        )

    profile = (
        db.query(BusinessProfile)
        .filter(BusinessProfile.id == current_user.business_profile_id)
        .first()
    )

    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Business profile not found for current user",
        )

    return profile

def add_display_message(state: dict, role: str, content: str) -> None:
    state.setdefault("display_messages", []).append(
        {
            "role": role,
            "content": content,
        }
    )

def build_recorded_response_message(state: dict, value: str) -> str:
    messages_by_value = {
        "true": [
            "Noted. This activity applies to your business.",
            "Understood. I have recorded that you carry out this activity.",
            "Recorded. This activity is part of your business operation.",
            "Thank you. I have recorded this activity as applicable.",
            "Got it. This activity is relevant to your business.",
            "Thank you. I have noted that this activity takes place in your business.",
            "Understood. This activity has been recorded as part of your operation.",
            "Recorded. Your business carries out this activity.",
            "Noted. This has been included in your screening information.",
            "Thank you. I have captured that this activity applies.",
        ],
        "false": [
            "Noted. This activity does not apply to your business.",
            "Understood. I have recorded that you do not carry out this activity.",
            "Recorded. This activity is not part of your business operation.",
            "Thank you. I have recorded this activity as not applicable.",
            "Got it. This activity is not relevant to your business.",
            "Thank you. I have noted that this activity does not take place in your business.",
            "Understood. This activity has been recorded as outside your operation.",
            "Recorded. Your business does not carry out this activity.",
            "Noted. This has not been included as an activity in your screening information.",
            "Thank you. I have captured that this activity does not apply.",
        ],
        "unknown": [
            "I could not determine a clear answer, so I have recorded this as unknown for now.",
            "I have not been able to establish whether this activity applies, so it has been recorded as unknown.",
            "Your response remains unclear, so I have marked this activity as unknown for now.",
            "I could not confirm whether this activity takes place, so I have recorded an unknown response.",
            "This activity could not be determined from your response, so it has been marked as unknown.",
            "I have recorded this as unknown because a clear answer could not be identified.",
            "I could not establish a clear outcome for this activity, so it remains recorded as unknown.",
            "Your response did not allow me to confirm this activity, so I have marked it as unknown.",
            "I was unable to determine whether this applies, so an unknown response has been recorded.",
            "This response could not be resolved clearly, so I have recorded the activity as unknown.",
        ],
    }

    messages = messages_by_value.get(
        value,
        ["Your response has been recorded."],
    )

    previous_message = state.get("last_recorded_message")
    available_messages = [
        message for message in messages
        if message != previous_message
    ]

    selected_message = random.choice(available_messages or messages)
    state["last_recorded_message"] = selected_message

    return selected_message

@router.post("/start")
def start_screening(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    profile = get_current_user_profile(db, current_user)

    existing = load_session(db, profile.id, "screening")
    if existing:
        state = json.loads(existing.state_json) if existing.state_json else {}
        display_messages = state.get("display_messages")

        if not display_messages and state.get("current_question_text"):
            display_messages = [
                {
                    "role": "assistant",
                    "content": state.get("current_question_text"),
                }
            ]

        return {
            "session_id": existing.id,
            "question_id": state.get("current_question_id"),
            "question_text": state.get("current_question_text"),
            "progress": state.get("answered_question_ids", []),
            "display_messages": display_messages or [],
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
        "display_messages": [
            {
                "role": "assistant",
                "content": first_q["text"],
            }
        ],
        "failed_answer_attempts": 0,
        "next_action": None,
    }


    update_session(db, session_obj.id, json.dumps(state), "in_progress")

    return {
        "session_id": session_obj.id,
        "question_id": first_q["question_id"],
        "question_text": first_q["text"],
        "progress": [],
        "display_messages": state["display_messages"],
    }



@router.get("/current")
def current_screening(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    profile = get_current_user_profile(db, current_user)

    session_obj = load_session(db, profile.id, "screening")
    if not session_obj:
        raise HTTPException(status_code=404, detail="No active screening session")

    state = json.loads(session_obj.state_json) if session_obj.state_json else {}
    display_messages = state.get("display_messages")

    if not display_messages and state.get("current_question_text"):
        display_messages = [
            {
                "role": "assistant",
                "content": state.get("current_question_text"),
            }
        ]

    return {
        "session_id": session_obj.id,
        "question_id": state.get("current_question_id"),
        "question_text": state.get("current_question_text"),
        "progress": state.get("answered_question_ids", []),
        "display_messages": display_messages or [],
    }



@router.post("/answer")
def submit_answer(
    req: AnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    answer = req.answer
    profile = get_current_user_profile(db, current_user)

    session_obj = load_session(db, profile.id, "screening")
    if not session_obj:
        raise HTTPException(status_code=404, detail="No active screening session")

    state = json.loads(session_obj.state_json) if session_obj.state_json else {}
    question_text = state.get("current_question_text", "")
    conditions_to_set = state.get("conditions_to_set", [])
    conversation = state.get("conversation_history", [])

    if not state.get("display_messages") and question_text:
        add_display_message(state, "assistant", question_text)

    add_display_message(state, "user", answer)
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

            existing = (
                db.query(ConditionValue)
                .filter_by(
                    business_profile_id=profile.id,
                    condition_id=cond,
                )
                .first()
            )

            if existing:
                existing.value = val
            else:
                new_cv = ConditionValue(
                    business_profile_id=profile.id,
                    condition_id=cond,
                    value=val,
                    source="user_answer",
                )
                db.add(new_cv)

        db.commit()

    def get_next_or_unresolved_question(answered_question_ids):
        """
        First, try the normal deterministic next-question flow.
        If no new eligible question remains, re-ask questions already answered
        as unknown. If none are unknown, screening is complete.
        """
        from gen_ai_fsms.services.screening_questions import screening_questions

        next_question = get_next_question(
            state.get("condition_values", {}),
            set(answered_question_ids),
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
            recorded_message = build_recorded_response_message(state, value)

            if next_mode == "reask_unknown":
                message = (
                    f"{recorded_message} "
                    "Some responses still need to be clarified before screening can finish. "
                    "I will ask those questions again."
                )
            else:
                message = recorded_message

            add_display_message(state, "assistant", message)

            set_current_question(next_question)
            add_display_message(state, "assistant", next_question["text"])

            update_session(db, session_obj.id, json.dumps(state), "in_progress")

            return {
                "action": "next_question",
                "question_id": next_question["question_id"],
                "question_text": next_question["text"],
                "message": message,
                "session_id": session_obj.id,
            }

        completion_message = (
            "Screening completed. Your responses have been recorded. "
            "You will be able to view the recorded condition values when you visit this page again."
        )

        add_display_message(state, "assistant", completion_message)
        update_session(db, session_obj.id, json.dumps(state), "completed")

        return {
            "action": "complete",
            "message": completion_message,
        }

    if action in ("ambiguous", "unrelated"):
        attempts = state.get("failed_answer_attempts", 0)

        if attempts < 2:
            state["failed_answer_attempts"] = attempts + 1
            state["conversation_history"] = conversation

            ask_again_message = (
                "I could not identify a clear answer. "
                "Please answer the question directly.\n\n"
                f"{question_text}"
            )

            add_display_message(state, "assistant", ask_again_message)
            update_session(db, session_obj.id, json.dumps(state), "in_progress")

            return {
                "action": "ask_again",
                "message": ask_again_message,
                "session_id": session_obj.id,
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
            recorded_message = build_recorded_response_message(state, "unknown")

            if next_mode == "reask_unknown":
                message = (
                    f"{recorded_message} "
                    "Some responses still need to be clarified before screening can finish. "
                    "I will ask those questions again."
                )
            else:
                message = (
                    f"{recorded_message} "
                    "We need to move on."
                )

            add_display_message(state, "assistant", message)

            set_current_question(next_question)
            add_display_message(state, "assistant", next_question["text"])

            update_session(db, session_obj.id, json.dumps(state), "in_progress")

            return {
                "action": "next_question",
                "question_id": next_question["question_id"],
                "question_text": next_question["text"],
                "message": message,
                "session_id": session_obj.id,
            }

        completion_message = (
            "Screening completed. Your responses have been recorded. "
            "You will be able to review the recorded condition values in the profile view later."
        )

        add_display_message(state, "assistant", completion_message)
        update_session(db, session_obj.id, json.dumps(state), "completed")

        return {
            "action": "complete",
            "message": completion_message,
        }

    ask_again_message = (
        "I could not process your answer clearly. "
        "Please answer the question directly.\n\n"
        f"{question_text}"
    )

    add_display_message(state, "assistant", ask_again_message)
    update_session(db, session_obj.id, json.dumps(state), "in_progress")

    return {
        "action": "ask_again",
        "message": ask_again_message,
        "session_id": session_obj.id,
    }


@router.get("/condition-values")
def get_screening_condition_values(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    profile = get_current_user_profile(db, current_user)

    rows = (
        db.query(ConditionValue, Condition)
        .join(Condition, ConditionValue.condition_id == Condition.condition_id)
        .filter(ConditionValue.business_profile_id == profile.id)
        .order_by(Condition.condition_id)
        .all()
    )

    condition_values = [
        {
            "condition_id": condition.condition_id,
            "condition_name": condition.condition_name,
            "value": condition_value.value,
            "source": condition_value.source,
        }
        for condition_value, condition in rows
    ]

    values_by_condition_id = {
        item["condition_id"]: item["value"]
        for item in condition_values
    }

    from gen_ai_fsms.services.screening_questions import screening_questions

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
        "business_profile_id": profile.id,
        "is_complete": is_complete,
        "active_condition_count": len(active_condition_ids),
        "completed_active_condition_count": len(completed_active_conditions),
        "condition_values": condition_values,
    }


@router.post("/reset")
def reset_screening(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    profile = get_current_user_profile(db, current_user)

    session_obj = load_session(db, profile.id, "screening")

    if session_obj:
        db.delete(session_obj)
        db.commit()

    db.query(ConditionValue).filter_by(business_profile_id=profile.id).delete()
    db.commit()

    return {"message": "Screening reset successfully"}


@router.post("/resume")
def resume_screening(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    profile = get_current_user_profile(db, current_user)

    session_obj = load_session(db, profile.id, "screening")
    if not session_obj:
        raise HTTPException(status_code=404, detail="No active screening session")

    state = json.loads(session_obj.state_json) if session_obj.state_json else {}
    display_messages = state.get("display_messages")

    if not display_messages and state.get("current_question_text"):
        display_messages = [
            {
                "role": "assistant",
                "content": state.get("current_question_text"),
            }
        ]

    return {
        "session_id": session_obj.id,
        "question_id": state.get("current_question_id"),
        "question_text": state.get("current_question_text"),
        "progress": state.get("answered_question_ids", []),
        "display_messages": display_messages or [],
    }