import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from gen_ai_fsms.db.models.test_record import TestRecord

def seed():
    load_dotenv()
    engine = create_engine(os.getenv("DATABASE_URL"))
    Session = sessionmaker(bind=engine)
    session = Session()

    # Check if already seeded
    if session.query(TestRecord).count() == 0:
        records = [
            TestRecord(name="Test Record 1"),
            TestRecord(name="Test Record 2"),
            TestRecord(name="Test Record 3"),
        ]
        session.add_all(records)
        session.commit()
        print("Seeded 3 test records.")
    else:
        print("Test records already exist. Skipping seed.")

    session.close()

if __name__ == "__main__":
    seed()
