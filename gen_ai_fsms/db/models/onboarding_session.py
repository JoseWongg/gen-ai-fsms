from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from gen_ai_fsms.db.base import Base

class OnboardingSession(Base):
    __tablename__ = "onboarding_sessions"

    id = Column(Integer, primary_key=True, index=True)
    business_profile_id = Column(Integer, ForeignKey("business_profiles.id"), nullable=False)
    user_id = Column(Integer, nullable=False)          # admin user who started the session
    phase = Column(String(50), nullable=False)        # "screening" or "safety_point_approval"
    state_json = Column(Text, nullable=True)          # JSON workflow state
    status = Column(String(20), default="in_progress") # in_progress, completed, abandoned
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
