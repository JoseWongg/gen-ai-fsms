from typing import Any, Optional

from pydantic import BaseModel


class CorrectiveActionMessageRequest(BaseModel):
    message: str


class CorrectiveActionWorkflowResponse(BaseModel):
    session_id: int
    incident_id: int
    stage: str
    status: str
    message: Optional[str] = None
    issues: list[dict[str, Any]]
    final_summary: Optional[str] = None
    is_completed: bool