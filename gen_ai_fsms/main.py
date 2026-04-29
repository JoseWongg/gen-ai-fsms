from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from gen_ai_fsms.api.routes import test_records_router, auth_router, users_router, admin_router

app = FastAPI(title="SFBB API", version="0.1.0")

origins = [
    "http://localhost:8501",
    "https://gen-ai-fsm-production-app.herokuapp.com",
    "https://gen-ai-fsm-production-app-1d7f924baa0c.herokuapp.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(test_records_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(admin_router)

@app.get("/")
def root():
    return {"message": "Welcome to the SFBB API. Use /docs for endpoints."}
