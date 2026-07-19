from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from gen_ai_fsms.api.deps import get_current_user, get_db
from gen_ai_fsms.api.routes.onboarding_screening import (
    get_current_user_profile,
)
from gen_ai_fsms.db.models import User
from gen_ai_fsms.schemas.fsms_document import FSMSDocument
from gen_ai_fsms.services.fsms_document_service import (
    generate_fsms_document_for_profile,
)


router = APIRouter(
    prefix="/fsms-document",
    tags=["FSMS Document"],
)


@router.get("", response_model=FSMSDocument)
def get_current_fsms_document(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the live FSMS document for the authenticated user's business.

    The document is rebuilt from current stored information and is not
    persisted as a separate snapshot.
    """
    profile = get_current_user_profile(db, current_user)

    return generate_fsms_document_for_profile(
        db=db,
        business_profile_id=profile.id,
    )
