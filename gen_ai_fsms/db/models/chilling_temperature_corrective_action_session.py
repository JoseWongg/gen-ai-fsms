from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from gen_ai_fsms.db.base import Base


class ChillingTemperatureCorrectiveActionSession(Base):
    __tablename__ = "chilling_temperature_corrective_action_sessions"
    __table_args__ = (
        UniqueConstraint(
            "incident_id",
            name="uq_chilling_temp_corrective_action_session_incident",
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
    started_by_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    status = Column(String(30), nullable=False, default="in_progress", index=True)
    current_stage = Column(String(50), nullable=False, default="gathering", index=True)

    state_json = Column(Text, nullable=True)
    issues_json = Column(Text, nullable=True)
    conversation_history_json = Column(Text, nullable=True)
    final_summary = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    incident = relationship("ChillingTemperatureIncident")
    business_profile = relationship("BusinessProfile")
    daily_shift = relationship("DailyShift")
    started_by_user = relationship("User", foreign_keys=[started_by_user_id])