import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from gen_ai_fsms.api.deps import get_db, require_admin
from gen_ai_fsms.api.routes.onboarding_screening import get_current_user_profile
from gen_ai_fsms.db.models import User
from gen_ai_fsms.db.models.onboarding_session import OnboardingSession
from gen_ai_fsms.services.safety_point_approval_service import (
    get_condition_values_for_profile,
    get_relevant_safety_points_for_profile,
    get_screening_completion_status,
)
from gen_ai_fsms.workflows.safety_point_graph import safety_point_graph


router = APIRouter(
    prefix="/onboarding/safety-points",
    tags=["Onboarding - Safety Points"],
)

SAFETY_POINT_APPROVAL_PHASE = "safety_point_approval"


class SafetyPointMessageRequest(BaseModel):
    message: str


def get_approval_session(
    db: Session,
    business_profile_id: int,
) -> Optional[OnboardingSession]:
    return (
        db.query(OnboardingSession)
        .filter(
            OnboardingSession.business_profile_id == business_profile_id,
            OnboardingSession.phase == SAFETY_POINT_APPROVAL_PHASE,
            OnboardingSession.status.in_(["in_progress", "completed"]),
        )
        .order_by(OnboardingSession.id.desc())
        .first()
    )


def create_approval_session(
    db: Session,
    business_profile_id: int,
    user_id: int,
) -> OnboardingSession:
    session = OnboardingSession(
        business_profile_id=business_profile_id,
        user_id=user_id,
        phase=SAFETY_POINT_APPROVAL_PHASE,
        status="in_progress",
        state_json=None,
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return session


def load_session_state(session: OnboardingSession) -> Dict[str, Any]:
    if not session.state_json:
        return {}

    return json.loads(session.state_json)


def save_session_state(
    db: Session,
    session: OnboardingSession,
    state: Dict[str, Any],
) -> OnboardingSession:
    session.state_json = json.dumps(state)
    session.status = (
        "completed"
        if state.get("status") == "completed"
        else "in_progress"
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return session


def build_approval_response(
    session: OnboardingSession,
    state: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "session_id": session.id,
        "business_profile_id": session.business_profile_id,
        "session_status": session.status,
        "workflow_status": state.get("status"),
        "next_action": state.get("next_action"),
        "assistant_message": state.get("assistant_message"),
        "current_safety_point": state.get("current_safety_point_view"),
        "progress": state.get("approval_progress"),
        "pending_additional_questions": state.get(
            "pending_additional_questions",
            [],
        ),
        "current_additional_question": state.get("current_additional_question"),
        "current_q_and_a_messages": state.get("current_q_and_a_messages", []),
        "approved_safety_point_ids": state.get("approved_safety_point_ids", []),
        "last_approved_safety_point_record": state.get(
            "last_approved_safety_point_record"
        ),
        "relevant_safety_point_count": state.get("relevant_safety_point_count"),
        "active_condition_count": state.get("active_condition_count"),
        "completed_active_condition_count": state.get(
            "completed_active_condition_count"
        ),
    }


def initialise_approval_state(
    db: Session,
    business_profile_id: int,
    user_id: int,
) -> Dict[str, Any]:
    status = get_screening_completion_status(db, business_profile_id)

    if not status["is_complete"]:
        raise HTTPException(
            status_code=400,
            detail=(
                "Complete the Food Safety Profile screening before starting "
                "the safety point approval workflow."
            ),
        )

    initial_state = {
        "business_profile_id": business_profile_id,
        "user_id": user_id,
    }

    return safety_point_graph.invoke(initial_state)


@router.get("/readiness")
def get_safety_point_readiness(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    profile = get_current_user_profile(db, current_user)
    status = get_screening_completion_status(db, profile.id)

    if not status["is_complete"]:
        return {
            "is_ready": False,
            "message": (
                "Complete the Food Safety Profile screening before starting the "
                "Food Safety Management System Builder."
            ),
            **status,
        }

    return {
        "is_ready": True,
        "message": "Food Safety Profile screening is complete.",
        **status,
    }


@router.get("/relevant")
def get_relevant_safety_points(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    profile = get_current_user_profile(db, current_user)
    status = get_screening_completion_status(db, profile.id)

    if not status["is_complete"]:
        raise HTTPException(
            status_code=400,
            detail=(
                "Complete the Food Safety Profile screening before retrieving "
                "relevant safety points."
            ),
        )

    condition_values = get_condition_values_for_profile(db, profile.id)
    relevant_safety_points = get_relevant_safety_points_for_profile(db, profile.id)

    return {
        "business_profile_id": profile.id,
        "relevant_safety_point_count": len(relevant_safety_points),
        "relevant_safety_point_ids": [
            safety_point.get("safety_point_id")
            for safety_point in relevant_safety_points
        ],
        "condition_values": condition_values,
        "relevant_safety_points": relevant_safety_points,
    }


@router.post("/start")
def start_safety_point_approval(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    profile = get_current_user_profile(db, current_user)
    session = get_approval_session(db, profile.id)

    if session is not None and session.state_json:
        state = load_session_state(session)
        return build_approval_response(session, state)

    state = initialise_approval_state(
        db=db,
        business_profile_id=profile.id,
        user_id=current_user.id,
    )

    if session is None:
        session = create_approval_session(
            db=db,
            business_profile_id=profile.id,
            user_id=current_user.id,
        )

    session = save_session_state(db, session, state)

    return build_approval_response(session, state)


@router.get("/current")
def get_current_safety_point_approval_state(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    profile = get_current_user_profile(db, current_user)
    session = get_approval_session(db, profile.id)

    if session is None or not session.state_json:
        raise HTTPException(
            status_code=404,
            detail="No safety point approval session exists. Start one first.",
        )

    state = load_session_state(session)

    return build_approval_response(session, state)


@router.post("/message")
def send_safety_point_approval_message(
    request: SafetyPointMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    profile = get_current_user_profile(db, current_user)
    session = get_approval_session(db, profile.id)

    if session is None or not session.state_json:
        raise HTTPException(
            status_code=404,
            detail="No safety point approval session exists. Start one first.",
        )

    state = load_session_state(session)
    state["business_profile_id"] = profile.id
    state["user_id"] = current_user.id
    state["last_user_message"] = request.message

    updated_state = safety_point_graph.invoke(state)
    session = save_session_state(db, session, updated_state)

    return build_approval_response(session, updated_state)


@router.post("/resume")
def resume_safety_point_approval(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    profile = get_current_user_profile(db, current_user)
    session = get_approval_session(db, profile.id)

    if session is None or not session.state_json:
        raise HTTPException(
            status_code=404,
            detail="No safety point approval session exists. Start one first.",
        )

    state = load_session_state(session)

    return build_approval_response(session, state)


@router.post("/reset")
def reset_safety_point_approval(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    profile = get_current_user_profile(db, current_user)

    sessions = (
        db.query(OnboardingSession)
        .filter(
            OnboardingSession.business_profile_id == profile.id,
            OnboardingSession.phase == SAFETY_POINT_APPROVAL_PHASE,
        )
        .all()
    )

    deleted_count = len(sessions)

    for session in sessions:
        db.delete(session)

    db.commit()

    return {
        "business_profile_id": profile.id,
        "deleted_session_count": deleted_count,
        "message": "Safety point approval session reset.",
    }