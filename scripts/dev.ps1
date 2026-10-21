# PowerShell Developer Helper Script for CastTrace AI
param (
    [string]$Action = "status"
)

switch ($Action.ToLower()) {
    "migrate" {
        Write-Host "Applying database migrations..." -ForegroundColor Cyan
        .\.venv\Scripts\alembic upgrade head
    }
    "seed" {
        Write-Host "Seeding demo accounts..." -ForegroundColor Cyan
        .\.venv\Scripts\python backend\scripts\seed.py
    }
    "test" {
        Write-Host "Running backend tests..." -ForegroundColor Cyan
        .\.venv\Scripts\pytest -v backend\tests
        Write-Host "Building frontend..." -ForegroundColor Cyan
        cd frontend
        npm run build
        cd ..
    }
    "backend" {
        Write-Host "Starting FastAPI backend on http://127.0.0.1:8000..." -ForegroundColor Green
        .\.venv\Scripts\uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
    }
    "frontend" {
        Write-Host "Starting frontend on http://127.0.0.1:5173..." -ForegroundColor Green
        cd frontend
        npm run dev
    }
    default {
        Write-Host "CastTrace AI Developer CLI" -ForegroundColor Yellow
        Write-Host "Usage: .\scripts\dev.ps1 [migrate | seed | test | backend | frontend]"
    }
}
