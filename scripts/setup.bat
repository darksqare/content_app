@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo   AutoAnime Shorts - 1-Click Automated Setup (Windows)
echo ========================================================
echo.

cd /d "%~dp0.."

:: Check if Python is available
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python was not found in your system PATH.
    echo Please install Python 3.10 or 3.11 from https://www.python.org/downloads/
    echo IMPORTANT: Check the box "Add python.exe to PATH" during installation.
    pause
    exit /b 1
)

:: Create Virtual Environment
if not exist "venv\Scripts\python.exe" (
    echo [*] Creating isolated virtual environment in .\venv ...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created.
) else (
    echo [OK] Virtual environment exists in .\venv.
)

set VENV_PY="%~dp0..\venv\Scripts\python.exe"

:: Upgrade pip in venv
echo.
echo [*] Upgrading pip...
%VENV_PY% -m pip install --upgrade pip

:: Install PyTorch with CUDA 12.1 for NVIDIA RTX 4060
echo.
echo [*] Installing PyTorch with NVIDIA CUDA 12.1 support...
%VENV_PY% -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
if errorlevel 1 (
    echo [!] CUDA wheel failed, falling back to standard PyTorch...
    %VENV_PY% -m pip install torch torchvision
)

:: Install Application Requirements
echo.
echo [*] Installing core application requirements (FastAPI, Diffusers, Kokoro, etc.)...
%VENV_PY% -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Encountered an error while installing requirements.
    pause
    exit /b 1
)

:: Check Playwright Browsers for Social Upload
echo.
echo [*] Setting up browser automation engine...
%VENV_PY% -m playwright install chromium >nul 2>&1

:: Check FFmpeg
echo.
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo [NOTICE] FFmpeg is not detected in your Windows PATH.
    echo To install FFmpeg automatically on Windows 11, open PowerShell and run:
    echo   winget install Gyan.FFmpeg
    echo or download directly from: https://www.gyan.dev/ffmpeg/builds/
) else (
    echo [OK] FFmpeg is installed and accessible.
)

echo.
echo ========================================================
echo   Setup Complete!
echo   Double-click "start.bat" to launch the Studio anytime!
echo ========================================================
echo.
pause
