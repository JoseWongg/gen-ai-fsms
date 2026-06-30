from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from gen_ai_fsms.db.base import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)

    recipient_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    business_profile_id = Column(
        Integer,
        ForeignKey("business_profiles.id"),
        nullable=True,
        index=True,
    )

    daily_shift_id = Column(
        Integer,
        ForeignKey("daily_shifts.id"),
        nullable=True,
        index=True,
    )

    notification_type = Column(String(100), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)

    related_entity_type = Column(String(100), nullable=True)
    related_entity_id = Column(Integer, nullable=True)

    action_route = Column(String(255), nullable=True)

    status = Column(String(20), nullable=False, default="unread", index=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    read_at = Column(DateTime(timezone=True), nullable=True)

    recipient_user = relationship("User", foreign_keys=[recipient_user_id])
    business_profile = relationship("BusinessProfile")
    daily_shift = relationship("DailyShift")