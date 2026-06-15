from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from gen_ai_fsms.api.deps import get_current_user, get_db, require_admin
from gen_ai_fsms.db.models import User
from gen_ai_fsms.schemas.daily_shift import (
    DailyShiftCurrentResponse,
    DailyShiftEndRequest,
    DailyShiftResponse,
)
from gen_ai_fsms.services.daily_shift_service import (
    end_daily_shift,
    get_current_shift_date,
    get_current_shift_state,
    start_daily_shift,
)


router = APIRouter(prefix="/daily-shifts", tags=["Daily Shifts"])


def get_current_business_profile_id(current_user: User) -> int:
    if current_user.business_profile_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current user is not linked to a business profile.",
        )

    return current_user.business_profile_id


@router.get("/current", response_model=DailyShiftCurrentResponse)
def get_current_daily_shift(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    business_profile_id = get_current_business_profile_id(current_user)
    shift_date = get_current_shift_date()

    return get_current_shift_state(
        db=db,
        business_profile_id=business_profile_id,
        shift_date=shift_date,
    )


@router.post("/start", response_model=DailyShiftResponse)
def start_current_daily_shift(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    business_profile_id = get_current_business_profile_id(current_user)
    shift_date = get_current_shift_date()

    return start_daily_shift(
        db=db,
        business_profile_id=business_profile_id,
        user_id=current_user.id,
        shift_date=shift_date,
    )


@router.post("/end", response_model=DailyShiftResponse)
def end_current_daily_shift(
    data: DailyShiftEndRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    business_profile_id = get_current_business_profile_id(current_user)

    return end_daily_shift(
        db=db,
        business_profile_id=business_profile_id,
        user_id=current_user.id,
        end_notes=data.end_notes,
    )