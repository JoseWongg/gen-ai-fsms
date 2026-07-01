from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import case
from sqlalchemy.orm import Session

from gen_ai_fsms.db.models.notification import Notification


UNREAD_STATUS = "unread"
READ_STATUS = "read"
NOTIFICATION_TIMEZONE = ZoneInfo("Europe/London")


def create_notification(
    db: Session,
    recipient_user_id: int,
    notification_type: str,
    title: str,
    message: str,
    business_profile_id: Optional[int] = None,
    daily_shift_id: Optional[int] = None,
    related_entity_type: Optional[str] = None,
    related_entity_id: Optional[int] = None,
    action_route: Optional[str] = None,
    commit: bool = True,
    refresh: bool = True,
) -> Notification:
    notification = Notification(
        recipient_user_id=recipient_user_id,
        business_profile_id=business_profile_id,
        daily_shift_id=daily_shift_id,
        notification_type=notification_type,
        title=title,
        message=message,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        action_route=action_route,
        status=UNREAD_STATUS,
    )

    db.add(notification)

    if commit:
        db.commit()

        if refresh:
            db.refresh(notification)
    else:
        db.flush()

        if refresh:
            db.refresh(notification)

    return notification


def list_notifications_for_user(
    db: Session,
    recipient_user_id: int,
) -> list[Notification]:
    return (
        db.query(Notification)
        .filter(Notification.recipient_user_id == recipient_user_id)
        .order_by(
            case((Notification.status == UNREAD_STATUS, 0), else_=1),
            Notification.created_at.desc(),
            Notification.id.desc(),
        )
        .all()
    )


def get_unread_notification_count(
    db: Session,
    recipient_user_id: int,
) -> int:
    return (
        db.query(Notification)
        .filter(
            Notification.recipient_user_id == recipient_user_id,
            Notification.status == UNREAD_STATUS,
        )
        .count()
    )


def get_notification_for_user(
    db: Session,
    notification_id: int,
    recipient_user_id: int,
) -> Notification:
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.recipient_user_id == recipient_user_id,
        )
        .first()
    )

    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        )

    return notification


def mark_notification_read(
    db: Session,
    notification_id: int,
    recipient_user_id: int,
) -> Notification:
    notification = get_notification_for_user(
        db=db,
        notification_id=notification_id,
        recipient_user_id=recipient_user_id,
    )

    if notification.status == READ_STATUS:
        return notification

    notification.status = READ_STATUS
    notification.read_at = datetime.now(NOTIFICATION_TIMEZONE)

    db.commit()
    db.refresh(notification)

    return notification


def mark_all_notifications_read(
    db: Session,
    recipient_user_id: int,
) -> int:
    unread_notifications = (
        db.query(Notification)
        .filter(
            Notification.recipient_user_id == recipient_user_id,
            Notification.status == UNREAD_STATUS,
        )
        .all()
    )

    updated_count = len(unread_notifications)

    if updated_count == 0:
        return 0

    read_at = datetime.now(NOTIFICATION_TIMEZONE)

    for notification in unread_notifications:
        notification.status = READ_STATUS
        notification.read_at = read_at

    db.commit()

    return updated_count