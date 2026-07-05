import json
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from gen_ai_fsms.ai.adapter import get_llm_adapter
from gen_ai_fsms.db.models.auth.user import User
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
    get_open_freezer_temperature_incident_for_corrective_action,
)
from gen_ai_fsms.services.freezer_corrective_action_validation_service import (
    FreezerCorrectiveActionState,
    validate_freezer_corrective_action_state,
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
    "food_checked_for_thawing_signs",
    "thawing_signs_present",
    "food_decision",
    "destination_freezer_temperature_c",
    "freezer_issue_type",
    "transient_issue_description",
    "corrective_action_taken",
    "follow_up_temperature_c",
    "food_returned_to_freezer",
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


def _get_user_display_name(db: Session, user_id: int) -> str | None:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        return None

    first_name = getattr(user, "first_name", None)
    if isinstance(first_name, str) and first_name.strip():
        return first_name.strip()

    return None


def _build_initial_message(user_display_name: str | None) -> str:
    if user_display_name:
        return (
            f"Hello {user_display_name}. Please describe the corrective "
            "action taken for this freezer temperature incident."
        )

    return "Describe the corrective action taken for this freezer temperature incident."


def _has_extracted_corrective_action_facts(
    extracted_facts: Any,
    current_state: dict[str, Any],
) -> bool:
    if isinstance(extracted_facts, dict):
        data = extracted_facts
    else:
        data = _model_to_dict(extracted_facts)

    for field in CORRECTIVE_ACTION_STATE_FIELDS:
        extracted_value = data.get(field)

        if extracted_value is None:
            continue

        if current_state.get(field) == extracted_value:
            continue

        return True

    return False


def _build_initial_repeat_message() -> str:
    return "Please describe the corrective action taken for this freezer temperature incident."


UNUSABLE_ANSWER_PREFIXES = (
    "I could not understand that. ",
    "I still could not understand that. ",
    "I still do not have enough information from that answer. ",
    "I still cannot identify the corrective-action details from that response. ",
)


def _strip_unusable_answer_prefix(message: str) -> str:
    for prefix in UNUSABLE_ANSWER_PREFIXES:
        if message.startswith(prefix):
            return message[len(prefix):].strip()

    return message.strip()


def _is_unusable_answer_message(message: str) -> bool:
    return any(
        message.startswith(prefix)
        for prefix in UNUSABLE_ANSWER_PREFIXES
    )


def _count_recent_unusable_answer_repeats(
    conversation_history: list[dict[str, Any]],
    base_question: str,
) -> int:
    repeat_count = 0

    for message in reversed(conversation_history):
        if message.get("role") != "assistant":
            continue

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            continue

        if not _is_unusable_answer_message(content):
            break

        if _strip_unusable_answer_prefix(content) != base_question:
            break

        repeat_count += 1

    return repeat_count


def _build_unusable_answer_message(
    previous_assistant_message: str,
    conversation_history: list[dict[str, Any]],
) -> str:
    base_question = _strip_unusable_answer_prefix(previous_assistant_message)
    repeat_count = _count_recent_unusable_answer_repeats(
        conversation_history=conversation_history,
        base_question=base_question,
    )

    prefix_index = min(repeat_count, len(UNUSABLE_ANSWER_PREFIXES) - 1)
    return f"{UNUSABLE_ANSWER_PREFIXES[prefix_index]}{base_question}"


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



def _get_last_assistant_message(
    conversation_history: list[dict[str, Any]],
) -> str | None:
    for message in reversed(conversation_history):
        if message.get("role") == "assistant":
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()

    return None


def _get_last_user_message(
    conversation_history: list[dict[str, Any]],
) -> str | None:
    for message in reversed(conversation_history):
        if message.get("role") == "user":
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()

    return None


def _get_recent_conversation_history(
    conversation_history: list[dict[str, Any]],
    max_messages: int = 6,
) -> list[dict[str, Any]]:
    return [
        {
            key: value
            for key, value in message.items()
            if key != "metadata"
        }
        for message in conversation_history[-max_messages:]
    ]

def _get_issue_retry_context(
    conversation_history: list[dict[str, Any]],
    current_issue: dict[str, Any],
) -> dict[str, Any]:
    current_kind = current_issue.get("kind")
    current_field = current_issue.get("field")

    for message in reversed(conversation_history):
        if message.get("role") != "assistant":
            continue

        metadata = message.get("metadata")
        if not isinstance(metadata, dict):
            continue

        previous_kind = metadata.get("issue_kind")
        previous_field = metadata.get("issue_field")
        previous_retry_count = metadata.get("retry_count", 0)

        same_issue = (
            previous_kind == current_kind
            and previous_field == current_field
        )

        if not same_issue:
            return {
                "is_retry": False,
                "retry_count": 0,
            }

        if not isinstance(previous_retry_count, int):
            previous_retry_count = 0

        return {
            "is_retry": True,
            "retry_count": previous_retry_count + 1,
        }

    return {
        "is_retry": False,
        "retry_count": 0,
    }


def _build_issue_message_metadata(
    issue: dict[str, Any],
    retry_context: dict[str, Any],
) -> dict[str, Any]:
    return {
        "issue_kind": issue.get("kind"),
        "issue_field": issue.get("field"),
        "retry_count": retry_context["retry_count"],
    }


def _get_stored_issue_retry_context(
    conversation_history: list[dict[str, Any]],
    current_issue: dict[str, Any],
) -> dict[str, Any]:
    current_kind = current_issue.get("kind")
    current_field = current_issue.get("field")

    for message in reversed(conversation_history):
        if message.get("role") != "assistant":
            continue

        metadata = message.get("metadata")
        if not isinstance(metadata, dict):
            continue

        same_issue = (
            metadata.get("issue_kind") == current_kind
            and metadata.get("issue_field") == current_field
        )

        if not same_issue:
            return {
                "is_retry": False,
                "retry_count": 0,
            }

        retry_count = metadata.get("retry_count", 0)
        if not isinstance(retry_count, int):
            retry_count = 0

        return {
            "is_retry": retry_count > 0,
            "retry_count": retry_count,
        }

    return {
        "is_retry": False,
        "retry_count": 0,
    }


def _append_conversation_message(
    conversation_history: list[dict[str, Any]],
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    updated_history = list(conversation_history)
    message = {
        "role": role,
        "content": content,
        "created_at": _now().isoformat(),
    }
    if metadata:
        message["metadata"] = metadata

    updated_history.append(message)
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
    incident = get_open_freezer_temperature_incident_for_corrective_action(
        db=db,
        business_profile_id=business_profile_id,
        incident_id=incident_id,
    )

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Open freezer temperature incident was not found for this "
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
        "equipment_type": "freezer",
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



def _build_validator_issue_message(issue: dict[str, Any]) -> str | None:
    if issue.get("kind") != "contradiction":
        return None

    issue_message = issue.get("message") or (
        "That answer does not match the freezer safety rules."
    )

    guidance_by_field = {
        "food_checked_for_thawing_signs": (
            "Please confirm whether the frozen food has now been checked for "
            "signs of thawing. If it was already checked, correct the earlier "
            "answer."
        ),
        "food_decision": (
            "Based on the information given, the food cannot be kept. Please "
            "confirm whether it has now been discarded, or correct the earlier "
            "information if it did not actually show signs of thawing."
        ),
        "destination_freezer_temperature_c": (
            "Food can only be moved to compliant freezer equipment. Please "
            "correct the food decision or the destination freezer temperature."
        ),
        "freezer_issue_type": (
            "Please confirm whether the freezer has now been logged for "
            "maintenance or repair. If the freezer was actually back within the "
            "safe range, correct the follow-up temperature."
        ),
    }

    correction_guidance = guidance_by_field.get(
        issue.get("field"),
        (
            "Please correct the earlier information or describe the updated "
            "corrective action taken."
        ),
    )

    return (
        "There is a problem with that answer.\n\n"
        f"{issue_message}\n\n"
        f"{correction_guidance}"
    )

def _validate_state_and_update_session(
    session: ChillingTemperatureCorrectiveActionSession,
    user_display_name: str | None = None,
) -> dict[str, Any]:
    adapter = get_llm_adapter()

    state_data = _read_json_object(session.state_json)
    state = FreezerCorrectiveActionState(**state_data)

    validation_result = validate_freezer_corrective_action_state(state)
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
        conversation_history = _read_json_list(
            session.conversation_history_json
        )
        retry_context = _get_issue_retry_context(
            conversation_history=conversation_history,
            current_issue=first_issue,
        )
        last_user_message = _get_last_user_message(conversation_history)
        last_assistant_message = _get_last_assistant_message(
            conversation_history
        )
        recent_conversation_history = _get_recent_conversation_history(
            conversation_history
        )

        question = _build_validator_issue_message(first_issue)

        if question is None:
            question = adapter.generate_freezer_corrective_action_question(
                issue=first_issue,
                current_state=state_data,
                recent_conversation_history=recent_conversation_history,
                last_user_message=last_user_message,
                last_assistant_message=last_assistant_message,
                user_display_name=user_display_name,
                is_retry=retry_context["is_retry"],
                retry_count=retry_context["retry_count"],
            )
        conversation_history = _append_conversation_message(
            conversation_history=conversation_history,
            role="assistant",
            content=question,
            metadata=_build_issue_message_metadata(
                issue=first_issue,
                retry_context=retry_context,
            ),
        )
        session.conversation_history_json = _write_json(conversation_history)

        return _build_workflow_response(
            session=session,
            message=question,
        )

    summary = adapter.generate_freezer_corrective_action_summary(state_data)

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
            conversation_history = _read_json_list(
                session.conversation_history_json
            )
            retry_context = _get_stored_issue_retry_context(
                conversation_history=conversation_history,
                current_issue=issues[0],
            )
            user_display_name = _get_user_display_name(
                db=db,
                user_id=user_id,
            )
            question = adapter.generate_freezer_corrective_action_question(
                issue=issues[0],
                current_state=_read_json_object(session.state_json),
                recent_conversation_history=_get_recent_conversation_history(
                    conversation_history
                ),
                last_user_message=_get_last_user_message(conversation_history),
                last_assistant_message=_get_last_assistant_message(
                    conversation_history
                ),
                user_display_name=user_display_name,
                is_retry=retry_context["is_retry"],
                retry_count=retry_context["retry_count"],
            )
            return _build_workflow_response(
                session=session,
                message=question,
            )

        return _build_workflow_response(
            session=session,
            message=_build_initial_message(
                _get_user_display_name(
                    db=db,
                    user_id=user_id,
                )
            ),
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
        message=_build_initial_message(
                _get_user_display_name(
                    db=db,
                    user_id=user_id,
                )
            ),
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
        approval_result = adapter.classify_freezer_corrective_action_approval(
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

    current_issues = _read_json_list(session.issues_json)
    last_assistant_message = _get_last_assistant_message(
        conversation_history
    )
    recent_conversation_history = _get_recent_conversation_history(
        conversation_history
    )

    extracted_facts = adapter.extract_freezer_corrective_action_facts(
        user_message=user_message.strip(),
        existing_state=current_state,
        current_issues=current_issues,
        last_assistant_message=last_assistant_message,
        recent_conversation_history=recent_conversation_history,
    )

    if not _has_extracted_corrective_action_facts(
        extracted_facts=extracted_facts,
        current_state=current_state,
    ):
        if last_assistant_message is None:
            last_assistant_message = _build_initial_repeat_message()

        assistant_message = _build_unusable_answer_message(
            previous_assistant_message=last_assistant_message,
            conversation_history=conversation_history,
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

    merged_state = _merge_extracted_facts(
        current_state=current_state,
        extracted_facts=extracted_facts,
    )

    session.state_json = _write_json(merged_state)
    session.conversation_history_json = _write_json(conversation_history)

    user_display_name = _get_user_display_name(
        db=db,
        user_id=user_id,
    )
    response = _validate_state_and_update_session(
        session,
        user_display_name=user_display_name,
    )

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
                f"{incident.check_period.upper()} non-compliant freezer "
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
