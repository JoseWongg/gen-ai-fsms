from sqlalchemy.orm import Session
from datetime import datetime
from gen_ai_fsms.db.models import PasswordResetToken

class TokenRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_reset_token(self, user_id: int, token: str, expires_at: datetime) -> PasswordResetToken:
        reset_token = PasswordResetToken(
            user_id=user_id,
            token=token,
            expires_at=expires_at,
            used=False
        )
        self.db.add(reset_token)
        self.db.commit()
        self.db.refresh(reset_token)
        return reset_token

    def get_valid_token(self, token: str) -> PasswordResetToken | None:
        now = datetime.utcnow()
        return self.db.query(PasswordResetToken).filter(
            PasswordResetToken.token == token,
            PasswordResetToken.used == False,
            PasswordResetToken.expires_at > now
        ).first()

    def mark_used(self, token: PasswordResetToken) -> None:
        token.used = True
        self.db.commit()

    def invalidate_unused_tokens_for_user(self, user_id: int) -> None:
        self.db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used.is_(False),
        ).update(
            {PasswordResetToken.used: True},
            synchronize_session=False,
        )