from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel


EquipmentUse = Literal["storage", "display"]
EquipmentType = Literal["fridge", "freezer"]
TemperatureCheckMethod = Literal[
    "digital_or_dial_display",
    "probe_between_packs",
]


class ChillingEquipmentCreate(BaseModel):
    equipment_name: str
    equipment_use: EquipmentUse
    equipment_type: EquipmentType
    temperature_check_method: TemperatureCheckMethod
    source_safety_point_id: str = "4.1.1.3"


class ChillingEquipmentUpdate(BaseModel):
    equipment_name: Optional[str] = None
    equipment_use: Optional[EquipmentUse] = None
    equipment_type: Optional[EquipmentType] = None
    temperature_check_method: Optional[TemperatureCheckMethod] = None
    source_safety_point_id: Optional[str] = None


class ChillingEquipmentResponse(BaseModel):
    id: int
    business_profile_id: int
    source_safety_point_id: str
    equipment_asset_code: str
    equipment_name: str
    equipment_use: str
    equipment_type: str
    temperature_check_method: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ChillingEquipmentTemperatureHistoryResponse(BaseModel):
    id: int
    daily_shift_id: int
    shift_date: date
    shift_status: str
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


class ChillingEquipmentChangeRecordResponse(BaseModel):
    id: int
    business_profile_id: int
    chilling_equipment_id: int
    change_type: str
    field_name: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    changed_by_user_id: Optional[int] = None
    changed_by_name: Optional[str] = None
    changed_at: datetime

    class Config:
        from_attributes = True
