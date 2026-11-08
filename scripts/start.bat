@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0.."

echo ========================================================
echo   AutoAnime Shorts - Starting Local Studio
echo ========================================================
echo.

:: Check if venv python exists
if not exist "venv\Scripts\python.exe" (
    echo [!] Virtual environment not found in .\venv
    echo [*] Running automated 1-click setup first...
    call scripts\setup.bat
    if errorlevel 1 goto :fail
)

:: Verify if core dependencies are installed in venv
"venv\Scripts\python.exe" -c "import fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
    echo [!] Core dependencies are missing in the virtual environment.
    echo [*] Installing requirements from requirements.txt...
    "venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies. Please run setup.bat manually.
        goto :fail
    )
)

echo [*] Starting Studio on http://127.0.0.1:7860 ...
"venv\Scripts\python.exe" run.py

if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo [ERROR] The application encountered an error and stopped.
pause
exit /b 1
