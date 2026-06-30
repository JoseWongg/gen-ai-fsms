from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from gen_ai_fsms.api.deps import get_current_user, get_db
from gen_ai_fsms.db.models import User
from gen_ai_fsms.schemas.notification import (
    NotificationMarkAllReadResponse,
    NotificationResponse,
    NotificationUnreadCountResponse,
)
from gen_ai_fsms.services.notification_service import (
    get_unread_notification_count,
    list_notifications_for_user,
    mark_all_notifications_read,
    mark_notification_read,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=list[NotificationResponse])
def get_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_notifications_for_user(
        db=db,
        recipient_user_id=current_user.id,
    )


@router.get("/unread-count", response_model=NotificationUnreadCountResponse)
def get_notifications_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    unread_count = get_unread_notification_count(
        db=db,
        recipient_user_id=current_user.id,
    )

    return {"unread_count": unread_count}


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return mark_notification_read(
        db=db,
        notification_id=notification_id,
        recipient_user_id=current_user.id,
    )


@router.patch("/read-all", response_model=NotificationMarkAllReadResponse)
def mark_all_user_notifications_as_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    updated_count = mark_all_notifications_read(
        db=db,
        recipient_user_id=current_user.id,
    )

    return {"updated_count": updated_count}