from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from gen_ai_fsms.db.base import Base


class DailyShift(Base):
    __tablename__ = "daily_shifts"

    __table_args__ = (
        UniqueConstraint(
            "business_profile_id",
            "shift_date",
            name="uq_daily_shifts_business_profile_date",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    business_profile_id = Column(
        Integer,
        ForeignKey("business_profiles.id"),
        nullable=False,
        index=True,
    )
    shift_date = Column(Date, nullable=False, index=True)
    status = Column(String(20), nullable=False, default="active")
    started_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ended_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    end_notes = Column(Text, nullable=True)

    started_by_user = relationship("User", foreign_keys=[started_by_user_id])
    ended_by_user = relationship("User", foreign_keys=[ended_by_user_id])

    @staticmethod
    def _format_user_name(user):
        if not user:
            return None

        name_parts = [
            part
            for part in (user.first_name, user.last_name)
            if part
        ]

        if name_parts:
            return " ".join(name_parts)

        return user.email

    @property
    def started_by_name(self):
        return self._format_user_name(self.started_by_user)

    @property
    def ended_by_name(self):
        return self._format_user_name(self.ended_by_user)
