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
