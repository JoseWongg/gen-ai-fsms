from sqlalchemy.orm import Session
from gen_ai_fsms.db.models import User

class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def create(
        self,
        email: str,
        hashed_password: str,
        first_name: str | None,
        last_name: str | None,
        business_profile_id: int,
        role: str = "user",
    ) -> User:
        user = User(
            email=email,
            hashed_password=hashed_password,
            first_name=first_name,
            last_name=last_name,
            business_profile_id=business_profile_id,
            role=role,
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
      
    def get_by_id_and_business_profile(
        self,
        user_id: int,
        business_profile_id: int,
    ) -> User | None:
        return (
            self.db.query(User)
            .filter(
                User.id == user_id,
                User.business_profile_id == business_profile_id,
            )
            .first()
        )

    def list_by_business_profile(self, business_profile_id: int) -> list[User]:
        return (
            self.db.query(User)
            .filter(User.business_profile_id == business_profile_id)
            .order_by(User.id)
            .all()
        )

    def count_admins_by_business_profile(self, business_profile_id: int) -> int:
        return (
            self.db.query(User)
            .filter(
                User.business_profile_id == business_profile_id,
                User.role == "admin",
            )
            .count()
        )

    def update(self, user: User) -> User:
        self.db.commit()
        self.db.refresh(user)
        return user
