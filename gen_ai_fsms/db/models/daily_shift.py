from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

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