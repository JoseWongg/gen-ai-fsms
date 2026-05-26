from pydantic import BaseModel, EmailStr

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class RegisterRequest(BaseModel):
    business_name: str
    site_name: str
    email: EmailStr
    password: str
    first_name: str | None = None
    last_name: str | None = None

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
