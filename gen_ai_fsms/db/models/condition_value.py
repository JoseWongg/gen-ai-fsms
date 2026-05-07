from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from gen_ai_fsms.db.base import Base

class ConditionValue(Base):
    __tablename__ = "condition_values"

    id = Column(Integer, primary_key=True, index=True)
    business_profile_id = Column(Integer, ForeignKey("business_profiles.id"), nullable=False)
    condition_id = Column(String(50), nullable=False, index=True)
    value = Column(String(20), nullable=False)  # true, false, unknown, not_asked
    source = Column(String(50), default="user_answer")
    answered_at = Column(DateTime(timezone=True), server_default=func.now())
    last_updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    notes = Column(Text, nullable=True)
