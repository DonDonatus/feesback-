@echo off
echo ===================================================
echo Starting Local Node (FastAPI + SQLite) on port 8000
echo Swagger UI: http://localhost:8000/docs
echo ===================================================
set NODE_TYPE=local
set DATABASE_URL=sqlite:///./data/local.db
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload
