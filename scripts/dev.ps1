# PowerShell Developer Helper Script for CastTrace AI
# Buildathon 2.0 | Problem Statement 1
param (
    [string]$Action = "help"
)

$HostIP = "127.0.0.1"
$BackendPort = "8001"
$FrontendPort = "5173"

switch ($Action.ToLower()) {
    "migrate" {
        Write-Host "Applying database migrations..." -ForegroundColor Cyan
        .\.venv\Scripts\alembic.exe upgrade head
    }
    "seed" {
        Write-Host "Seeding demo accounts..." -ForegroundColor Cyan
        .\.venv\Scripts\python.exe backend\scripts\seed.py
    }
    "backend" {
        Write-Host "Starting FastAPI backend on http://${HostIP}:${BackendPort}..." -ForegroundColor Green
        .\.venv\Scripts\uvicorn.exe backend.app.main:app --host $HostIP --port $BackendPort --reload
    }
    "worker" {
        Write-Host "Starting ML inference background worker..." -ForegroundColor Green
        .\.venv\Scripts\python.exe backend\app\worker.py --poll-interval 1.0
    }
    "frontend" {
        Write-Host "Starting Vite frontend on http://localhost:${FrontendPort}..." -ForegroundColor Green
        Push-Location frontend
        npm run dev
        Pop-Location
    }
    "test" {
        Write-Host "Running backend regression test suite..." -ForegroundColor Cyan
        .\.venv\Scripts\pytest.exe -v backend\tests
        Write-Host "Running frontend production build..." -ForegroundColor Cyan
        Push-Location frontend
        npm run build
        Pop-Location
    }
    "lint" {
        Write-Host "Running frontend lint (oxlint)..." -ForegroundColor Cyan
        Push-Location frontend
        npm run lint
        Pop-Location
    }
    "backup" {
        Write-Host "PostgreSQL database backup (pg_dump)..." -ForegroundColor Cyan
        Write-Host "Run: pg_dump -U postgres -d casttrace_dev -F c -f backups\casttrace_dev.dump" -ForegroundColor Yellow
    }
    "restore" {
        Write-Host "PostgreSQL database restoration (pg_restore)..." -ForegroundColor Cyan
        Write-Host "Run: pg_restore -U postgres -d casttrace_dev -c backups\casttrace_dev.dump" -ForegroundColor Yellow
    }
    "verify" {
        Write-Host "Running live integration verification suite..." -ForegroundColor Cyan
        .\.venv\Scripts\python.exe scripts\verify_phase5d_live.py
    }
    "smoke" {
        Write-Host "Running isolated clean-setup verification smoke test..." -ForegroundColor Cyan
        .\.venv\Scripts\python.exe scripts\verify_clean_setup.py
    }
    "status" {
        Write-Host "CastTrace AI Service Status Check" -ForegroundColor Yellow
        Write-Host "Backend Expected:  http://${HostIP}:${BackendPort}"
        Write-Host "Frontend Expected: http://localhost:${FrontendPort}"
        try {
            $h = Invoke-RestMethod -Uri "http://${HostIP}:${BackendPort}/health" -TimeoutSec 3
            Write-Host "  Backend: ONLINE (status: $($h.status), db: $($h.database))" -ForegroundColor Green
        } catch {
            Write-Host "  Backend: OFFLINE" -ForegroundColor Red
        }
        try {
            $f = Invoke-WebRequest -Uri "http://localhost:${FrontendPort}" -UseBasicParsing -TimeoutSec 3
            Write-Host "  Frontend: ONLINE (HTTP $($f.StatusCode))" -ForegroundColor Green
        } catch {
            Write-Host "  Frontend: OFFLINE" -ForegroundColor Red
        }
    }
    default {
        Write-Host "=== CastTrace AI Developer CLI ===" -ForegroundColor Yellow
        Write-Host "Usage: .\scripts\dev.ps1 <command>"
        Write-Host ""
        Write-Host "Available commands:"
        Write-Host "  backend   - Start FastAPI server on http://${HostIP}:${BackendPort}"
        Write-Host "  worker    - Start ML inference worker"
        Write-Host "  frontend  - Start Vite dev server on http://localhost:${FrontendPort}"
        Write-Host "  migrate   - Apply Alembic migrations"
        Write-Host "  seed      - Seed demo accounts (Inspector, Supervisor, QM)"
        Write-Host "  test      - Run backend pytest and frontend production build"
        Write-Host "  lint      - Run frontend linter (oxlint)"
        Write-Host "  backup    - Instructions for PostgreSQL pg_dump backup"
        Write-Host "  restore   - Instructions for PostgreSQL pg_restore restoration"
        Write-Host "  verify    - Run live Phase 5D integration verification suite"
        Write-Host "  smoke     - Run non-destructive clean-clone setup verification"
        Write-Host "  status    - Probe backend and frontend services"
        Write-Host "  help      - Show this help message"
    }
}
