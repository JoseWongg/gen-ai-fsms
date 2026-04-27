# this test verifies that the dev database is correctly set up and accessible 

from sqlalchemy import text

def test_dev_database(dev_db_engine):
    with dev_db_engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1
        db_name = conn.execute(text("SELECT DATABASE()")).scalar()
        print(f"Dev database: {db_name}")
