from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from gen_ai_fsms.api.deps import get_db, require_admin
from gen_ai_fsms.db.models import User
from gen_ai_fsms.db.models.business_profile import BusinessProfile
from gen_ai_fsms.repositories.auth.user_repository import UserRepository
from gen_ai_fsms.schemas.user import UserCreate, UserResponse
from gen_ai_fsms.services.auth.password_service import hash_password


router = APIRouter(prefix="/admin", tags=["Admin"])

@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_venue_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user_repo = UserRepository(db)

    existing = user_repo.get_by_email(data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    profile = (
        db.query(BusinessProfile)
        .filter(BusinessProfile.id == current_user.business_profile_id)
        .first()
    )

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business profile not found for current admin",
        )

    user = user_repo.create(
        email=data.email,
        hashed_password=hash_password(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
        business_profile_id=current_user.business_profile_id,
        role="user",
    )

    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "business_name": profile.business_name,
        "site_name": profile.site_name,
    }

@router.get("/users", response_model=list[UserResponse])
def list_venue_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user_repo = UserRepository(db)

    profile = (
        db.query(BusinessProfile)
        .filter(BusinessProfile.id == current_user.business_profile_id)
        .first()
    )

    users = user_repo.list_by_business_profile(current_user.business_profile_id)

    return [
        {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "is_active": user.is_active,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "business_name": profile.business_name if profile else None,
            "site_name": profile.site_name if profile else None,
        }
        for user in users
    ]

@router.patch("/users/{user_id}/promote", response_model=UserResponse)
def promote_venue_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user_repo = UserRepository(db)

    target_user = user_repo.get_by_id_and_business_profile(
        user_id=user_id,
        business_profile_id=current_user.business_profile_id,
    )

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in your venue",
        )

    if target_user.role != "admin":
        target_user.role = "admin"
        user_repo.update(target_user)

    profile = (
        db.query(BusinessProfile)
        .filter(BusinessProfile.id == current_user.business_profile_id)
        .first()
    )

    return {
        "id": target_user.id,
        "email": target_user.email,
        "first_name": target_user.first_name,
        "last_name": target_user.last_name,
        "role": target_user.role,
        "is_active": target_user.is_active,
        "created_at": target_user.created_at,
        "updated_at": target_user.updated_at,
        "business_name": profile.business_name if profile else None,
        "site_name": profile.site_name if profile else None,
    }

@router.patch("/users/{user_id}/demote", response_model=UserResponse)
def demote_venue_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user_repo = UserRepository(db)

    target_user = user_repo.get_by_id_and_business_profile(
        user_id=user_id,
        business_profile_id=current_user.business_profile_id,
    )

    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in your venue",
        )

    if target_user.role == "admin":
        admin_count = user_repo.count_admins_by_business_profile(
            current_user.business_profile_id
        )

        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A venue must retain at least one admin user",
            )

        target_user.role = "user"
        user_repo.update(target_user)

    profile = (
        db.query(BusinessProfile)
        .filter(BusinessProfile.id == current_user.business_profile_id)
        .first()
    )

    return {
        "id": target_user.id,
        "email": target_user.email,
        "first_name": target_user.first_name,
        "last_name": target_user.last_name,
        "role": target_user.role,
        "is_active": target_user.is_active,
        "created_at": target_user.created_at,
        "updated_at": target_user.updated_at,
        "business_name": profile.business_name if profile else None,
        "site_name": profile.site_name if profile else None,
    }