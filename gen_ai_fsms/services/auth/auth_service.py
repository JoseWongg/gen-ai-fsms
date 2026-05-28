from datetime import datetime, timedelta
import secrets
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from gen_ai_fsms.db.models import BusinessProfile, User
from gen_ai_fsms.repositories.auth.user_repository import UserRepository
from gen_ai_fsms.repositories.auth.token_repository import TokenRepository
from gen_ai_fsms.services.auth.password_service import hash_password, verify_password
from gen_ai_fsms.services.auth.token_service import create_access_token

class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        self.token_repo = TokenRepository(db)

    def register_user(
        self,
        business_name: str,
        site_name: str,
        email: str,
        password: str,
        first_name: str | None,
        last_name: str | None,
    ) -> dict:
        existing = self.user_repo.get_by_email(email)
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        profile = BusinessProfile(
            business_name=business_name,
            site_name=site_name,
            status="active",
        )

        self.db.add(profile)
        self.db.flush()

        user = User(
            email=email,
            hashed_password=hash_password(password),
            first_name=first_name,
            last_name=last_name,
            role="admin",
            is_active=True,
            business_profile_id=profile.id,
        )

        self.db.add(user)
        self.db.commit()

        return {"message": "User created successfully"}

    def authenticate_user(self, email: str, password: str) -> dict:
        user = self.user_repo.get_by_email(email)

        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive",
            )

        access_token = create_access_token(
            user.id,
            user.access_token_version,
        )
        return {"access_token": access_token, "token_type": "bearer"}

    def get_user_by_id(self, user_id: int):
        user = self.user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=404, detail="User not found")
        return user

    def create_password_reset_token(self, email: str) -> str | None:
        user = self.user_repo.get_by_email(email)

        if not user or not user.is_active:
            return None  # silently ignore for security

        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=24)
        self.token_repo.create_reset_token(user.id, token, expires_at)
        return token
    
    def reset_password(self, token: str, new_password: str) -> bool:
        reset_token = self.token_repo.get_valid_token(token)
        if not reset_token:
            raise HTTPException(status_code=400, detail="Invalid or expired token")
        user = self.user_repo.get_by_id(reset_token.user_id)
        if not user or not user.is_active:
            raise HTTPException(status_code=400, detail="Invalid or expired token")
        user.hashed_password = hash_password(new_password)
        self.user_repo.update(user)
        self.token_repo.mark_used(reset_token)
        return True
