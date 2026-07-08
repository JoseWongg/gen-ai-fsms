from typing import Optional

from sqlalchemy.orm import Session

from gen_ai_fsms.db.models.business_context_fact import BusinessContextFact


BUSINESS_CONTEXT_FACT_STATUS = "unverified_user_statement"
BUSINESS_CONTEXT_FACT_USAGE_SCOPE = "personalisation_only"

ALLOWED_BUSINESS_CONTEXT_FACT_TYPES = {
    "business_activity",
    "food_type_or_ingredient",
    "equipment_used",
    "temperature_control_practice",
    "storage_practice",
    "cleaning_practice",
    "cooking_or_reheating_practice",
    "supplier_or_delivery_practice",
    "monitoring_or_recording_practice",
    "staff_training_practice",
    "other_business_operation",
}


def create_business_context_fact(
    db: Session,
    business_profile_id: int,
    fact_type: str,
    fact_text: str,
    workflow_session_id: Optional[int] = None,
    source_safety_point_id: Optional[str] = None,
    source_user_message: Optional[str] = None,
    normalised_fact: Optional[str] = None,
    confidence: Optional[float] = None,
    created_by_user_id: Optional[int] = None,
    commit: bool = True,
    refresh: bool = True,
) -> BusinessContextFact:
    clean_fact_type = (fact_type or "").strip()
    clean_fact_text = " ".join((fact_text or "").split())

    if clean_fact_type not in ALLOWED_BUSINESS_CONTEXT_FACT_TYPES:
        raise ValueError(f"Unsupported business context fact_type: {fact_type}")

    if not clean_fact_text:
        raise ValueError("Business context fact_text cannot be empty.")

    fact = BusinessContextFact(
        business_profile_id=business_profile_id,
        workflow_session_id=workflow_session_id,
        source_safety_point_id=source_safety_point_id,
        source_user_message=source_user_message,
        fact_type=clean_fact_type,
        fact_text=clean_fact_text,
        normalised_fact=normalised_fact,
        confidence=confidence,
        status=BUSINESS_CONTEXT_FACT_STATUS,
        usage_scope=BUSINESS_CONTEXT_FACT_USAGE_SCOPE,
        created_by_user_id=created_by_user_id,
    )

    db.add(fact)

    if commit:
        db.commit()

        if refresh:
            db.refresh(fact)
    else:
        db.flush()

        if refresh:
            db.refresh(fact)

    return fact


def list_business_context_facts_for_profile(
    db: Session,
    business_profile_id: int,
    fact_types: Optional[set[str]] = None,
    limit: int = 20,
) -> list[BusinessContextFact]:
    query = db.query(BusinessContextFact).filter(
        BusinessContextFact.business_profile_id == business_profile_id,
        BusinessContextFact.status == BUSINESS_CONTEXT_FACT_STATUS,
        BusinessContextFact.usage_scope == BUSINESS_CONTEXT_FACT_USAGE_SCOPE,
    )

    if fact_types:
        allowed_requested_types = (
            set(fact_types) & ALLOWED_BUSINESS_CONTEXT_FACT_TYPES
        )
        if not allowed_requested_types:
            return []

        query = query.filter(
            BusinessContextFact.fact_type.in_(allowed_requested_types)
        )

    return (
        query
        .order_by(
            BusinessContextFact.created_at.desc(),
            BusinessContextFact.id.desc(),
        )
        .limit(limit)
        .all()
    )
