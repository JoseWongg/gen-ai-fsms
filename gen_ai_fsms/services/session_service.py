from sqlalchemy.orm import Session
from gen_ai_fsms.db.models.onboarding_session import OnboardingSession

def create_session(db: Session, business_profile_id: int, user_id: int, phase: str) -> OnboardingSession:
    """Create a new onboarding session."""
    session = OnboardingSession(
        business_profile_id=business_profile_id,
        user_id=user_id,
        phase=phase,
        status="in_progress"
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

def load_session(db: Session, business_profile_id: int, phase: str) -> OnboardingSession | None:
    """Load the most recent active session for a given business profile and phase."""
    return db.query(OnboardingSession).filter(
        OnboardingSession.business_profile_id == business_profile_id,
        OnboardingSession.phase == phase,
        OnboardingSession.status == "in_progress"
    ).order_by(OnboardingSession.created_at.desc()).first()

def update_session(db: Session, session_id: int, state_json: str, status: str = "in_progress") -> OnboardingSession:
    """Update session state and optionally status."""
    session = db.query(OnboardingSession).filter(OnboardingSession.id == session_id).first()
    if session:
        session.state_json = state_json  # type: ignore
        session.status = status           # type: ignore
        db.commit()
        db.refresh(session)
    return session

def complete_session(db: Session, session_id: int) -> None:
    """Mark a session as completed."""
    session = db.query(OnboardingSession).filter(OnboardingSession.id == session_id).first()
    if session:
        session.status = "completed"  # type: ignore
        db.commit()
