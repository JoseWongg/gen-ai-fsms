# This is the session.py file that sets up the database connection and session management for SQLAlchemy.
# A central place to manage database sessions and connections that Alembic and FastAPI can use to interact with the database. 
# It uses environment variables to securely manage the database URL and creates a session factory that can be used throughout the application to create database sessions.
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
