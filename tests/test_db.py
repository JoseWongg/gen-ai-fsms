# This test checks if the MySQL database connection is successful by executing a simple query.
# to run this test, ensure you have a .env file with the DATABASE_URL variable set to your MySQL connection string.
# To run: pytest tests/test_dev_database.py

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

def test_mysql_connection():
    load_dotenv()
    engine = create_engine(os.getenv("DATABASE_URL"))
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        val = result.scalar()
        assert val == 1
        print("MySQL connection successful:", val)


