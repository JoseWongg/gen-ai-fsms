# This module defines dependencies for the FastAPI application, including database session management and user authentication.
# The get_db function provides a database session that is properly closed after use, ensuring efficient resource management.
# The get_current_user function decodes the JWT token to retrieve the user ID, checks if the user is active, and returns the user object. If the token is invalid or the user is inactive, it raises appropriate HTTP exceptions.
# The require_admin function checks if the current user has admin privileges and raises a 403 Forbidden error if not. This can be used to protect routes that require admin access.
# These dependencies can be used in route handlers to enforce authentication and authorization, ensuring that only authorized users can access certain endpoints. The use of FastAPI's Depends allows for clean and modular code, making it easy to manage and reuse these dependencies across the application. 


from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from gen_ai_fsms.db.session import SessionLocal
from gen_ai_fsms.services.auth.token_service import decode_access_token
from gen_ai_fsms.services.auth.auth_service import AuthService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    decoded_token = decode_access_token(token)

    if decoded_token is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
        )

    user_id, token_version = decoded_token

    auth_service = AuthService(db)
    user = auth_service.get_user_by_id(user_id)

    if user.access_token_version != token_version:
        raise HTTPException(
            status_code=401,
            detail="Authentication session is no longer valid",
        )

    return user

def require_admin(current_user = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user
