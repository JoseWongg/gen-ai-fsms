from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from gen_ai_fsms.db.base import Base


class BusinessChillingEquipment(Base):
    __tablename__ = "business_chilling_equipment"

    id = Column(Integer, primary_key=True, index=True)
    business_profile_id = Column(
        Integer,
        ForeignKey("business_profiles.id"),
        nullable=False,
        index=True,
    )
    source_safety_point_id = Column(String(50), nullable=False, default="4.1.1.3")
    equipment_name = Column(String(255), nullable=False)
    equipment_use = Column(String(50), nullable=False)
    equipment_type = Column(String(50), nullable=False)
    temperature_check_method = Column(String(100), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
