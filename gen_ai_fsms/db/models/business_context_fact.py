from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from gen_ai_fsms.db.base import Base


class BusinessContextFact(Base):
    __tablename__ = "business_context_facts"

    id = Column(Integer, primary_key=True, index=True)

    business_profile_id = Column(
        Integer,
        ForeignKey("business_profiles.id"),
        nullable=False,
        index=True,
    )

    workflow_session_id = Column(
        Integer,
        ForeignKey("onboarding_sessions.id"),
        nullable=True,
        index=True,
    )

    source_safety_point_id = Column(String(100), nullable=True, index=True)
    source_user_message = Column(Text, nullable=True)

    fact_type = Column(String(100), nullable=False, index=True)
    fact_text = Column(Text, nullable=False)
    normalised_fact = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)

    status = Column(
        String(50),
        nullable=False,
        default="unverified_user_statement",
        index=True,
    )

    usage_scope = Column(
        String(50),
        nullable=False,
        default="personalisation_only",
        index=True,
    )

    created_by_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
