from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from gen_ai_fsms.api.deps import get_db, require_admin
from gen_ai_fsms.api.routes.onboarding_screening import get_current_user_profile
from gen_ai_fsms.db.models import User
from gen_ai_fsms.db.models.condition import Condition
from gen_ai_fsms.db.models.condition_value import ConditionValue
from gen_ai_fsms.services.screening_questions import screening_questions
from gen_ai_fsms.services.content_service import ContentService


router = APIRouter(
    prefix="/onboarding/safety-points",
    tags=["Onboarding - Safety Points"],
)


def get_screening_completion_status(db: Session, business_profile_id: int) -> dict:
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


def get_condition_values_for_profile(db: Session, business_profile_id: int) -> dict:
    rows = (
        db.query(ConditionValue)
        .filter(ConditionValue.business_profile_id == business_profile_id)
        .all()
    )

    return {
        row.condition_id: row.value
        for row in rows
    }


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

# Retrieve the safety points that apply to the current business profile based on the completed screening condition values.
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

    content_service = ContentService()
    relevant_safety_points = content_service.get_safety_points_by_conditions(
        condition_values
    )

    return {
        "business_profile_id": profile.id,
        "relevant_safety_point_count": len(relevant_safety_points),
        "relevant_safety_point_ids": [
            safety_point.get("safety_point_id")
            for safety_point in relevant_safety_points
        ],
        "relevant_safety_points": relevant_safety_points,
    }

