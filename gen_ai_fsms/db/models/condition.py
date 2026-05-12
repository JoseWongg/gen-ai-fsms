from sqlalchemy import Column, Integer, String, Text
from gen_ai_fsms.db.base import Base

class Condition(Base):
    __tablename__ = "conditions"

    id = Column(Integer, primary_key=True, index=True)
    condition_id = Column(String(50), unique=True, nullable=False, index=True)
    condition_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), default="active")
