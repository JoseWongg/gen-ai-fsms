from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from gen_ai_fsms.services.chilling_temperature_compliance_service import (
    FREEZER_TYPE,
    FRIDGE_TYPE,
    normalize_chilling_equipment_type,
)
from gen_ai_fsms.services.chilling_temperature_incident_service import (
    get_chilling_temperature_incident_for_corrective_action,
)
from gen_ai_fsms.workflows import freezer_corrective_action_workflow
from gen_ai_fsms.workflows import fridge_corrective_action_workflow


def _get_equipment_type_for_incident(
    db: Session,
    business_profile_id: int,
    incident_id: int,
) -> str:
    incident = get_chilling_temperature_incident_for_corrective_action(
        db=db,
        business_profile_id=business_profile_id,
        incident_id=incident_id,
    )

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Chilling temperature incident was not found for this "
                "business profile."
            ),
        )

    try:
        equipment_type = normalize_chilling_equipment_type(
            incident.equipment_type_snapshot
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported chilling equipment type for corrective action.",
        ) from exc

    if equipment_type not in {FRIDGE_TYPE, FREEZER_TYPE}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported chilling equipment type for corrective action.",
        )

    return equipment_type


def _select_workflow_module(
    db: Session,
    business_profile_id: int,
    incident_id: int,
):
    equipment_type = _get_equipment_type_for_incident(
        db=db,
        business_profile_id=business_profile_id,
        incident_id=incident_id,
    )

    if equipment_type == FRIDGE_TYPE:
        return fridge_corrective_action_workflow

    if equipment_type == FREEZER_TYPE:
        return freezer_corrective_action_workflow

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported chilling equipment type for corrective action.",
    )


def start_or_resume_session(
    db: Session,
    business_profile_id: int,
    user_id: int,
    incident_id: int,
) -> dict[str, Any]:
    workflow_module = _select_workflow_module(
        db=db,
        business_profile_id=business_profile_id,
        incident_id=incident_id,
    )
    return workflow_module.start_or_resume_session(
        db=db,
        business_profile_id=business_profile_id,
        user_id=user_id,
        incident_id=incident_id,
    )


def get_existing_session_status(
    db: Session,
    business_profile_id: int,
    incident_id: int,
) -> dict[str, Any]:
    workflow_module = _select_workflow_module(
        db=db,
        business_profile_id=business_profile_id,
        incident_id=incident_id,
    )
    return workflow_module.get_existing_session_status(
        db=db,
        business_profile_id=business_profile_id,
        incident_id=incident_id,
    )


def process_user_message(
    db: Session,
    business_profile_id: int,
    user_id: int,
    incident_id: int,
    user_message: str,
) -> dict[str, Any]:
    workflow_module = _select_workflow_module(
        db=db,
        business_profile_id=business_profile_id,
        incident_id=incident_id,
    )
    return workflow_module.process_user_message(
        db=db,
        business_profile_id=business_profile_id,
        user_id=user_id,
        incident_id=incident_id,
        user_message=user_message,
    )


def approve_final_summary(
    db: Session,
    business_profile_id: int,
    user_id: int,
    incident_id: int,
) -> dict[str, Any]:
    workflow_module = _select_workflow_module(
        db=db,
        business_profile_id=business_profile_id,
        incident_id=incident_id,
    )
    return workflow_module.approve_final_summary(
        db=db,
        business_profile_id=business_profile_id,
        user_id=user_id,
        incident_id=incident_id,
    )
