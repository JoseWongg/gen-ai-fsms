from sqlalchemy import text

def test_test_database(test_db_engine):
    with test_db_engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1
        db_name = conn.execute(text("SELECT DATABASE()")).scalar()
        print(f"Test database: {db_name}")
