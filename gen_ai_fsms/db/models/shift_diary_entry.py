from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from gen_ai_fsms.db.base import Base


class ShiftDiaryEntry(Base):
    __tablename__ = "shift_diary_entries"

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
    created_by_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    entry_type = Column(String(50), nullable=False, default="general", index=True)
    title = Column(String(255), nullable=True)
    entry_text = Column(Text, nullable=False)

    related_entity_type = Column(String(100), nullable=True)
    related_entity_id = Column(Integer, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    business_profile = relationship("BusinessProfile")
    daily_shift = relationship("DailyShift")
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])