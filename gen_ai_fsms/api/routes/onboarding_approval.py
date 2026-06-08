from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from gen_ai_fsms.api.deps import get_db, require_admin
from gen_ai_fsms.api.routes.onboarding_screening import get_current_user_profile
from gen_ai_fsms.db.models import User
from gen_ai_fsms.services.safety_point_approval_service import (
    get_condition_values_for_profile,
    get_relevant_safety_points_for_profile,
    get_screening_completion_status,
)


router = APIRouter(
    prefix="/onboarding/safety-points",
    tags=["Onboarding - Safety Points"],
)


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