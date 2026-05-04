# This file defines the API routes for user authentication, including registration, login, password reset, and token generation.
# The routes use FastAPI's APIRouter to organize the endpoints under the "/auth" prefix.
# Each route handler interacts with the AuthService to perform the necessary operations, such as creating a new user, authenticating credentials, generating password reset tokens, and resetting passwords.
# The use of Pydantic models for request and response validation ensures that the API receives and returns data in the expected format, improving reliability and ease of use for clients consuming the API. The routes also leverage dependency injection to access the database session, ensuring that resources are managed efficiently and securely.    

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from gen_ai_fsms.api.deps import get_db
from gen_ai_fsms.schemas.auth import LoginRequest, TokenResponse, RegisterRequest, ForgotPasswordRequest, ResetPasswordRequest
from gen_ai_fsms.services.auth.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", status_code=201)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    return service.register_user(data.email, data.password, data.first_name, data.last_name)

@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    return service.authenticate_user(data.email, data.password)

@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    token = service.create_password_reset_token(data.email)
    if token:
        # Build the reset link (adjust domain for production)
        reset_link = f"http://localhost:8501/reset?token={token}"
        # In production, you would use https://www.ai-fsms.com/reset?token=...
        from gen_ai_fsms.services.email_service import send_reset_email
        email_sent = send_reset_email(data.email, reset_link)
        if email_sent:
            print(f"Password reset email sent to {data.email}")
        else:
            print(f"Failed to send password reset email to {data.email}")
    return {"message": "If the email exists, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    service = AuthService(db)
    service.reset_password(data.token, data.new_password)
    return {"message": "Password reset successfully"}
