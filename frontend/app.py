# This is the main Streamlit application file that serves as the frontend for the Gen-AI Food Safety Management System.
# It uses Streamlit to create a simple dashboard that displays test records fetched from the FastAPI backend. 
# The app makes an HTTP GET request to the /test-records/ endpoint of the FastAPI backend.

import streamlit as st
import httpx
import pandas as pd

# Imports needed for direct database access via SQLAlchemy instead of FastAPI
# import os
# from sqlalchemy import create_engine, text
# from dotenv import load_dotenv

st.write("Gen-AI Food Safety Management - Work in progress!!!")

st.title("Test Records Dashboard (via FastAPI)")

# --- DIRECT DATABASE APPROACH via SQLAlchemy ---
# load_dotenv()
# engine = create_engine(os.getenv("DATABASE_URL"))
# with engine.connect() as conn:
#     df = pd.read_sql(text("SELECT id, name, created_at FROM test_records ORDER BY id"), conn)
# st.dataframe(df)
# ----------------------------------------------------

# --- FASTAPI APPROACH ---
try:
    response = httpx.get("http://localhost:8001/test-records/")
    response.raise_for_status()
    data = response.json()
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df)
    else:
        st.info("No records found.")
except Exception as e:
    st.error(f"Error connecting to API: {e}")