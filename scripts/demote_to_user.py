# This script demotes an admin user to a regular user based on their email address.
# To run the script, use the command: python scripts/demote_to_user.py <email>
# Example: python scripts\demote_to_user.py some@email.com
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

def demote_user(email):
    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        print(f"User with email {email} not found.")
        return
    if user.role == "user":
        print(f"User {email} is already a regular user.")
        return
    user.role = "user"
    db.commit()
    print(f"User {email} has been demoted to regular user.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python demote_to_user.py <email>")
        sys.exit(1)
    demote_user(sys.argv[1])
