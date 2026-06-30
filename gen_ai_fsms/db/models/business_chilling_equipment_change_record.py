from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from gen_ai_fsms.db.base import Base


class BusinessChillingEquipmentChangeRecord(Base):
    __tablename__ = "business_chilling_equipment_change_records"

    id = Column(Integer, primary_key=True, index=True)

    business_profile_id = Column(
        Integer,
        ForeignKey("business_profiles.id"),
        nullable=False,
        index=True,
    )
    chilling_equipment_id = Column(
        Integer,
        ForeignKey("business_chilling_equipment.id"),
        nullable=False,
        index=True,
    )

    change_type = Column(String(50), nullable=False)
    field_name = Column(String(100), nullable=True)

    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)

    changed_by_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    changed_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    equipment = relationship("BusinessChillingEquipment")
    changed_by_user = relationship("User")
