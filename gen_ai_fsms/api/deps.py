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
    user_id = decode_access_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    auth_service = AuthService(db)
    user = auth_service.get_user_by_id(user_id)
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user

def require_admin(current_user = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user
