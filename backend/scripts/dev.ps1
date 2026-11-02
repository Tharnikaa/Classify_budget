$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$lanIp = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
    $_.InterfaceAlias -notmatch "Loopback|vEthernet" -and $_.IPAddress -notlike "169.254.*"
} | Select-Object -First 1 -ExpandProperty IPAddress)

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " ExpenseIt FastAPI Backend (Phase 0 Stateful Stubs)" -ForegroundColor Cyan
Write-Host " Local URL:   http://localhost:8000/docs" -ForegroundColor Green
if ($lanIp) {
    Write-Host " Expo LAN URL: http://$($lanIp):8000/api/v1" -ForegroundColor Yellow
    Write-Host " -> Set EXPO_PUBLIC_API_URL=http://$($lanIp):8000/api/v1 in mobile/.env" -ForegroundColor Yellow
}
Write-Host "==========================================================" -ForegroundColor Cyan

if (Test-Path ".\.venv\Scripts\uvicorn.exe") {
    .\.venv\Scripts\uvicorn.exe app.main:app --reload --host 0.0.0.0 --port 8000
} else {
    python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
}

