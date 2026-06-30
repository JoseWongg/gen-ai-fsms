from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from gen_ai_fsms.db.base import Base


class ChillingTemperatureIncident(Base):
    __tablename__ = "chilling_temperature_incidents"

    __table_args__ = (
        UniqueConstraint(
            "chilling_temperature_check_id",
            "check_period",
            name="uq_chilling_temp_incident_check_period",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    business_profile_id = Column(
        Integer,
        ForeignKey("business_profiles.id"),
        nullable=False,
        index=True,
    )
    daily_shift_id = Column(
        Integer,
        ForeignKey("daily_shifts.id"),
        nullable=False,
        index=True,
    )
    chilling_temperature_check_id = Column(
        Integer,
        ForeignKey("daily_shift_chilling_temperature_checks.id"),
        nullable=False,
        index=True,
    )
    chilling_equipment_id = Column(
        Integer,
        ForeignKey("business_chilling_equipment.id"),
        nullable=False,
        index=True,
    )

    check_period = Column(String(20), nullable=False)

    equipment_asset_code_snapshot = Column(String(50), nullable=False)
    equipment_name_snapshot = Column(String(255), nullable=False)
    equipment_type_snapshot = Column(String(50), nullable=False)

    recorded_temperature = Column(Numeric(5, 2), nullable=False)
    compliance_threshold = Column(Numeric(5, 2), nullable=False)

    recorded_by_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    recorded_at = Column(DateTime(timezone=True), nullable=True)

    status = Column(String(30), nullable=False, default="open", index=True)

    opened_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    business_profile = relationship("BusinessProfile")
    daily_shift = relationship("DailyShift")
    chilling_temperature_check = relationship("DailyShiftChillingTemperatureCheck")
    chilling_equipment = relationship("BusinessChillingEquipment")
    recorded_by_user = relationship("User", foreign_keys=[recorded_by_user_id])