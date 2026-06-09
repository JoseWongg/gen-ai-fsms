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
from gen_ai_fsms.db.models.auth.user import User
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



def _build_user_display_name(user: User | None) -> str | None:
    if user is None:
        return None

    name_parts = [
        user.first_name,
        user.last_name,
    ]

    display_name = " ".join(
        part
        for part in name_parts
        if part
    ).strip()

    if display_name:
        return display_name

    return user.email


def _build_provenance_references_for_approved_safety_point(
    approved_safety_point: ApprovedSafetyPoint,
    content_safety_point: Dict[str, Any] | None,
) -> List[str]:
    provenance_references: List[str] = []

    if content_safety_point is not None:
        section_name = content_safety_point.get("section_name")
        safe_method_name = content_safety_point.get("safe_method_name")

        if section_name and safe_method_name:
            provenance_references.append(
                f"SFBB Pack > {section_name} > {safe_method_name}"
            )

        for reference in content_safety_point.get("source_references", []):
            if reference and reference not in provenance_references:
                provenance_references.append(reference)

    return provenance_references


def get_approved_methods_for_profile(
    db: Session,
    business_profile_id: int,
) -> Dict[str, Any]:
    approved_rows = (
        db.query(ApprovedSafetyPoint, User)
        .outerjoin(
            User,
            ApprovedSafetyPoint.approved_by_user_id == User.id,
        )
        .filter(ApprovedSafetyPoint.business_profile_id == business_profile_id)
        .order_by(
            ApprovedSafetyPoint.safe_method_name,
            ApprovedSafetyPoint.safety_point_id,
            ApprovedSafetyPoint.id,
        )
        .all()
    )

    content_service = ContentService()
    sections_by_id: Dict[str, Dict[str, Any]] = {}
    flat_approved_safety_points: List[Dict[str, Any]] = []

    for approved_safety_point, approving_user in approved_rows:
        content_safety_point = content_service.get_safety_point_by_id(
            approved_safety_point.safety_point_id
        ) or {}

        section_id = (
            content_safety_point.get("section_id")
            or "unknown_section"
        )
        section_name = (
            content_safety_point.get("section_name")
            or "Unknown section"
        )
        safe_method_id = (
            content_safety_point.get("safe_method_id")
            or approved_safety_point.safe_method_id
        )
        safe_method_name = (
            content_safety_point.get("safe_method_name")
            or approved_safety_point.safe_method_name
        )

        responses = [
            {
                "id": response.id,
                "question_key": response.question_key,
                "question_text": response.question_text,
                "response_text": response.response_text,
                "created_at": (
                    response.created_at.isoformat()
                    if response.created_at
                    else None
                ),
                "updated_at": (
                    response.updated_at.isoformat()
                    if response.updated_at
                    else None
                ),
            }
            for response in sorted(
                approved_safety_point.responses,
                key=lambda response: response.id,
            )
        ]

        approved_safety_point_view = {
            "approved_safety_point_id": approved_safety_point.id,
            "safety_point_id": approved_safety_point.safety_point_id,
            "safety_point_text": approved_safety_point.safety_point_text,
            "section_id": section_id,
            "section_name": section_name,
            "safe_method_id": safe_method_id,
            "safe_method_name": safe_method_name,
            "approved_at": (
                approved_safety_point.approved_at.isoformat()
                if approved_safety_point.approved_at
                else None
            ),
            "approved_by_user_id": approved_safety_point.approved_by_user_id,
            "approved_by_user": {
                "id": approving_user.id,
                "email": approving_user.email,
                "first_name": approving_user.first_name,
                "last_name": approving_user.last_name,
                "display_name": _build_user_display_name(approving_user),
            }
            if approving_user
            else None,
            "provenance_references": (
                _build_provenance_references_for_approved_safety_point(
                    approved_safety_point=approved_safety_point,
                    content_safety_point=content_safety_point,
                )
            ),
            "additional_responses": responses,
            "additional_response_count": len(responses),
        }

        flat_approved_safety_points.append(approved_safety_point_view)

        section_view = sections_by_id.setdefault(
            section_id,
            {
                "section_id": section_id,
                "section_name": section_name,
                "safe_methods": {},
            },
        )

        safe_method_view = section_view["safe_methods"].setdefault(
            safe_method_id,
            {
                "safe_method_id": safe_method_id,
                "safe_method_name": safe_method_name,
                "safety_points": [],
            },
        )

        safe_method_view["safety_points"].append(approved_safety_point_view)

    sections = []

    for section_view in sections_by_id.values():
        sections.append(
            {
                "section_id": section_view["section_id"],
                "section_name": section_view["section_name"],
                "safe_methods": list(section_view["safe_methods"].values()),
            }
        )

    return {
        "business_profile_id": business_profile_id,
        "approved_safety_point_count": len(flat_approved_safety_points),
        "sections": sections,
        "approved_safety_points": flat_approved_safety_points,
    }



def reset_approved_methods_for_profile(
    db: Session,
    business_profile_id: int,
) -> int:
    approved_safety_points = (
        db.query(ApprovedSafetyPoint)
        .filter(ApprovedSafetyPoint.business_profile_id == business_profile_id)
        .all()
    )

    deleted_count = len(approved_safety_points)

    for approved_safety_point in approved_safety_points:
        db.delete(approved_safety_point)

    return deleted_count


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