# Stops the KnowledgeOps AI dev stack (backend uvicorn :8000 + Vite :5173).
$ErrorActionPreference = 'SilentlyContinue'

$listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    $listener | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {
        Write-Host "Stopping backend (PID $_)..."
        Stop-Process -Id $_ -Force
    }
} else {
    Write-Host 'No backend process found on port 8000.'
}

$viteProcs = Get-CimInstance Win32_Process -Filter "Name = 'node.exe'" |
    Where-Object { $_.CommandLine -match 'vite' }
if ($viteProcs) {
    $viteProcs | ForEach-Object {
        Write-Host "Stopping Vite (PID $_($_.ProcessId))..."
        Stop-Process -Id $_.ProcessId -Force
    }
} else {
    Write-Host 'No Vite process found.'
}

Write-Host 'Dev stack stopped.'
