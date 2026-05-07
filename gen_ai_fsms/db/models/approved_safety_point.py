from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from gen_ai_fsms.db.base import Base

class ApprovedSafetyPoint(Base):
    __tablename__ = "approved_safety_points"

    id = Column(Integer, primary_key=True, index=True)
    business_profile_id = Column(Integer, ForeignKey("business_profiles.id"), nullable=False)
    safety_point_id = Column(String(50), nullable=False, index=True)
    safe_method_id = Column(String(50), nullable=False)
    safe_method_name = Column(String(255), nullable=False)
    safety_point_text = Column(Text, nullable=False)
    approved_by_user_id = Column(Integer, nullable=False)
    approved_at = Column(DateTime(timezone=True), server_default=func.now())
