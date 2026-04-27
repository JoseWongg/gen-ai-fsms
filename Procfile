web: if [ "$APP_TYPE" = "backend" ]; then uvicorn gen_ai_fsms.main:app --host 0.0.0.0 --port ${PORT}; else streamlit run frontend/app.py --server.port ${PORT} --server.address 0.0.0.0; fi
