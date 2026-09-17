# ==============================================================================
# Encrypted Ledger - PowerShell Startup Script
# ==============================================================================
$Host.UI.RawUI.WindowTitle = "Encrypted Ledger - Automated Quant Workstation"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

$PyPath = "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
if (-not (Test-Path $PyPath)) {
    $PyPath = "python"
}

if (-not (Test-Path ".env")) {
    if (Test-Path "env.example") {
        Write-Host "📝 Creating .env from env.example..." -ForegroundColor Cyan
        Copy-Item "env.example" ".env"
    }
}

Write-Host "✨ Launching Encrypted Ledger on http://127.0.0.1:8080 ..." -ForegroundColor Green
& $PyPath "$ScriptDir\backend\run.py"
