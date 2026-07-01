from datetime import datetime

from sqlalchemy.orm import Session

from gen_ai_fsms.db.models.auth.user import User
from gen_ai_fsms.db.models.chilling_temperature_incident import (
    ChillingTemperatureIncident,
)
from gen_ai_fsms.db.models.daily_shift import DailyShift
from gen_ai_fsms.db.models.daily_shift_chilling_temperature_check import (
    DailyShiftChillingTemperatureCheck,
)
from gen_ai_fsms.db.models.shift_diary_entry import ShiftDiaryEntry
from gen_ai_fsms.services.chilling_temperature_compliance_service import (
    build_chilling_temperature_non_compliance_message,
    get_chilling_temperature_threshold,
    is_chilling_temperature_compliant,
    normalize_chilling_equipment_type,
    parse_temperature,
)
from gen_ai_fsms.services.notification_service import create_notification

INCIDENT_STATUS_OPEN = "open"

NOTIFICATION_TYPE_CHILLING_TEMPERATURE_NON_COMPLIANCE = (
    "chilling_temperature_non_compliance"
)

DIARY_ENTRY_TYPE_CHILLING_TEMPERATURE_INCIDENT = "chilling_temperature_incident"


def format_user_display_name(user: User | None) -> str:
    if user is None:
        return "Unknown user"

    full_name_parts = [
        user.first_name,
        user.last_name,
    ]

    full_name = " ".join(
        part.strip()
        for part in full_name_parts
        if part and part.strip()
    )

    if full_name:
        return full_name

    return user.email


def get_user_display_name(db: Session, user_id: int) -> str:
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    return format_user_display_name(user)


def record_chilling_temperature_incident_if_needed(
    db: Session,
    active_shift: DailyShift,
    check: DailyShiftChillingTemperatureCheck,
    check_period: str,
    temperature,
    recorded_by_user_id: int,
    recorded_at: datetime,
) -> ChillingTemperatureIncident | None:
    if is_chilling_temperature_compliant(
        equipment_type=check.equipment_type_snapshot,
        temperature=temperature,
    ):
        return None

    existing_incident = (
        db.query(ChillingTemperatureIncident)
        .filter(
            ChillingTemperatureIncident.chilling_temperature_check_id == check.id,
            ChillingTemperatureIncident.check_period == check_period,
        )
        .first()
    )

    if existing_incident is not None:
        return existing_incident

    parsed_temperature = parse_temperature(temperature)
    threshold = get_chilling_temperature_threshold(check.equipment_type_snapshot)
    normalized_equipment_type = normalize_chilling_equipment_type(
        check.equipment_type_snapshot,
    )
    recorded_by_name = get_user_display_name(
        db=db,
        user_id=recorded_by_user_id,
    )

    base_message = build_chilling_temperature_non_compliance_message(
        equipment_name=check.equipment_name_snapshot,
        equipment_type=check.equipment_type_snapshot,
        temperature=parsed_temperature,
        check_period=check_period.upper(),
    )

    message = f"{base_message} Recorded by: {recorded_by_name}."

    incident = ChillingTemperatureIncident(
        business_profile_id=active_shift.business_profile_id,
        daily_shift_id=active_shift.id,
        chilling_temperature_check_id=check.id,
        chilling_equipment_id=check.chilling_equipment_id,
        check_period=check_period,
        equipment_asset_code_snapshot=check.equipment_asset_code_snapshot,
        equipment_name_snapshot=check.equipment_name_snapshot,
        equipment_type_snapshot=check.equipment_type_snapshot,
        recorded_temperature=parsed_temperature,
        compliance_threshold=threshold,
        recorded_by_user_id=recorded_by_user_id,
        recorded_at=recorded_at,
        status=INCIDENT_STATUS_OPEN,
    )

    db.add(incident)
    db.flush()

    create_notification(
        db=db,
        recipient_user_id=active_shift.started_by_user_id,
        business_profile_id=active_shift.business_profile_id,
        daily_shift_id=active_shift.id,
        notification_type=NOTIFICATION_TYPE_CHILLING_TEMPERATURE_NON_COMPLIANCE,
        title=(
            f"{check_period.upper()} non-compliant "
            f"{normalized_equipment_type} temperature - "
            f"{check.equipment_name_snapshot}"
        ),
        message=message,
        related_entity_type="chilling_temperature_incident",
        related_entity_id=incident.id,
        action_route="shift_checklist",
        commit=False,
        refresh=False,
    )

    diary_entry = ShiftDiaryEntry(
        business_profile_id=active_shift.business_profile_id,
        daily_shift_id=active_shift.id,
        created_by_user_id=recorded_by_user_id,
        entry_type=DIARY_ENTRY_TYPE_CHILLING_TEMPERATURE_INCIDENT,
        title=(
            f"{check_period.upper()} non-compliant "
            f"{normalized_equipment_type} temperature recorded"
        ),
        entry_text=message,
        related_entity_type="chilling_temperature_incident",
        related_entity_id=incident.id,
    )

    db.add(diary_entry)

    return incident