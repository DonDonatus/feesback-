Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "Starting Local Node (FastAPI + SQLite) on port 8000" -ForegroundColor Green
Write-Host "Swagger UI: http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host "===================================================" -ForegroundColor Cyan

$env:NODE_TYPE = "local"
$env:DATABASE_URL = "sqlite:///./data/local.db"
& ".\.venv\Scripts\uvicorn.exe" app.main:app --host 127.0.0.1 --port 8000 --reload
