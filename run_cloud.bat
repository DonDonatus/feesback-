@echo off
echo ====================================================
echo Starting Cloud Node (FastAPI + Supabase PostgreSQL) on port 8001
echo Swagger UI: http://localhost:8001/docs
echo ====================================================
set NODE_TYPE=cloud
set DATABASE_URL=postgresql+psycopg://postgres.nzucydefyhnwjbkdacge:Donatus%%40010@aws-0-eu-west-1.pooler.supabase.com:5432/postgres?sslmode=require
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8001 --reload
