"""
Shared service functions for the safety point approval workflow.

This module centralises the business logic used to check whether the Food
Safety Profile screening is complete, load stored screening condition values,
and derive the relevant SFBB safety points for a business profile.

It is used by both the FastAPI approval routes and the LangGraph approval
workflow so that safety point retrieval rules remain consistent.
"""

from typing import Any, Dict, List
from uuid import uuid4

from sqlalchemy.orm import Session

from gen_ai_fsms.db.models.approved_safety_point import ApprovedSafetyPoint
from gen_ai_fsms.db.models.business_context_fact import BusinessContextFact
from gen_ai_fsms.db.models.approved_safety_point_response import (
    ApprovedSafetyPointResponse,
)
from gen_ai_fsms.db.models.auth.user import User
from gen_ai_fsms.db.models.condition import Condition
from gen_ai_fsms.db.models.condition_value import ConditionValue
from gen_ai_fsms.db.models.daily_shift import DailyShift
from gen_ai_fsms.db.models.daily_shift_chilling_temperature_check import (
    DailyShiftChillingTemperatureCheck,
)
from gen_ai_fsms.db.models.chilling_temperature_corrective_action import (
    ChillingTemperatureCorrectiveAction,
)
from gen_ai_fsms.db.models.chilling_temperature_corrective_action_session import (
    ChillingTemperatureCorrectiveActionSession,
)
from gen_ai_fsms.db.models.chilling_temperature_incident import (
    ChillingTemperatureIncident,
)
from gen_ai_fsms.db.models.notification import Notification
from gen_ai_fsms.db.models.shift_diary_entry import ShiftDiaryEntry
from gen_ai_fsms.db.models.business_chilling_equipment import BusinessChillingEquipment
from gen_ai_fsms.services.chilling_equipment_service import (
    TRACKED_EQUIPMENT_FIELDS,
    build_chilling_equipment_state_summary,
    generate_chilling_equipment_asset_code,
    record_chilling_equipment_change,
    record_chilling_equipment_field_changes,
)



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

        current_chilling_equipment = []

        if approved_safety_point.safety_point_id == "4.1.1.3":
            current_chilling_equipment = [
                {
                    "id": equipment.id,
                    "equipment_asset_code": equipment.equipment_asset_code,
                    "equipment_name": equipment.equipment_name,
                    "equipment_type": equipment.equipment_type,
                    "equipment_use": equipment.equipment_use,
                    "temperature_check_method": equipment.temperature_check_method,
                }
                for equipment in (
                    db.query(BusinessChillingEquipment)
                    .filter(
                        BusinessChillingEquipment.business_profile_id
                        == business_profile_id,
                        BusinessChillingEquipment.is_active.is_(True),
                    )
                    .order_by(
                        BusinessChillingEquipment.equipment_name,
                        BusinessChillingEquipment.id,
                    )
                    .all()
                )
            ]

        responses = []

        for response in sorted(
            approved_safety_point.responses,
            key=lambda response: response.id,
        ):
            response_view = {
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

            if (
                approved_safety_point.safety_point_id == "4.1.1.3"
                and response.question_key == "chilling_equipment_temperature_checks"
            ):
                response_view["response_text"] = None
                response_view["current_chilling_equipment"] = current_chilling_equipment

            responses.append(response_view)

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




def reset_business_context_facts_for_profile(
    db: Session,
    business_profile_id: int,
    workflow_session_ids: list[int] | None = None,
) -> int:
    """Delete parked personalisation facts before workflow/session reset.

    When workflow_session_ids is provided, only facts linked to those workflow
    sessions are deleted. When omitted, all parked facts for the business
    profile are deleted.
    """
    query = db.query(BusinessContextFact).filter(
        BusinessContextFact.business_profile_id == business_profile_id
    )

    if workflow_session_ids is not None:
        if not workflow_session_ids:
            return 0

        query = query.filter(
            BusinessContextFact.workflow_session_id.in_(workflow_session_ids)
        )

    return query.delete(synchronize_session=False)


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

    active_shift_ids = [
        shift.id
        for shift in (
            db.query(DailyShift)
            .filter(
                DailyShift.business_profile_id == business_profile_id,
                DailyShift.status == "active",
            )
            .all()
        )
    ]

    if active_shift_ids:
        active_temperature_check_ids = [
            check.id
            for check in (
                db.query(DailyShiftChillingTemperatureCheck)
                .filter(
                    DailyShiftChillingTemperatureCheck.daily_shift_id.in_(
                        active_shift_ids
                    )
                )
                .all()
            )
        ]

        if active_temperature_check_ids:
            active_incident_ids = [
                incident.id
                for incident in (
                    db.query(ChillingTemperatureIncident)
                    .filter(
                        ChillingTemperatureIncident.chilling_temperature_check_id.in_(
                            active_temperature_check_ids
                        )
                    )
                    .all()
                )
            ]

            if active_incident_ids:
                (
                    db.query(ChillingTemperatureCorrectiveActionSession)
                    .filter(
                        ChillingTemperatureCorrectiveActionSession.incident_id.in_(
                            active_incident_ids
                        )
                    )
                    .delete(synchronize_session=False)
                )

                (
                    db.query(ChillingTemperatureCorrectiveAction)
                    .filter(
                        ChillingTemperatureCorrectiveAction.incident_id.in_(
                            active_incident_ids
                        )
                    )
                    .delete(synchronize_session=False)
                )

                (
                    db.query(Notification)
                    .filter(
                        Notification.business_profile_id == business_profile_id,
                        Notification.related_entity_type
                        == "chilling_temperature_incident",
                        Notification.related_entity_id.in_(active_incident_ids),
                    )
                    .delete(synchronize_session=False)
                )

                (
                    db.query(ShiftDiaryEntry)
                    .filter(
                        ShiftDiaryEntry.business_profile_id == business_profile_id,
                        ShiftDiaryEntry.related_entity_type
                        == "chilling_temperature_incident",
                        ShiftDiaryEntry.related_entity_id.in_(active_incident_ids),
                    )
                    .delete(synchronize_session=False)
                )

                (
                    db.query(ChillingTemperatureIncident)
                    .filter(ChillingTemperatureIncident.id.in_(active_incident_ids))
                    .delete(synchronize_session=False)
                )

            (
                db.query(DailyShiftChillingTemperatureCheck)
                .filter(
                    DailyShiftChillingTemperatureCheck.id.in_(
                        active_temperature_check_ids
                    )
                )
                .delete(synchronize_session=False)
            )

    active_chilling_equipment = (
        db.query(BusinessChillingEquipment)
        .filter(
            BusinessChillingEquipment.business_profile_id == business_profile_id,
            BusinessChillingEquipment.is_active.is_(True),
        )
        .all()
    )

    for equipment in active_chilling_equipment:
        equipment.is_active = False

    return deleted_count


def save_chilling_equipment_items_for_profile(
    db: Session,
    business_profile_id: int,
    equipment_items: List[Dict[str, Any]],
    source_safety_point_id: str = "4.1.1.3",
    changed_by_user_id: int | None = None,
) -> Dict[str, Any]:
    """
    Save complete chilling equipment items for a business profile.

    The workflow should call this only for equipment items that already have all
    required details. Items with missing details are skipped by the workflow and
    should not be passed here.
    """
    valid_equipment_uses = {"storage", "display"}
    valid_equipment_types = {"fridge", "freezer"}
    valid_temperature_methods = {
        "digital_or_dial_display",
        "probe_between_packs",
    }

    existing_records = (
        db.query(BusinessChillingEquipment)
        .filter(
            BusinessChillingEquipment.business_profile_id == business_profile_id,
            BusinessChillingEquipment.source_safety_point_id == source_safety_point_id,
        )
        .all()
    )

    existing_by_name = {
        record.equipment_name.strip().lower(): record
        for record in existing_records
    }

    saved_items = []
    skipped_items = []

    for item in equipment_items:
        equipment_name = str(item.get("equipment_name") or "").strip()
        equipment_use = item.get("equipment_use")
        equipment_type = item.get("equipment_type")
        temperature_check_method = item.get("temperature_check_method")

        if (
            not equipment_name
            or equipment_use not in valid_equipment_uses
            or equipment_type not in valid_equipment_types
            or temperature_check_method not in valid_temperature_methods
        ):
            skipped_items.append(
                {
                    "equipment_name": equipment_name,
                    "reason": "Missing or invalid required equipment details.",
                }
            )
            continue

        lookup_key = equipment_name.lower()
        existing_record = existing_by_name.get(lookup_key)

        if existing_record is None:
            record = BusinessChillingEquipment(
                business_profile_id=business_profile_id,
                source_safety_point_id=source_safety_point_id,
                equipment_name=equipment_name,
                equipment_use=equipment_use,
                equipment_type=equipment_type,
                temperature_check_method=temperature_check_method,
                is_active=True,
                equipment_asset_code=f"PENDING-{uuid4().hex}",
            )
            db.add(record)
            db.flush()
            record.equipment_asset_code = generate_chilling_equipment_asset_code(record)

            record_chilling_equipment_change(
                db=db,
                business_profile_id=business_profile_id,
                chilling_equipment_id=record.id,
                change_type="created",
                field_name="current_state",
                old_value=None,
                new_value=build_chilling_equipment_state_summary(record),
                changed_by_user_id=changed_by_user_id,
            )

            existing_by_name[lookup_key] = record
        else:
            record = existing_record
            old_values = {
                field_name: getattr(record, field_name)
                for field_name in TRACKED_EQUIPMENT_FIELDS
            }
            was_active = bool(record.is_active)

            record.equipment_name = equipment_name
            record.equipment_use = equipment_use
            record.equipment_type = equipment_type
            record.temperature_check_method = temperature_check_method
            record.is_active = True
            db.flush()

            record_chilling_equipment_field_changes(
                db=db,
                business_profile_id=business_profile_id,
                equipment=record,
                old_values=old_values,
                changed_by_user_id=changed_by_user_id,
            )

            if not was_active:
                record_chilling_equipment_change(
                    db=db,
                    business_profile_id=business_profile_id,
                    chilling_equipment_id=record.id,
                    change_type="activated",
                    field_name="is_active",
                    old_value=False,
                    new_value=True,
                    changed_by_user_id=changed_by_user_id,
                )

        saved_items.append(
            {
                "id": record.id,
                "equipment_asset_code": record.equipment_asset_code,
                "equipment_name": record.equipment_name,
                "equipment_use": record.equipment_use,
                "equipment_type": record.equipment_type,
                "temperature_check_method": record.temperature_check_method,
            }
        )

    return {
        "saved_count": len(saved_items),
        "skipped_count": len(skipped_items),
        "saved_items": saved_items,
        "skipped_items": skipped_items,
    }


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
