# This is a test route for fetching test records from the database. 
# It defines a GET endpoint at /test-records/ that retrieves all test records from the database using SQLAlchemy and returns them as a response. 
# The route uses dependency injection to get a database session from the deps.get_db function, which ensures that the session is properly managed and closed after use.
# Data is returned as a list of TestRecord objects, which are defined in the gen_ai_fsms.db.models.test_record module. This route can be used for testing database connectivity and retrieving test data.
# Data structure used for the response is json, which is the default response format for FastAPI. Each TestRecord object will be serialized to JSON format when returned in the response.
# Note: This route is for testing purposes and may not be included in the production API. It can be used to verify that the database connection is working and that test records can be retrieved successfully.

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from gen_ai_fsms.api import deps
from gen_ai_fsms.db.models.test_record import TestRecord

router = APIRouter(prefix="/test-records", tags=["test"])

@router.get("/")
def get_test_records(db: Session = Depends(deps.get_db)):
    records = db.query(TestRecord).all()
    return records
