from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from gen_ai_fsms.db.models.business_chilling_equipment import BusinessChillingEquipment
from gen_ai_fsms.schemas.chilling_equipment import (
    ChillingEquipmentCreate,
    ChillingEquipmentUpdate,
)


def _clean_required_text(value: str, field_name: str) -> str:
    cleaned_value = value.strip()

    if not cleaned_value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} cannot be empty.",
        )

    return cleaned_value


def list_active_chilling_equipment(
    db: Session,
    business_profile_id: int,
) -> list[BusinessChillingEquipment]:
    return (
        db.query(BusinessChillingEquipment)
        .filter(
            BusinessChillingEquipment.business_profile_id == business_profile_id,
            BusinessChillingEquipment.is_active.is_(True),
        )
        .order_by(BusinessChillingEquipment.id.asc())
        .all()
    )


def get_chilling_equipment_for_business(
    db: Session,
    business_profile_id: int,
    equipment_id: int,
) -> BusinessChillingEquipment:
    equipment = (
        db.query(BusinessChillingEquipment)
        .filter(
            BusinessChillingEquipment.id == equipment_id,
            BusinessChillingEquipment.business_profile_id == business_profile_id,
        )
        .first()
    )

    if equipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chilling equipment item was not found.",
        )

    return equipment


def create_chilling_equipment(
    db: Session,
    business_profile_id: int,
    data: ChillingEquipmentCreate,
) -> BusinessChillingEquipment:
    equipment = BusinessChillingEquipment(
        business_profile_id=business_profile_id,
        source_safety_point_id=_clean_required_text(
            data.source_safety_point_id,
            "source_safety_point_id",
        ),
        equipment_name=_clean_required_text(
            data.equipment_name,
            "equipment_name",
        ),
        equipment_use=data.equipment_use,
        equipment_type=data.equipment_type,
        temperature_check_method=data.temperature_check_method,
        is_active=True,
    )

    db.add(equipment)
    db.commit()
    db.refresh(equipment)

    return equipment


def update_chilling_equipment(
    db: Session,
    business_profile_id: int,
    equipment_id: int,
    data: ChillingEquipmentUpdate,
) -> BusinessChillingEquipment:
    equipment = get_chilling_equipment_for_business(
        db=db,
        business_profile_id=business_profile_id,
        equipment_id=equipment_id,
    )

    update_data = data.model_dump(exclude_unset=True)

    if "equipment_name" in update_data and update_data["equipment_name"] is not None:
        equipment.equipment_name = _clean_required_text(
            update_data["equipment_name"],
            "equipment_name",
        )

    if "source_safety_point_id" in update_data and update_data["source_safety_point_id"] is not None:
        equipment.source_safety_point_id = _clean_required_text(
            update_data["source_safety_point_id"],
            "source_safety_point_id",
        )

    if "equipment_use" in update_data and update_data["equipment_use"] is not None:
        equipment.equipment_use = update_data["equipment_use"]

    if "equipment_type" in update_data and update_data["equipment_type"] is not None:
        equipment.equipment_type = update_data["equipment_type"]

    if "temperature_check_method" in update_data and update_data["temperature_check_method"] is not None:
        equipment.temperature_check_method = update_data["temperature_check_method"]

    db.commit()
    db.refresh(equipment)

    return equipment


def deactivate_chilling_equipment(
    db: Session,
    business_profile_id: int,
    equipment_id: int,
) -> BusinessChillingEquipment:
    equipment = get_chilling_equipment_for_business(
        db=db,
        business_profile_id=business_profile_id,
        equipment_id=equipment_id,
    )

    equipment.is_active = False

    db.commit()
    db.refresh(equipment)

    return equipment
