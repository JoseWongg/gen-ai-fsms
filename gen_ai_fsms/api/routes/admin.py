
from fastapi import APIRouter, Depends
from gen_ai_fsms.api.deps import require_admin
from gen_ai_fsms.db.models import User

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/", dependencies=[Depends(require_admin)])
def admin_placeholder(current_user: User = Depends(require_admin)):
    return {"message": "Admin area / work in progress"}
