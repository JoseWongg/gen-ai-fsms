from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from gen_ai_fsms.db.base import Base


class ChillingTemperatureCorrectiveAction(Base):
    __tablename__ = "chilling_temperature_corrective_actions"
    __table_args__ = (
        UniqueConstraint(
            "incident_id",
            name="uq_chilling_temp_corrective_action_incident",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    incident_id = Column(
        Integer,
        ForeignKey("chilling_temperature_incidents.id"),
        nullable=False,
    )
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
    recorded_by_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    final_narrative = Column(Text, nullable=False)
    structured_facts_json = Column(Text, nullable=True)
    validation_status = Column(String(30), nullable=False, default="approved", index=True)

    approved_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    incident = relationship("ChillingTemperatureIncident")
    business_profile = relationship("BusinessProfile")
    daily_shift = relationship("DailyShift")
    recorded_by_user = relationship("User", foreign_keys=[recorded_by_user_id])