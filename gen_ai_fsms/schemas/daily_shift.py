from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class DailyShiftEndRequest(BaseModel):
    end_notes: Optional[str] = None


class DailyShiftResponse(BaseModel):
    id: int
    business_profile_id: int
    shift_date: date
    status: str
    started_by_user_id: int
    started_by_name: Optional[str] = None
    started_at: datetime
    ended_by_user_id: Optional[int] = None
    ended_by_name: Optional[str] = None
    ended_at: Optional[datetime] = None
    end_notes: Optional[str] = None

    class Config:
        from_attributes = True


class DailyShiftCurrentResponse(BaseModel):
    state: str
    shift: Optional[DailyShiftResponse] = None