import streamlit as st
import os
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

st.write("Gen-AI Food Safety Management - Work in progress!!!")

st.title("Test Records Dashboard")

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))

with engine.connect() as conn:
    df = pd.read_sql(text("SELECT id, name, created_at FROM test_records ORDER BY id"), conn)

st.dataframe(df)