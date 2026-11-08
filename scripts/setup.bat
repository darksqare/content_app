@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo   AutoAnime Shorts - 1-Click Automated Setup (Windows)
echo ========================================================
echo.

cd /d "%~dp0.."

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.10+ was not found on your PATH.
    echo Please install Python 3.10 or 3.11 from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: Create Virtual Environment
if not exist "venv" (
    echo [*] Creating isolated virtual environment in .\venv ...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo [*] Activating virtual environment...
call venv\Scripts\activate.bat

:: Upgrade pip
python -m pip install --upgrade pip

:: Install PyTorch with CUDA 12.1 support for RTX 4060
echo.
echo [*] Installing PyTorch with NVIDIA CUDA 12.1 support...
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

:: Install Requirements
echo.
echo [*] Installing core application dependencies...
python -m pip install -r requirements.txt

:: Install Playwright browsers for zero-setup upload automation
echo.
echo [*] Setting up Playwright browser engine for social uploads...
python -m playwright install chromium

:: Check FFmpeg
echo.
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [NOTICE] FFmpeg is not detected in your Windows PATH.
    echo To install FFmpeg automatically on Windows 11:
    echo   winget install Gyan.FFmpeg
    echo or download from: https://www.gyan.dev/ffmpeg/builds/
) else (
    echo [OK] FFmpeg is installed and accessible.
)

echo.
echo ========================================================
echo   Setup Complete! You can now launch the app anytime
echo   by double-clicking "start.bat"
echo ========================================================
echo.
pause
