# This is the main Streamlit application file that serves as the frontend for the Gen-AI Food Safety Management System.
# It uses Streamlit to create a simple dashboard that displays test records fetched from the FastAPI backend.
# The app makes an HTTP GET request to the /test-records/ endpoint of the FastAPI backend.

import streamlit as st
import httpx
import pandas as pd
import os

# Imports needed for direct database access via SQLAlchemy instead of FastAPI
# from sqlalchemy import create_engine, text
# from dotenv import load_dotenv

st.write("Gen-AI Food Safety Management - Work in progress!!!")

st.title("Test Records Dashboard (via FastAPI)")

# --- DIRECT DATABASE APPROACH via SQLAlchemy ---
# Developer note: This approach is simpler for quick testing and development, but it bypasses the FastAPI backend and its dependency management.
# It is commented out in favor of the FastAPI approach, which is more realistic for a production application and allows for better separation of concerns and scalability.  

# load_dotenv()
# engine = create_engine(os.getenv("DATABASE_URL"))
# with engine.connect() as conn:
#     df = pd.read_sql(text("SELECT id, name, created_at FROM test_records ORDER BY id"), conn)
# st.dataframe(df)
# ---------------------------------------------------------------

# --- FASTAPI APPROACH ---
# Chooses API base URL depending on environment
# If running on Heroku, use the Heroku app URL; otherwise, use localhost for local development. This allows the same code to work in both environments without changes. The API_BASE variable is used to construct the full URL for the API request to fetch test records.  
IS_HEROKU = os.getenv("DYNO") is not None   # Heroku sets this variable
if IS_HEROKU:
    API_BASE = "https://gen-ai-fsms-api-809d8118221b.herokuapp.com"
else:
    API_BASE = "http://localhost:8001"

try:
    response = httpx.get(f"{API_BASE}/test-records")
    response.raise_for_status()
    data = response.json()
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df)
    else:
        st.info("No records found.")
except Exception as e:
    st.error(f"Error connecting to API: {e}")
