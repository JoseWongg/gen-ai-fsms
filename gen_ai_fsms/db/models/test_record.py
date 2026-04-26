from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from gen_ai_fsms.db.base import Base

class TestRecord(Base):
    __tablename__ = "test_records"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
