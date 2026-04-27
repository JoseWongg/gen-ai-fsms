from fastapi import FastAPI
from gen_ai_fsms.api.routes import test_records

app = FastAPI(title="SFBB API", version="0.1.0")

app.include_router(test_records.router)

@app.get("/")
def root():
    return {"message": "Welcome to the SFBB API. Use /test-records to get test data."}
