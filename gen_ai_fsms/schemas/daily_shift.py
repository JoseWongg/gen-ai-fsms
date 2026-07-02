from datetime import date, datetime
from decimal import Decimal
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


class DailyShiftIncidentSummaryResponse(BaseModel):
    temp_alert_count: int
    unresolved_incident_count: int


class FridgeTemperatureChecklistProgressResponse(BaseModel):
    progress_percentage: float
    completed_temperature_count: int
    required_temperature_count: int
    total_rows: int
    completed_rows: int


class DailyShiftChillingTemperatureCheckUpdateRequest(BaseModel):
    am_temperature: Optional[Decimal] = None
    pm_temperature: Optional[Decimal] = None


class ArchiveFridgeTemperatureCheckResponse(BaseModel):
    id: int
    daily_shift_id: int
    equipment_asset_code_snapshot: str
    equipment_name_snapshot: str
    equipment_use_snapshot: str
    equipment_type_snapshot: str
    temperature_check_method_snapshot: str
    am_temperature: Optional[Decimal] = None
    am_recorded_by_user_id: Optional[int] = None
    am_recorded_by_name: Optional[str] = None
    am_recorded_at: Optional[datetime] = None
    pm_temperature: Optional[Decimal] = None
    pm_recorded_by_user_id: Optional[int] = None
    pm_recorded_by_name: Optional[str] = None
    pm_recorded_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class DailyShiftChillingTemperatureCheckResponse(BaseModel):
    id: int
    daily_shift_id: int
    chilling_equipment_id: int
    equipment_asset_code_snapshot: str
    equipment_name_snapshot: str
    equipment_use_snapshot: str
    equipment_type_snapshot: str
    temperature_check_method_snapshot: str
    am_temperature: Optional[Decimal] = None
    am_recorded_by_user_id: Optional[int] = None
    am_recorded_at: Optional[datetime] = None
    pm_temperature: Optional[Decimal] = None
    pm_recorded_by_user_id: Optional[int] = None
    pm_recorded_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
