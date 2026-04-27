
# This is the deps.py file that defines dependencies for FastAPI routes, such as database sessions.
# It provides a get_db function that yields a database session for use in FastAPI routes. This allows for easy dependency injection of the database session into route handlers, ensuring that the session is properly managed and closed after use. The get_db function uses the SessionLocal factory defined in the session.py file to create and manage database sessions.
from gen_ai_fsms.db.session import SessionLocal

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
