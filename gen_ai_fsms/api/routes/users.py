# This file defines the API routes related to user operations, such as retrieving the current user's information. It uses FastAPI's APIRouter to organize the endpoints under the "/users" prefix and includes a route for getting the current user's details, which requires authentication. The route handler depends on the get_current_user function to retrieve the authenticated user's information from the database and returns it in a structured format defined by the UserResponse schema.

from fastapi import APIRouter, Depends
from gen_ai_fsms.api.deps import get_current_user
from gen_ai_fsms.schemas.user import UserResponse
from gen_ai_fsms.db.models import User

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
