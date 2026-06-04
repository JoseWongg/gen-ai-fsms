from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from gen_ai_fsms.db.base import Base


class ApprovedSafetyPointResponse(Base):
    __tablename__ = "approved_safety_point_responses"

    id = Column(Integer, primary_key=True, index=True)
    approved_safety_point_id = Column(
        Integer,
        ForeignKey("approved_safety_points.id"),
        nullable=False,
        index=True,
    )
    question_key = Column(String(100), nullable=False)
    question_text = Column(Text, nullable=False)
    response_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    approved_safety_point = relationship(
        "ApprovedSafetyPoint",
        back_populates="responses",
    )