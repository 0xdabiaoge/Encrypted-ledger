@echo off
title Encrypted Ledger - Quant Trading Station
cd /d "%~dp0"

echo ======================================================================
echo   Encrypted Ledger - Automated Quant Trading Station
echo ======================================================================

set PY_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe
if not exist "%PY_EXE%" (
    set PY_EXE=python.exe
)

if not exist ".env" (
    if exist "env.example" (
        echo [INFO] Copying env.example to .env ...
        copy env.example .env
    )
)

echo [INFO] Launching Encrypted Ledger on http://127.0.0.1:8080 ...
"%PY_EXE%" "%~dp0backend\run.py"
pause
