"""
Shared service functions for the safety point approval workflow.

This module centralises the business logic used to check whether the Food
Safety Profile screening is complete, load stored screening condition values,
and derive the relevant SFBB safety points for a business profile.

It is used by both the FastAPI approval routes and the LangGraph approval
workflow so that safety point retrieval rules remain consistent.
"""

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from gen_ai_fsms.db.models.approved_safety_point import ApprovedSafetyPoint
from gen_ai_fsms.db.models.approved_safety_point_response import (
    ApprovedSafetyPointResponse,
)
from gen_ai_fsms.db.models.condition import Condition
from gen_ai_fsms.db.models.condition_value import ConditionValue



from gen_ai_fsms.services.content_service import ContentService
from gen_ai_fsms.services.screening_questions import screening_questions


def get_screening_completion_status(
    db: Session,
    business_profile_id: int,
) -> Dict[str, Any]:
    rows = (
        db.query(ConditionValue, Condition)
        .join(Condition, ConditionValue.condition_id == Condition.condition_id)
        .filter(ConditionValue.business_profile_id == business_profile_id)
        .all()
    )

    values_by_condition_id = {
        condition.condition_id: condition_value.value
        for condition_value, condition in rows
    }

    active_condition_ids = {
        condition_id
        for question in screening_questions
        for condition_id in question.get("sets_conditions", [])
    }

    completed_active_conditions = {
        condition_id
        for condition_id in active_condition_ids
        if values_by_condition_id.get(condition_id) in ("true", "false")
    }

    is_complete = (
        len(active_condition_ids) > 0
        and completed_active_conditions == active_condition_ids
    )

    return {
        "is_complete": is_complete,
        "active_condition_count": len(active_condition_ids),
        "completed_active_condition_count": len(completed_active_conditions),
    }


def get_condition_values_for_profile(
    db: Session,
    business_profile_id: int,
) -> Dict[str, str]:
    rows = (
        db.query(ConditionValue)
        .filter(ConditionValue.business_profile_id == business_profile_id)
        .all()
    )

    return {
        row.condition_id: row.value
        for row in rows
    }


def get_relevant_safety_points_for_profile(
    db: Session,
    business_profile_id: int,
) -> List[Dict[str, Any]]:
    condition_values = get_condition_values_for_profile(db, business_profile_id)

    return ContentService().get_safety_points_by_conditions(condition_values)


def record_approved_safety_point(
    db: Session,
    business_profile_id: int,
    user_id: int,
    safety_point: Dict[str, Any],
    additional_answers: Dict[str, str],
) -> Dict[str, Any]:
    safety_point_text = (
        safety_point.get("text")
        or safety_point.get("safety_point_text")
        or ""
    )

    approved_safety_point = ApprovedSafetyPoint(
        business_profile_id=business_profile_id,
        safety_point_id=safety_point.get("safety_point_id"),
        safe_method_id=safety_point.get("safe_method_id"),
        safe_method_name=safety_point.get("safe_method_name"),
        safety_point_text=safety_point_text,
        approved_by_user_id=user_id,
    )

    db.add(approved_safety_point)
    db.flush()

    questions_by_key = {
        question.get("question_key"): question
        for question in safety_point.get("additional_questions", [])
        if question.get("question_key")
    }

    response_records = []

    for question_key, response_text in additional_answers.items():
        question = questions_by_key.get(question_key)

        if question is None:
            continue

        response_record = ApprovedSafetyPointResponse(
            approved_safety_point_id=approved_safety_point.id,
            question_key=question_key,
            question_text=question.get("question_text", ""),
            response_text=response_text,
        )

        db.add(response_record)
        response_records.append(response_record)

    db.flush()

    return {
        "approved_safety_point_id": approved_safety_point.id,
        "safety_point_id": approved_safety_point.safety_point_id,
        "additional_response_count": len(response_records),
    }