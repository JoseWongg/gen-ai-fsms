
# This conftest.py file defines two pytest fixtures, dev_db_engine and test_db_engine,
#  which create SQLAlchemy engine instances for connecting to the development and test
#  databases, respectively. The load_dotenv function is used to load environment 
# variables from the .env file for the development database, while the test database 
# connection string is expected to be loaded from the .env.test file via pytest-dotenv 
# configuration in pytest.ini.


import pytest
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os

@pytest.fixture(scope="session")
def dev_db_engine():
    load_dotenv('.env', override=True)
    return create_engine(os.getenv("DATABASE_URL"))

@pytest.fixture(scope="session")
def test_db_engine():
    # DATABASE_URL already from .env.test via pytest-dotenv
    return create_engine(os.getenv("DATABASE_URL"))
