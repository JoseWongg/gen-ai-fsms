from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from gen_ai_fsms.db.models.auth.user import User
from gen_ai_fsms.db.models.shift_diary_entry import ShiftDiaryEntry
from gen_ai_fsms.services.daily_shift_service import get_active_shift


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


def list_shift_diary_entries_for_active_shift(
    db: Session,
    business_profile_id: int,
) -> list[dict]:
    active_shift = get_active_shift(
        db=db,
        business_profile_id=business_profile_id,
    )

    if active_shift is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active daily shift found.",
        )

    entries = (
        db.query(ShiftDiaryEntry)
        .filter(
            ShiftDiaryEntry.business_profile_id == business_profile_id,
            ShiftDiaryEntry.daily_shift_id == active_shift.id,
        )
        .order_by(
            ShiftDiaryEntry.created_at.asc(),
            ShiftDiaryEntry.id.asc(),
        )
        .all()
    )

    return [
        {
            "id": entry.id,
            "business_profile_id": entry.business_profile_id,
            "daily_shift_id": entry.daily_shift_id,
            "created_by_user_id": entry.created_by_user_id,
            "created_by_name": format_user_display_name(entry.created_by_user),
            "entry_type": entry.entry_type,
            "title": entry.title,
            "entry_text": entry.entry_text,
            "related_entity_type": entry.related_entity_type,
            "related_entity_id": entry.related_entity_id,
            "created_at": entry.created_at,
            "updated_at": entry.updated_at,
        }
        for entry in entries
    ]