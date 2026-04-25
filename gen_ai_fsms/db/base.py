# This base.py file defines the SQLAlchemy declarative base class, 
# which is used as the base for all ORM models in the application. 
# By creating a Base class using declarative_base(), you can define your database models as subclasses of this Base, allowing SQLAlchemy to manage the database schema and interactions for those models.
from sqlalchemy.orm import declarative_base

Base = declarative_base()
