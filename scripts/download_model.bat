@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0.."

echo ========================================================
echo   AutoAnime Shorts - Download Local LLM Model (GGUF)
echo ========================================================
echo.

if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" scripts\download_model.py
) else (
    python scripts\download_model.py
)

if errorlevel 1 (
    echo.
    echo [ERROR] Model download did not complete successfully.
) else (
    echo.
    echo [OK] Done!
)
pause
