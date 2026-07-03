import json
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from gen_ai_fsms.ai.adapter import get_llm_adapter
from gen_ai_fsms.db.models.chilling_temperature_corrective_action import (
    ChillingTemperatureCorrectiveAction,
)
from gen_ai_fsms.db.models.chilling_temperature_corrective_action_session import (
    ChillingTemperatureCorrectiveActionSession,
)
from gen_ai_fsms.db.models.chilling_temperature_incident import (
    ChillingTemperatureIncident,
)
from gen_ai_fsms.db.models.shift_diary_entry import ShiftDiaryEntry
from gen_ai_fsms.services.chilling_temperature_incident_service import (
    get_open_fridge_temperature_incident_for_corrective_action,
)
from gen_ai_fsms.services.fridge_corrective_action_validation_service import (
    FridgeCorrectiveActionState,
    validate_fridge_corrective_action_state,
)


WORKFLOW_TIMEZONE = ZoneInfo("Europe/London")

SESSION_STATUS_IN_PROGRESS = "in_progress"
SESSION_STATUS_AWAITING_APPROVAL = "awaiting_approval"
SESSION_STATUS_COMPLETED = "completed"
SESSION_STATUS_CANCELLED = "cancelled"

STAGE_GATHERING = "gathering"
STAGE_AWAITING_APPROVAL = "awaiting_approval"
STAGE_COMPLETED = "completed"

INCIDENT_STATUS_RESOLVED = "resolved"

RELATED_ENTITY_TYPE_CHILLING_TEMPERATURE_INCIDENT = "chilling_temperature_incident"


CORRECTIVE_ACTION_STATE_FIELDS = {
    "food_probed",
    "food_type",
    "food_temperature_c",
    "out_of_range_duration",
    "food_decision",
    "destination_fridge_temperature_c",
    "fridge_issue_type",
    "transient_issue_description",
    "corrective_action_taken",
    "follow_up_temperature_c",
    "food_returned_to_fridge",
    "maintenance_logged",
    "maintenance_reference",
}


def _now() -> datetime:
    return datetime.now(WORKFLOW_TIMEZONE)


def _read_json_object(value: str | None) -> dict[str, Any]:
    if not value:
        return {}

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}

    if isinstance(parsed, dict):
        return parsed

    return {}


def _read_json_list(value: str | None) -> list[dict[str, Any]]:
    if not value:
        return []

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []

    if isinstance(parsed, list):
        return [
            item
            for item in parsed
            if isinstance(item, dict)
        ]

    return []


def _write_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _model_to_dict(model) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()

    return model.dict()


def _merge_extracted_facts(
    current_state: dict[str, Any],
    extracted_facts: dict[str, Any],
) -> dict[str, Any]:
    merged_state = dict(current_state)

    for field in CORRECTIVE_ACTION_STATE_FIELDS:
        value = extracted_facts.get(field)

        if value is not None:
            merged_state[field] = value

    return merged_state


def _append_conversation_message(
    conversation_history: list[dict[str, Any]],
    role: str,
    content: str,
) -> list[dict[str, Any]]:
    updated_history = list(conversation_history)
    updated_history.append(
        {
            "role": role,
            "content": content,
            "created_at": _now().isoformat(),
        }
    )
    return updated_history


def _get_existing_session(
    db: Session,
    business_profile_id: int,
    incident_id: int,
) -> ChillingTemperatureCorrectiveActionSession | None:
    return (
        db.query(ChillingTemperatureCorrectiveActionSession)
        .filter(
            ChillingTemperatureCorrectiveActionSession.business_profile_id
            == business_profile_id,
            ChillingTemperatureCorrectiveActionSession.incident_id
            == incident_id,
        )
        .first()
    )


def _get_open_incident_or_raise(
    db: Session,
    business_profile_id: int,
    incident_id: int,
) -> ChillingTemperatureIncident:
    incident = get_open_fridge_temperature_incident_for_corrective_action(
        db=db,
        business_profile_id=business_profile_id,
        incident_id=incident_id,
    )

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Open fridge temperature incident was not found for this "
                "business profile."
            ),
        )

    return incident


def _build_workflow_response(
    session: ChillingTemperatureCorrectiveActionSession,
    message: str | None,
) -> dict[str, Any]:
    return {
        "session_id": session.id,
        "incident_id": session.incident_id,
        "stage": session.current_stage,
        "status": session.status,
        "message": message,
        "issues": _read_json_list(session.issues_json),
        "final_summary": session.final_summary,
        "is_completed": session.status == SESSION_STATUS_COMPLETED,
    }


def _build_completed_incident_response(
    session: ChillingTemperatureCorrectiveActionSession,
) -> dict[str, Any]:
    return _build_workflow_response(
        session=session,
        message="This incident has already been resolved.",
    )


def _validate_state_and_update_session(
    session: ChillingTemperatureCorrectiveActionSession,
) -> dict[str, Any]:
    adapter = get_llm_adapter()

    state_data = _read_json_object(session.state_json)
    state = FridgeCorrectiveActionState(**state_data)

    validation_result = validate_fridge_corrective_action_state(state)
    issue_data = [
        _model_to_dict(issue)
        for issue in validation_result.issues
    ]

    session.issues_json = _write_json(issue_data)

    if issue_data:
        session.status = SESSION_STATUS_IN_PROGRESS
        session.current_stage = STAGE_GATHERING
        session.final_summary = None

        first_issue = issue_data[0]
        question = adapter.generate_fridge_corrective_action_question(
            issue=first_issue,
            current_state=state_data,
        )

        conversation_history = _read_json_list(
            session.conversation_history_json
        )
        conversation_history = _append_conversation_message(
            conversation_history=conversation_history,
            role="assistant",
            content=question,
        )
        session.conversation_history_json = _write_json(conversation_history)

        return _build_workflow_response(
            session=session,
            message=question,
        )

    summary = adapter.generate_fridge_corrective_action_summary(state_data)

    session.status = SESSION_STATUS_AWAITING_APPROVAL
    session.current_stage = STAGE_AWAITING_APPROVAL
    session.final_summary = summary
    session.issues_json = _write_json([])

    conversation_history = _read_json_list(session.conversation_history_json)
    conversation_history = _append_conversation_message(
        conversation_history=conversation_history,
        role="assistant",
        content=summary,
    )
    session.conversation_history_json = _write_json(conversation_history)

    return _build_workflow_response(
        session=session,
        message="Please review and approve the corrective-action summary.",
    )



def start_or_resume_session(
    db: Session,
    business_profile_id: int,
    user_id: int,
    incident_id: int,
) -> dict[str, Any]:
    session = _get_existing_session(
        db=db,
        business_profile_id=business_profile_id,
        incident_id=incident_id,
    )

    if session is not None:
        db.refresh(session)

        if session.status == SESSION_STATUS_COMPLETED:
            return _build_completed_incident_response(session)

        if session.status == SESSION_STATUS_AWAITING_APPROVAL:
            return _build_workflow_response(
                session=session,
                message="Please review and approve the corrective-action summary.",
            )

        issues = _read_json_list(session.issues_json)
        if issues:
            adapter = get_llm_adapter()
            question = adapter.generate_fridge_corrective_action_question(
                issue=issues[0],
                current_state=_read_json_object(session.state_json),
            )
            return _build_workflow_response(
                session=session,
                message=question,
            )

        return _build_workflow_response(
            session=session,
            message="Describe the corrective action taken for this fridge temperature incident.",
        )

    incident = _get_open_incident_or_raise(
        db=db,
        business_profile_id=business_profile_id,
        incident_id=incident_id,
    )

    session = ChillingTemperatureCorrectiveActionSession(
        incident_id=incident.id,
        business_profile_id=incident.business_profile_id,
        daily_shift_id=incident.daily_shift_id,
        started_by_user_id=user_id,
        status=SESSION_STATUS_IN_PROGRESS,
        current_stage=STAGE_GATHERING,
        state_json=_write_json({}),
        issues_json=_write_json([]),
        conversation_history_json=_write_json([]),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return _build_workflow_response(
        session=session,
        message="Describe the corrective action taken for this fridge temperature incident.",
    )


def get_existing_session_status(
    db: Session,
    business_profile_id: int,
    incident_id: int,
) -> dict[str, Any]:
    session = _get_existing_session(
        db=db,
        business_profile_id=business_profile_id,
        incident_id=incident_id,
    )

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Corrective-action session not found.",
        )

    return _build_workflow_response(
        session=session,
        message=None,
    )



def process_user_message(
    db: Session,
    business_profile_id: int,
    user_id: int,
    incident_id: int,
    user_message: str,
) -> dict[str, Any]:
    if not user_message or not user_message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User message cannot be empty.",
        )

    existing_session = _get_existing_session(
        db=db,
        business_profile_id=business_profile_id,
        incident_id=incident_id,
    )

    if (
        existing_session is not None
        and existing_session.status == SESSION_STATUS_COMPLETED
    ):
        return _build_completed_incident_response(existing_session)

    incident = _get_open_incident_or_raise(
        db=db,
        business_profile_id=business_profile_id,
        incident_id=incident_id,
    )

    session = _get_existing_session(
        db=db,
        business_profile_id=business_profile_id,
        incident_id=incident.id,
    )

    if session is None:
        start_or_resume_session(
            db=db,
            business_profile_id=business_profile_id,
            user_id=user_id,
            incident_id=incident.id,
        )
        session = _get_existing_session(
            db=db,
            business_profile_id=business_profile_id,
            incident_id=incident.id,
        )

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create corrective-action session.",
        )

    if session.status == SESSION_STATUS_COMPLETED:
        return _build_completed_incident_response(session)

    adapter = get_llm_adapter()

    current_state = _read_json_object(session.state_json)
    conversation_history = _read_json_list(
        session.conversation_history_json
    )
    conversation_history = _append_conversation_message(
        conversation_history=conversation_history,
        role="user",
        content=user_message.strip(),
    )

    if session.status == SESSION_STATUS_AWAITING_APPROVAL:
        approval_result = adapter.classify_fridge_corrective_action_approval(
            user_message=user_message.strip(),
        )

        if approval_result.get("action") == "approve":
            session.conversation_history_json = _write_json(
                conversation_history
            )
            db.commit()
            db.refresh(session)

            return approve_final_summary(
                db=db,
                business_profile_id=business_profile_id,
                user_id=user_id,
                incident_id=incident.id,
            )

        if approval_result.get("action") == "unclear":
            assistant_message = approval_result.get("assistant_message") or (
                "Please confirm whether you approve the corrective-action "
                "summary, or provide the correction needed."
            )
            conversation_history = _append_conversation_message(
                conversation_history=conversation_history,
                role="assistant",
                content=assistant_message,
            )
            session.conversation_history_json = _write_json(
                conversation_history
            )
            db.commit()
            db.refresh(session)

            return _build_workflow_response(
                session=session,
                message=assistant_message,
            )

        session.status = SESSION_STATUS_IN_PROGRESS
        session.current_stage = STAGE_GATHERING
        session.final_summary = None

    extracted_facts = adapter.extract_fridge_corrective_action_facts(
        user_message=user_message.strip(),
        existing_state=current_state,
    )

    merged_state = _merge_extracted_facts(
        current_state=current_state,
        extracted_facts=extracted_facts,
    )

    session.state_json = _write_json(merged_state)
    session.conversation_history_json = _write_json(conversation_history)

    response = _validate_state_and_update_session(session)

    db.commit()
    db.refresh(session)

    return {
        **response,
        "session_id": session.id,
        "stage": session.current_stage,
        "status": session.status,
        "issues": _read_json_list(session.issues_json),
        "final_summary": session.final_summary,
        "is_completed": session.status == SESSION_STATUS_COMPLETED,
    }



def approve_final_summary(
    db: Session,
    business_profile_id: int,
    user_id: int,
    incident_id: int,
) -> dict[str, Any]:
    existing_session = _get_existing_session(
        db=db,
        business_profile_id=business_profile_id,
        incident_id=incident_id,
    )

    if (
        existing_session is not None
        and existing_session.status == SESSION_STATUS_COMPLETED
    ):
        return _build_completed_incident_response(existing_session)

    incident = _get_open_incident_or_raise(
        db=db,
        business_profile_id=business_profile_id,
        incident_id=incident_id,
    )

    session = _get_existing_session(
        db=db,
        business_profile_id=business_profile_id,
        incident_id=incident.id,
    )

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Corrective-action session not found.",
        )

    if session.status != SESSION_STATUS_AWAITING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Corrective-action session is not awaiting approval.",
        )

    if not session.final_summary:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Corrective-action summary is missing.",
        )

    return record_corrective_action(
        db=db,
        incident=incident,
        session=session,
        recorded_by_user_id=user_id,
    )


def record_corrective_action(
    db: Session,
    incident: ChillingTemperatureIncident,
    session: ChillingTemperatureCorrectiveActionSession,
    recorded_by_user_id: int,
) -> dict[str, Any]:
    existing_corrective_action = (
        db.query(ChillingTemperatureCorrectiveAction)
        .filter(
            ChillingTemperatureCorrectiveAction.incident_id == incident.id,
            ChillingTemperatureCorrectiveAction.business_profile_id
            == incident.business_profile_id,
        )
        .first()
    )

    if existing_corrective_action is not None:
        session.status = SESSION_STATUS_COMPLETED
        session.current_stage = STAGE_COMPLETED
        if session.completed_at is None:
            session.completed_at = _now()

        db.commit()
        db.refresh(session)

        return _build_workflow_response(
            session=session,
            message="Corrective action has already been recorded.",
        )

    final_summary = session.final_summary
    if not final_summary:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Corrective-action summary is missing.",
        )

    corrective_action = ChillingTemperatureCorrectiveAction(
        incident_id=incident.id,
        business_profile_id=incident.business_profile_id,
        daily_shift_id=incident.daily_shift_id,
        recorded_by_user_id=recorded_by_user_id,
        final_narrative=final_summary,
        structured_facts_json=session.state_json,
        validation_status="approved",
    )
    db.add(corrective_action)

    incident.status = INCIDENT_STATUS_RESOLVED
    incident.resolved_at = _now()

    diary_entry = (
        db.query(ShiftDiaryEntry)
        .filter(
            ShiftDiaryEntry.business_profile_id == incident.business_profile_id,
            ShiftDiaryEntry.daily_shift_id == incident.daily_shift_id,
            ShiftDiaryEntry.related_entity_type
            == RELATED_ENTITY_TYPE_CHILLING_TEMPERATURE_INCIDENT,
            ShiftDiaryEntry.related_entity_id == incident.id,
        )
        .order_by(
            ShiftDiaryEntry.created_at.asc(),
            ShiftDiaryEntry.id.asc(),
        )
        .first()
    )

    corrective_action_text = (
        "Corrective action recorded:\n"
        f"{final_summary}"
    )

    if diary_entry is not None:
        diary_entry.entry_text = (
            f"{diary_entry.entry_text}\n\n{corrective_action_text}"
        )
        diary_entry.updated_at = _now()
    else:
        diary_entry = ShiftDiaryEntry(
            business_profile_id=incident.business_profile_id,
            daily_shift_id=incident.daily_shift_id,
            created_by_user_id=recorded_by_user_id,
            entry_type=RELATED_ENTITY_TYPE_CHILLING_TEMPERATURE_INCIDENT,
            title=(
                f"{incident.check_period.upper()} non-compliant fridge "
                "temperature corrective action recorded"
            ),
            entry_text=corrective_action_text,
            related_entity_type=RELATED_ENTITY_TYPE_CHILLING_TEMPERATURE_INCIDENT,
            related_entity_id=incident.id,
        )
        db.add(diary_entry)

    conversation_history = _read_json_list(session.conversation_history_json)
    conversation_history = _append_conversation_message(
        conversation_history=conversation_history,
        role="assistant",
        content="Corrective action recorded and incident resolved.",
    )

    session.status = SESSION_STATUS_COMPLETED
    session.current_stage = STAGE_COMPLETED
    session.completed_at = _now()
    session.conversation_history_json = _write_json(conversation_history)

    db.commit()
    db.refresh(session)

    return _build_workflow_response(
        session=session,
        message="Corrective action recorded and incident resolved.",
    )
