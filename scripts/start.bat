@echo off
setlocal

cd /d "%~dp0.."

echo ========================================================
echo   AutoAnime Shorts - Starting Local Studio
echo ========================================================
echo.

if not exist "venv\Scripts\activate.bat" (
    echo [!] Virtual environment not found. Running setup.bat first...
    call scripts\setup.bat
)

call venv\Scripts\activate.bat

echo [*] Starting Studio on http://127.0.0.1:7860 ...
python run.py

pause
