# This file defines the API routes related to user operations, such as retrieving the current user's information. It uses FastAPI's APIRouter to organize the endpoints under the "/users" prefix and includes a route for getting the current user's details, which requires authentication. The route handler depends on the get_current_user function to retrieve the authenticated user's information from the database and returns it in a structured format defined by the UserResponse schema.

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from gen_ai_fsms.api.deps import get_current_user, get_db
from gen_ai_fsms.db.models import User
from gen_ai_fsms.db.models.business_profile import BusinessProfile
from gen_ai_fsms.schemas.user import UserResponse


router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
def get_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = None

    if current_user.business_profile_id is not None:
        profile = (
            db.query(BusinessProfile)
            .filter(BusinessProfile.id == current_user.business_profile_id)
            .first()
        )

    return {
        "id": current_user.id,
        "email": current_user.email,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at,
        "updated_at": current_user.updated_at,
        "business_name": profile.business_name if profile else None,
        "site_name": profile.site_name if profile else None,
    }
