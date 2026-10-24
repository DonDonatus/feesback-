Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "Starting Cloud Node (FastAPI + Supabase PostgreSQL) on port 8001" -ForegroundColor Green
Write-Host "Swagger UI: http://localhost:8001/docs" -ForegroundColor Yellow
Write-Host "====================================================" -ForegroundColor Cyan

$env:NODE_TYPE = "cloud"
$env:DATABASE_URL = "postgresql+psycopg://postgres.nzucydefyhnwjbkdacge:Donatus%40010@aws-0-eu-west-1.pooler.supabase.com:5432/postgres?sslmode=require"
& ".\.venv\Scripts\uvicorn.exe" app.main:app --host 127.0.0.1 --port 8001 --reload
