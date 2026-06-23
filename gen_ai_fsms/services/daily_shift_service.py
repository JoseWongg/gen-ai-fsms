from datetime import date, datetime
from zoneinfo import ZoneInfo
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from gen_ai_fsms.db.models.business_chilling_equipment import BusinessChillingEquipment
from gen_ai_fsms.db.models.daily_shift import DailyShift
from gen_ai_fsms.db.models.daily_shift_chilling_temperature_check import DailyShiftChillingTemperatureCheck
from gen_ai_fsms.db.models.auth.user import User


ACTIVE_STATUS = "active"
ENDED_STATUS = "ended"
SHIFT_TIMEZONE = ZoneInfo("Europe/London") # This sets the timezone to London time. Adjust as needed if application is used in different regions.

def get_current_shift_date() -> date:
    return datetime.now(SHIFT_TIMEZONE).date()

def get_today_shift(
    db: Session,
    business_profile_id: int,
    shift_date: date,
) -> Optional[DailyShift]:
    return (
        db.query(DailyShift)
        .filter(
            DailyShift.business_profile_id == business_profile_id,
            DailyShift.shift_date == shift_date,
        )
        .first()
    )


def get_active_shift(
    db: Session,
    business_profile_id: int,
) -> Optional[DailyShift]:
    return (
        db.query(DailyShift)
        .filter(
            DailyShift.business_profile_id == business_profile_id,
            DailyShift.status == ACTIVE_STATUS,
        )
        .first()
    )


def get_current_shift_state(
    db: Session,
    business_profile_id: int,
    shift_date: date,
) -> dict:
    # Always check for an active shift first.
    # A restaurant shift may continue past midnight, so the current calendar date
    # should not hide a shift that was started on the previous date and is still running.
    active_shift = get_active_shift(
        db=db,
        business_profile_id=business_profile_id,
    )

    if active_shift is not None:
        return {
            "state": ACTIVE_STATUS,
            "shift": active_shift,
        }

    # The shift_date represents the date the shift was started.
    # It is used to prevent duplicate shift starts for the same business profile
    # on the same start date. It is not recalculated when a shift crosses midnight.
    today_shift = get_today_shift(
        db=db,
        business_profile_id=business_profile_id,
        shift_date=shift_date,
    )

    if today_shift is None:
        return {
            "state": "no_shift_today",
            "shift": None,
        }

    return {
        "state": today_shift.status,
        "shift": today_shift,
    }


def start_daily_shift(
    db: Session,
    business_profile_id: int,
    user_id: int,
    shift_date: date,
) -> DailyShift:
    # A new shift cannot be started while another shift is still active.
    # This protects shifts that continue past midnight.
    active_shift = get_active_shift(
        db=db,
        business_profile_id=business_profile_id,
    )

    if active_shift is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A daily shift is already active for this business profile.",
        )
    # The shift_date is the date the new shift is started.
    # A second shift cannot be created for the same business profile
    # with the same start date, even if the previous shift has already ended.
    today_shift = get_today_shift(
        db=db,
        business_profile_id=business_profile_id,
        shift_date=shift_date,
    )

    if today_shift is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A daily shift already exists for this start date.",
        )

    shift = DailyShift(
        business_profile_id=business_profile_id,
        shift_date=shift_date,
        status=ACTIVE_STATUS,
        started_by_user_id=user_id,
        started_at=datetime.now(SHIFT_TIMEZONE),
    )

    db.add(shift)
    db.commit()
    db.refresh(shift)

    return shift


def validate_shift_can_be_ended(
    db: Session,
    shift: DailyShift,
) -> None:
    progress = get_fridge_temperature_checklist_progress_for_active_shift(
        db=db,
        business_profile_id=shift.business_profile_id,
    )

    required_temperature_count = progress["required_temperature_count"]
    completed_temperature_count = progress["completed_temperature_count"]

    if required_temperature_count == 0:
        return None

    if completed_temperature_count < required_temperature_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to end shift due to incomplete checklist.",
        )

    return None


def end_daily_shift(
    db: Session,
    business_profile_id: int,
    user_id: int,
    end_notes: Optional[str] = None,
) -> DailyShift:
    active_shift = get_active_shift(
        db=db,
        business_profile_id=business_profile_id,
    )

    if active_shift is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="There is no active daily shift to end.",
        )

    validate_shift_can_be_ended(db=db, shift=active_shift)

    active_shift.status = ENDED_STATUS
    active_shift.ended_by_user_id = user_id
    active_shift.ended_at = datetime.now(SHIFT_TIMEZONE)
    active_shift.end_notes = end_notes

    db.commit()
    db.refresh(active_shift)

    return active_shift

def list_daily_shifts(
    db: Session,
    business_profile_id: int,
    shift_date: Optional[date] = None,
) -> list[DailyShift]:
    query = db.query(DailyShift).filter(
        DailyShift.business_profile_id == business_profile_id,
    )

    if shift_date is not None:
        query = query.filter(DailyShift.shift_date == shift_date)

    return (
        query
        .order_by(
            DailyShift.shift_date.desc(),
            DailyShift.started_at.desc(),
        )
        .all()
    )

def get_or_create_chilling_temperature_checks_for_active_shift(
    db: Session,
    business_profile_id: int,
) -> list[DailyShiftChillingTemperatureCheck]:
    active_shift = get_active_shift(
        db=db,
        business_profile_id=business_profile_id,
    )

    if active_shift is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="There is no active daily shift.",
        )

    active_equipment_items = (
        db.query(BusinessChillingEquipment)
        .filter(
            BusinessChillingEquipment.business_profile_id == business_profile_id,
            BusinessChillingEquipment.is_active.is_(True),
        )
        .order_by(BusinessChillingEquipment.id.asc())
        .all()
    )

    if not active_equipment_items:
        return []

    existing_checks = (
        db.query(DailyShiftChillingTemperatureCheck)
        .filter(
            DailyShiftChillingTemperatureCheck.daily_shift_id == active_shift.id,
        )
        .all()
    )

    existing_by_equipment_id = {
        check.chilling_equipment_id: check
        for check in existing_checks
    }

    for equipment in active_equipment_items:
        if equipment.id in existing_by_equipment_id:
            continue

        check = DailyShiftChillingTemperatureCheck(
            daily_shift_id=active_shift.id,
            chilling_equipment_id=equipment.id,
            equipment_asset_code_snapshot=equipment.equipment_asset_code,
            equipment_name_snapshot=equipment.equipment_name,
            equipment_use_snapshot=equipment.equipment_use,
            equipment_type_snapshot=equipment.equipment_type,
            temperature_check_method_snapshot=equipment.temperature_check_method,
        )
        db.add(check)

    db.commit()

    return (
        db.query(DailyShiftChillingTemperatureCheck)
        .filter(
            DailyShiftChillingTemperatureCheck.daily_shift_id == active_shift.id,
        )
        .order_by(DailyShiftChillingTemperatureCheck.id.asc())
        .all()
    )

def update_chilling_temperature_check_for_active_shift(
    db: Session,
    business_profile_id: int,
    user_id: int,
    check_id: int,
    update_data: dict,
) -> DailyShiftChillingTemperatureCheck:
    active_shift = get_active_shift(
        db=db,
        business_profile_id=business_profile_id,
    )

    if active_shift is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="There is no active daily shift.",
        )

    allowed_fields = {"am_temperature", "pm_temperature"}
    provided_fields = [
        field_name
        for field_name in allowed_fields
        if field_name in update_data
    ]

    if not provided_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide an AM temperature or PM temperature to update.",
        )

    check = (
        db.query(DailyShiftChillingTemperatureCheck)
        .filter(
            DailyShiftChillingTemperatureCheck.id == check_id,
            DailyShiftChillingTemperatureCheck.daily_shift_id == active_shift.id,
        )
        .first()
    )

    if check is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fridge temperature check row was not found for the active shift.",
        )

    recorded_at = datetime.now(SHIFT_TIMEZONE)

    for field_name in provided_fields:
        temperature_value = update_data[field_name]

        if temperature_value is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} cannot be empty.",
            )

        if field_name == "am_temperature":
            check.am_temperature = temperature_value
            check.am_recorded_by_user_id = user_id
            check.am_recorded_at = recorded_at

        if field_name == "pm_temperature":
            check.pm_temperature = temperature_value
            check.pm_recorded_by_user_id = user_id
            check.pm_recorded_at = recorded_at

    db.commit()
    db.refresh(check)

    return check

def calculate_fridge_temperature_checklist_progress(
    checks: list[DailyShiftChillingTemperatureCheck],
) -> dict:
    total_rows = len(checks)

    if total_rows == 0:
        return {
            "progress_percentage": 100.0,
            "completed_temperature_count": 0,
            "required_temperature_count": 0,
            "total_rows": 0,
            "completed_rows": 0,
        }

    required_temperature_count = total_rows * 2

    completed_temperature_count = 0
    completed_rows = 0

    for check in checks:
        am_complete = check.am_temperature is not None
        pm_complete = check.pm_temperature is not None

        if am_complete:
            completed_temperature_count += 1

        if pm_complete:
            completed_temperature_count += 1

        if am_complete and pm_complete:
            completed_rows += 1

    progress_percentage = round(
        (completed_temperature_count / required_temperature_count) * 100,
        1,
    )

    return {
        "progress_percentage": progress_percentage,
        "completed_temperature_count": completed_temperature_count,
        "required_temperature_count": required_temperature_count,
        "total_rows": total_rows,
        "completed_rows": completed_rows,
    }


def get_fridge_temperature_checklist_progress_for_active_shift(
    db: Session,
    business_profile_id: int,
) -> dict:
    checks = get_or_create_chilling_temperature_checks_for_active_shift(
        db=db,
        business_profile_id=business_profile_id,
    )

    return calculate_fridge_temperature_checklist_progress(checks)

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


def list_fridge_temperature_checks_for_shift_archive(
    db: Session,
    business_profile_id: int,
    shift_id: int,
) -> list[dict]:
    shift = (
        db.query(DailyShift)
        .filter(
            DailyShift.id == shift_id,
            DailyShift.business_profile_id == business_profile_id,
        )
        .first()
    )

    if shift is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Daily shift was not found for this business profile.",
        )

    checks = (
        db.query(DailyShiftChillingTemperatureCheck)
        .filter(DailyShiftChillingTemperatureCheck.daily_shift_id == shift.id)
        .order_by(DailyShiftChillingTemperatureCheck.id.asc())
        .all()
    )

    return [
        {
            "id": check.id,
            "daily_shift_id": check.daily_shift_id,
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
