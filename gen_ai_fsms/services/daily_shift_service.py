from datetime import date, datetime
from zoneinfo import ZoneInfo
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from gen_ai_fsms.db.models.daily_shift import DailyShift


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
    active_shift = get_active_shift(
        db=db,
        business_profile_id=business_profile_id,
    )

    if active_shift is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A daily shift is already active for this business profile.",
        )

    today_shift = get_today_shift(
        db=db,
        business_profile_id=business_profile_id,
        shift_date=shift_date,
    )

    if today_shift is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A daily shift already exists for today.",
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