@echo off
title School Fee Management System - Local Offline Server
color 0A
echo ================================================================
echo    ACHIMOTA SCHOOL - FEE MANAGEMENT SYSTEM (LOCAL OFFLINE)
echo ================================================================
echo.
echo Database: data\local.db (SQLite on hard drive)
echo Mode:     100%% Offline (No Internet Required)
echo API Docs: http://localhost:8000/docs
echo.
echo Starting FastAPI Backend Server on http://127.0.0.1:8000 ...
echo ================================================================
echo.

set NODE_TYPE=local
set DATABASE_URL=sqlite:///./data/local.db

cd /d "%~dp0"
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload
