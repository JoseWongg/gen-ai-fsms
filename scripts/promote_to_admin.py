# This script promotes a user to admin based on their email address.
# To run the script, use the command: python scripts/promote_to_admin.py <email>
# Example: python promote_to_admin.py some@email.com

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from gen_ai_fsms.db.models import User

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def promote_user(email):
    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        print(f"User with email {email} not found.")
        return
    if user.role == "admin":
        print(f"User {email} is already an admin.")
        return
    user.role = "admin"
    db.commit()
    print(f"User {email} has been promoted to admin.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python promote_to_admin.py <email>")
        sys.exit(1)
    promote_user(sys.argv[1])
