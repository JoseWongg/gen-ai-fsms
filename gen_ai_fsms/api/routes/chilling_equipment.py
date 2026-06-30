from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from gen_ai_fsms.api.deps import get_current_user, get_db, require_admin
from gen_ai_fsms.db.models import User
from gen_ai_fsms.schemas.chilling_equipment import (
    ChillingEquipmentChangeRecordResponse,
    ChillingEquipmentCreate,
    ChillingEquipmentResponse,
    ChillingEquipmentTemperatureHistoryResponse,
    ChillingEquipmentUpdate,
)
from gen_ai_fsms.services.chilling_equipment_service import (
    activate_chilling_equipment,
    create_chilling_equipment,
    deactivate_chilling_equipment,
    list_active_chilling_equipment,
    list_chilling_equipment,
    list_chilling_equipment_change_records,
    list_chilling_equipment_temperature_history,
    update_chilling_equipment,
)


router = APIRouter(prefix="/chilling-equipment", tags=["Chilling Equipment"])


def get_current_business_profile_id(current_user: User) -> int:
    if current_user.business_profile_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current user is not linked to a business profile.",
        )

    return current_user.business_profile_id


@router.get("/active", response_model=list[ChillingEquipmentResponse])
def get_active_chilling_equipment(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    business_profile_id = get_current_business_profile_id(current_user)

    return list_active_chilling_equipment(
        db=db,
        business_profile_id=business_profile_id,
    )


@router.post("/", response_model=ChillingEquipmentResponse)
def create_business_chilling_equipment(
    data: ChillingEquipmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    business_profile_id = get_current_business_profile_id(current_user)

    return create_chilling_equipment(
        db=db,
        business_profile_id=business_profile_id,
        data=data,
        user_id=current_user.id,
    )


@router.patch("/{equipment_id}", response_model=ChillingEquipmentResponse)
def update_business_chilling_equipment(
    equipment_id: int,
    data: ChillingEquipmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    business_profile_id = get_current_business_profile_id(current_user)

    return update_chilling_equipment(
        db=db,
        business_profile_id=business_profile_id,
        equipment_id=equipment_id,
        data=data,
        user_id=current_user.id,
    )


@router.patch("/{equipment_id}/deactivate", response_model=ChillingEquipmentResponse)
def deactivate_business_chilling_equipment(
    equipment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    business_profile_id = get_current_business_profile_id(current_user)

    return deactivate_chilling_equipment(
        db=db,
        business_profile_id=business_profile_id,
        equipment_id=equipment_id,
        user_id=current_user.id,
    )


@router.get(
    "/{equipment_id}/change-records",
    response_model=list[ChillingEquipmentChangeRecordResponse],
)
def get_business_chilling_equipment_change_records(
    equipment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    business_profile_id = get_current_business_profile_id(current_user)

    return list_chilling_equipment_change_records(
        db=db,
        business_profile_id=business_profile_id,
        equipment_id=equipment_id,
    )


@router.get(
    "/{equipment_id}/temperature-history",
    response_model=list[ChillingEquipmentTemperatureHistoryResponse],
)
def get_business_chilling_equipment_temperature_history(
    equipment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    business_profile_id = get_current_business_profile_id(current_user)

    return list_chilling_equipment_temperature_history(
        db=db,
        business_profile_id=business_profile_id,
        equipment_id=equipment_id,
    )


@router.get("/", response_model=list[ChillingEquipmentResponse])
def get_chilling_equipment(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    business_profile_id = get_current_business_profile_id(current_user)

    return list_chilling_equipment(
        db=db,
        business_profile_id=business_profile_id,
    )


@router.patch("/{equipment_id}/activate", response_model=ChillingEquipmentResponse)
def activate_business_chilling_equipment(
    equipment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    business_profile_id = get_current_business_profile_id(current_user)

    return activate_chilling_equipment(
        db=db,
        business_profile_id=business_profile_id,
        equipment_id=equipment_id,
        user_id=current_user.id,
    )
