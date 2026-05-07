from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from gen_ai_fsms.db.base import Base

class BusinessProfile(Base):
    __tablename__ = "business_profiles"

    id = Column(Integer, primary_key=True, index=True)
    business_name = Column(String(255), nullable=False)
    site_name = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    status = Column(String(50), default="active")
