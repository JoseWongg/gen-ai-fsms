from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ShiftDiaryEntryResponse(BaseModel):
    id: int
    business_profile_id: int
    daily_shift_id: int
    created_by_user_id: int
    created_by_name: Optional[str] = None
    entry_type: str
    title: Optional[str] = None
    entry_text: str
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None