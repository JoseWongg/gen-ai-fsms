from datetime import datetime
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
