from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from gen_ai_fsms.db.base import Base


class DailyShiftChillingTemperatureCheck(Base):
    __tablename__ = "daily_shift_chilling_temperature_checks"

    __table_args__ = (
        UniqueConstraint(
            "daily_shift_id",
            "chilling_equipment_id",
            name="uq_daily_shift_chilling_temperature_equipment",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    daily_shift_id = Column(
        Integer,
        ForeignKey("daily_shifts.id"),
        nullable=False,
        index=True,
    )
    chilling_equipment_id = Column(
        Integer,
        ForeignKey("business_chilling_equipment.id"),
        nullable=False,
        index=True,
    )

    equipment_asset_code_snapshot = Column(String(50), nullable=False)
    equipment_name_snapshot = Column(String(255), nullable=False)
    equipment_use_snapshot = Column(String(50), nullable=False)
    equipment_type_snapshot = Column(String(50), nullable=False)
    temperature_check_method_snapshot = Column(String(100), nullable=False)

    am_temperature = Column(Numeric(5, 2), nullable=True)
    am_recorded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    am_recorded_at = Column(DateTime(timezone=True), nullable=True)

    pm_temperature = Column(Numeric(5, 2), nullable=True)
    pm_recorded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    pm_recorded_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    daily_shift = relationship("DailyShift")
    chilling_equipment = relationship("BusinessChillingEquipment")
    am_recorded_by_user = relationship("User", foreign_keys=[am_recorded_by_user_id])
    pm_recorded_by_user = relationship("User", foreign_keys=[pm_recorded_by_user_id])
