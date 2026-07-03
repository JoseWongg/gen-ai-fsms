from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from gen_ai_fsms.api.deps import get_current_user, get_db
from gen_ai_fsms.db.models import User
from gen_ai_fsms.schemas.chilling_temperature_corrective_action_workflow import (
    CorrectiveActionMessageRequest,
    CorrectiveActionWorkflowResponse,
)
from gen_ai_fsms.workflows.fridge_corrective_action_workflow import (
    approve_final_summary,
    get_existing_session_status,
    process_user_message,
    start_or_resume_session,
)


router = APIRouter(
    prefix="/chilling-temperature-incidents",
    tags=["Chilling Temperature Incidents"],
)


def get_current_business_profile_id(current_user: User) -> int:
    if current_user.business_profile_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current user is not linked to a business profile.",
        )

    return current_user.business_profile_id


@router.post(
    "/{incident_id}/corrective-action/session",
    response_model=CorrectiveActionWorkflowResponse,
)
def start_chilling_temperature_corrective_action_session(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    business_profile_id = get_current_business_profile_id(current_user)

    return start_or_resume_session(
        db=db,
        business_profile_id=business_profile_id,
        user_id=current_user.id,
        incident_id=incident_id,
    )


@router.get(
    "/{incident_id}/corrective-action/session",
    response_model=CorrectiveActionWorkflowResponse,
)
def get_chilling_temperature_corrective_action_session(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    business_profile_id = get_current_business_profile_id(current_user)

    return get_existing_session_status(
        db=db,
        business_profile_id=business_profile_id,
        incident_id=incident_id,
    )


@router.post(
    "/{incident_id}/corrective-action/message",
    response_model=CorrectiveActionWorkflowResponse,
)
def send_chilling_temperature_corrective_action_message(
    incident_id: int,
    data: CorrectiveActionMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    business_profile_id = get_current_business_profile_id(current_user)

    return process_user_message(
        db=db,
        business_profile_id=business_profile_id,
        user_id=current_user.id,
        incident_id=incident_id,
        user_message=data.message,
    )


@router.post(
    "/{incident_id}/corrective-action/approve",
    response_model=CorrectiveActionWorkflowResponse,
)
def approve_chilling_temperature_corrective_action_summary(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    business_profile_id = get_current_business_profile_id(current_user)

    return approve_final_summary(
        db=db,
        business_profile_id=business_profile_id,
        user_id=current_user.id,
        incident_id=incident_id,
    )