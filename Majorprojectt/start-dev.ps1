# One-click dev stack for KnowledgeOps AI.
# Starts FastAPI backend (127.0.0.1:8000) then Vite frontend (localhost:5173),
# waiting for the backend health check before launching the frontend so the UI
# never renders against a dead API.
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $root 'backend'

function Get-BackendHealthy {
    try {
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 2 -UseBasicParsing
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

function Get-FrontendUp {
    try {
        $r = Invoke-WebRequest -Uri 'http://localhost:5173' -TimeoutSec 2 -UseBasicParsing
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

Write-Host '=== KnowledgeOps AI - starting dev stack ===' -ForegroundColor Cyan

# 1) Backend
if (Get-BackendHealthy) {
    Write-Host '[1/2] Backend already running on http://127.0.0.1:8000' -ForegroundColor Green
} else {
    Write-Host '[1/2] Starting FastAPI backend (uvicorn :8000)...' -ForegroundColor Yellow
    $env:PYTHONIOENCODING = 'utf-8'
    Start-Process -FilePath 'python' `
        -ArgumentList '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000' `
        -WorkingDirectory $backendDir -WindowStyle Hidden
    $ok = $false
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 750
        if (Get-BackendHealthy) { $ok = $true; break }
    }
    if (-not $ok) {
        Write-Host 'Backend failed to start. Run manually:' -ForegroundColor Red
        Write-Host '  cd backend && python -m uvicorn app.main:app --port 8000'
        exit 1
    }
    Write-Host 'Backend healthy: http://127.0.0.1:8000/api/health' -ForegroundColor Green
}

# 2) Frontend
if (Get-FrontendUp) {
    Write-Host '[2/2] Frontend already running on http://localhost:5173' -ForegroundColor Green
} else {
    Write-Host '[2/2] Starting Vite dev server (npm run dev)...' -ForegroundColor Yellow
    Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', 'npm run dev' -WorkingDirectory $root -WindowStyle Hidden
    $ok = $false
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 750
        if (Get-FrontendUp) { $ok = $true; break }
    }
    if (-not $ok) {
        Write-Host 'Vite failed to start. Run manually: npm run dev' -ForegroundColor Red
        exit 1
    }
    Write-Host 'Frontend up: http://localhost:5173' -ForegroundColor Green
}

Write-Host ''
Write-Host '=== Stack ready ===' -ForegroundColor Cyan
Write-Host '  Frontend : http://localhost:5173'
Write-Host '  Backend  : http://127.0.0.1:8000/api/health'
Write-Host '  Stop all : stop-dev.bat'
Write-Host ''
Write-Host 'Press Ctrl+C to close this window (servers keep running).'
try { Wait-Character } catch { }
