from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from gen_ai_fsms.db.models.auth.user import User
from gen_ai_fsms.db.models.business_chilling_equipment import BusinessChillingEquipment
from gen_ai_fsms.db.models.business_chilling_equipment_change_record import (
    BusinessChillingEquipmentChangeRecord,
)
from gen_ai_fsms.db.models.daily_shift import DailyShift
from gen_ai_fsms.db.models.daily_shift_chilling_temperature_check import (
    DailyShiftChillingTemperatureCheck,
)
from gen_ai_fsms.schemas.chilling_equipment import (
    ChillingEquipmentCreate,
    ChillingEquipmentUpdate,
)


CHILLING_EQUIPMENT_TIMEZONE = ZoneInfo("Europe/London")



TRACKED_EQUIPMENT_FIELDS = (
    "equipment_name",
    "equipment_use",
    "equipment_type",
    "temperature_check_method",
)


def normalise_change_value(value):
    if value is None:
        return None

    if isinstance(value, bool):
        return "true" if value else "false"

    return str(value)


def build_chilling_equipment_state_summary(
    equipment: BusinessChillingEquipment,
) -> str:
    return (
        f"asset_code={equipment.equipment_asset_code}; "
        f"name={equipment.equipment_name}; "
        f"use={equipment.equipment_use}; "
        f"type={equipment.equipment_type}; "
        f"temperature_check_method={equipment.temperature_check_method}; "
        f"is_active={normalise_change_value(equipment.is_active)}"
    )


def record_chilling_equipment_change(
    db: Session,
    business_profile_id: int,
    chilling_equipment_id: int,
    change_type: str,
    field_name: str | None = None,
    old_value=None,
    new_value=None,
    changed_by_user_id: int | None = None,
) -> BusinessChillingEquipmentChangeRecord:
    change_record = BusinessChillingEquipmentChangeRecord(
        business_profile_id=business_profile_id,
        chilling_equipment_id=chilling_equipment_id,
        change_type=change_type,
        field_name=field_name,
        old_value=normalise_change_value(old_value),
        new_value=normalise_change_value(new_value),
        changed_by_user_id=changed_by_user_id,
    )

    db.add(change_record)
    return change_record


def record_chilling_equipment_field_changes(
    db: Session,
    business_profile_id: int,
    equipment: BusinessChillingEquipment,
    old_values: dict,
    changed_by_user_id: int | None = None,
) -> None:
    for field_name in TRACKED_EQUIPMENT_FIELDS:
        old_value = old_values.get(field_name)
        new_value = getattr(equipment, field_name)

        if normalise_change_value(old_value) == normalise_change_value(new_value):
            continue

        record_chilling_equipment_change(
            db=db,
            business_profile_id=business_profile_id,
            chilling_equipment_id=equipment.id,
            change_type="updated",
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            changed_by_user_id=changed_by_user_id,
        )




def generate_chilling_equipment_asset_code(
    equipment: BusinessChillingEquipment,
) -> str:
    created_date = datetime.now(CHILLING_EQUIPMENT_TIMEZONE).strftime("%Y%m%d")
    return f"CHILL-{created_date}-{equipment.id:04d}"


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
    user_id: int | None = None,
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
        equipment_asset_code=f"PENDING-{uuid4().hex}",
    )

    db.add(equipment)
    db.flush()

    equipment.equipment_asset_code = generate_chilling_equipment_asset_code(equipment)

    record_chilling_equipment_change(
        db=db,
        business_profile_id=business_profile_id,
        chilling_equipment_id=equipment.id,
        change_type="created",
        field_name="current_state",
        old_value=None,
        new_value=build_chilling_equipment_state_summary(equipment),
        changed_by_user_id=user_id,
    )

    db.commit()
    db.refresh(equipment)

    return equipment


def update_chilling_equipment(
    db: Session,
    business_profile_id: int,
    equipment_id: int,
    data: ChillingEquipmentUpdate,
    user_id: int | None = None,
) -> BusinessChillingEquipment:
    equipment = get_chilling_equipment_for_business(
        db=db,
        business_profile_id=business_profile_id,
        equipment_id=equipment_id,
    )

    update_data = data.model_dump(exclude_unset=True)

    old_values = {
        field_name: getattr(equipment, field_name)
        for field_name in TRACKED_EQUIPMENT_FIELDS
    }

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

    record_chilling_equipment_field_changes(
        db=db,
        business_profile_id=business_profile_id,
        equipment=equipment,
        old_values=old_values,
        changed_by_user_id=user_id,
    )

    db.commit()
    db.refresh(equipment)

    return equipment


def deactivate_chilling_equipment(
    db: Session,
    business_profile_id: int,
    equipment_id: int,
    user_id: int | None = None,
) -> BusinessChillingEquipment:
    equipment = get_chilling_equipment_for_business(
        db=db,
        business_profile_id=business_profile_id,
        equipment_id=equipment_id,
    )

    active_shift_ids = [
        shift_id
        for (shift_id,) in (
            db.query(DailyShift.id)
            .filter(
                DailyShift.business_profile_id == business_profile_id,
                DailyShift.status == "active",
            )
            .all()
        )
    ]

    was_active = bool(equipment.is_active)

    if active_shift_ids:
        (
            db.query(DailyShiftChillingTemperatureCheck)
            .filter(
                DailyShiftChillingTemperatureCheck.daily_shift_id.in_(
                    active_shift_ids
                ),
                DailyShiftChillingTemperatureCheck.chilling_equipment_id
                == equipment.id,
            )
            .delete(synchronize_session=False)
        )

    equipment.is_active = False

    if was_active:
        record_chilling_equipment_change(
            db=db,
            business_profile_id=business_profile_id,
            chilling_equipment_id=equipment.id,
            change_type="deactivated",
            field_name="is_active",
            old_value=True,
            new_value=False,
            changed_by_user_id=user_id,
        )

    db.commit()
    db.refresh(equipment)

    return equipment


def format_user_display_name(user: User | None) -> str | None:
    if user is None:
        return None

    full_name_parts = [
        user.first_name,
        user.last_name,
    ]
    full_name = " ".join(
        part.strip()
        for part in full_name_parts
        if part and part.strip()
    )

    if full_name:
        return full_name

    return user.email


def list_chilling_equipment_change_records(
    db: Session,
    business_profile_id: int,
    equipment_id: int,
) -> list[dict]:
    equipment = get_chilling_equipment_for_business(
        db=db,
        business_profile_id=business_profile_id,
        equipment_id=equipment_id,
    )

    change_records = (
        db.query(BusinessChillingEquipmentChangeRecord)
        .filter(
            BusinessChillingEquipmentChangeRecord.business_profile_id
            == business_profile_id,
            BusinessChillingEquipmentChangeRecord.chilling_equipment_id
            == equipment.id,
        )
        .order_by(
            BusinessChillingEquipmentChangeRecord.changed_at.desc(),
            BusinessChillingEquipmentChangeRecord.id.desc(),
        )
        .all()
    )

    return [
        {
            "id": record.id,
            "business_profile_id": record.business_profile_id,
            "chilling_equipment_id": record.chilling_equipment_id,
            "change_type": record.change_type,
            "field_name": record.field_name,
            "old_value": record.old_value,
            "new_value": record.new_value,
            "changed_by_user_id": record.changed_by_user_id,
            "changed_by_name": format_user_display_name(record.changed_by_user),
            "changed_at": record.changed_at,
        }
        for record in change_records
    ]


def list_chilling_equipment_temperature_history(
    db: Session,
    business_profile_id: int,
    equipment_id: int,
) -> list[dict]:
    equipment = get_chilling_equipment_for_business(
        db=db,
        business_profile_id=business_profile_id,
        equipment_id=equipment_id,
    )

    checks = (
        db.query(DailyShiftChillingTemperatureCheck)
        .join(
            DailyShift,
            DailyShift.id == DailyShiftChillingTemperatureCheck.daily_shift_id,
        )
        .filter(
            DailyShift.business_profile_id == business_profile_id,
            DailyShiftChillingTemperatureCheck.chilling_equipment_id == equipment.id,
        )
        .order_by(
            DailyShift.shift_date.desc(),
            DailyShift.started_at.desc(),
            DailyShiftChillingTemperatureCheck.id.desc(),
        )
        .all()
    )

    return [
        {
            "id": check.id,
            "daily_shift_id": check.daily_shift_id,
            "shift_date": check.daily_shift.shift_date,
            "shift_status": check.daily_shift.status,
            "equipment_asset_code_snapshot": check.equipment_asset_code_snapshot,
            "equipment_name_snapshot": check.equipment_name_snapshot,
            "equipment_use_snapshot": check.equipment_use_snapshot,
            "equipment_type_snapshot": check.equipment_type_snapshot,
            "temperature_check_method_snapshot": check.temperature_check_method_snapshot,
            "am_temperature": check.am_temperature,
            "am_recorded_by_user_id": check.am_recorded_by_user_id,
            "am_recorded_by_name": format_user_display_name(check.am_recorded_by_user),
            "am_recorded_at": check.am_recorded_at,
            "pm_temperature": check.pm_temperature,
            "pm_recorded_by_user_id": check.pm_recorded_by_user_id,
            "pm_recorded_by_name": format_user_display_name(check.pm_recorded_by_user),
            "pm_recorded_at": check.pm_recorded_at,
            "created_at": check.created_at,
            "updated_at": check.updated_at,
        }
        for check in checks
    ]

def list_chilling_equipment(
    db: Session,
    business_profile_id: int,
) -> list[BusinessChillingEquipment]:
    return (
        db.query(BusinessChillingEquipment)
        .filter(BusinessChillingEquipment.business_profile_id == business_profile_id)
        .order_by(
            BusinessChillingEquipment.is_active.desc(),
            BusinessChillingEquipment.equipment_name.asc(),
            BusinessChillingEquipment.id.asc(),
        )
        .all()
    )


def activate_chilling_equipment(
    db: Session,
    business_profile_id: int,
    equipment_id: int,
    user_id: int | None = None,
) -> BusinessChillingEquipment:
    equipment = get_chilling_equipment_for_business(
        db=db,
        business_profile_id=business_profile_id,
        equipment_id=equipment_id,
    )

    was_active = bool(equipment.is_active)

    equipment.is_active = True

    if not was_active:
        record_chilling_equipment_change(
            db=db,
            business_profile_id=business_profile_id,
            chilling_equipment_id=equipment.id,
            change_type="activated",
            field_name="is_active",
            old_value=False,
            new_value=True,
            changed_by_user_id=user_id,
        )

    db.commit()
    db.refresh(equipment)

    return equipment
