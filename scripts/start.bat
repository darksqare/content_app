@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0.."

echo =====================================================================
echo   🎬 AutoAnime Shorts - Local AI Web-Novel & Shorts Studio (Windows)
echo =====================================================================
echo [*] System Time:       %DATE% %TIME%
echo [*] Project Folder:    %CD%
echo.

:: 1. Check Python & Virtual Environment
echo [1/5] Checking Python Virtual Environment...
if not exist "venv\Scripts\python.exe" (
    echo [!] Virtual environment not found in .\venv
    echo [*] Running automated 1-click setup first...
    call scripts\setup.bat
    if errorlevel 1 goto :fail
)
for /f "tokens=*" %%v in ('"venv\Scripts\python.exe" --version 2^>^&1') do set "PY_VER=%%v"
echo       [OK] Python interpreter: .\venv\Scripts\python.exe (!PY_VER!)

:: 2. Check Core Requirements
echo.
echo [2/5] Verifying Core Application Libraries...
"venv\Scripts\python.exe" -c "import fastapi, uvicorn, diffusers, transformers, kokoro" >nul 2>&1
if errorlevel 1 (
    echo       [!] Missing dependencies detected. Installing from requirements.txt...
    "venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies. Please run setup.bat manually.
        goto :fail
    )
)
echo       [OK] FastAPI, Uvicorn, Diffusers, Kokoro, and PyTorch verified.

:: 3. Check for transformers 5.x / PyTorch 2.5.1 alignment
"venv\Scripts\python.exe" -c "import transformers; assert int(transformers.__version__.split('.')[0]) < 5" >nul 2>&1
if errorlevel 1 (
    echo       [*] Aligning transformers library for PyTorch 2.5 CUDA compatibility...
    "venv\Scripts\python.exe" -m pip install "transformers>=4.41.0,<4.49.0" "diffusers>=0.28.0,<0.32.0" "accelerate<1.0.0"
)

:: 4. Check FFmpeg Subsystem
echo.
echo [3/5] Checking FFmpeg Video Rendering Subsystem...
if exist "tools" set "PATH=%CD%\tools;!PATH!"
where ffmpeg >nul 2>&1
if errorlevel 1 (
    "venv\Scripts\python.exe" -c "import imageio_ffmpeg" >nul 2>&1
    if errorlevel 1 (
        echo       [*] Installing portable FFmpeg for video rendering...
        "venv\Scripts\python.exe" -m pip install imageio-ffmpeg
    )
)
for /f "tokens=*" %%f in ('"venv\Scripts\python.exe" -c "from core.video_engine import VideoEngine; print(VideoEngine().ffmpeg_cmd)" 2^>nul') do set "FFMPEG_LOC=%%f"
echo       [OK] FFmpeg binary: !FFMPEG_LOC!

:: 5. Hardware Diagnostics (PyTorch, CUDA, VRAM)
echo.
echo [4/5] Inspecting GPU Acceleration...
"venv\Scripts\python.exe" -c "import torch; dev = torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'; vram = f'{torch.cuda.get_device_properties(0).total_memory / (1024**3):.1f} GB' if torch.cuda.is_available() else 'N/A'; print(f'      [OK] PyTorch: {torch.__version__} | CUDA: {torch.cuda.is_available()} | GPU: {dev} ({vram} VRAM)')"

:: 6. Launch Application with Debug Logging
echo.
echo [5/5] Launching Local Studio on http://127.0.0.1:7860 ...
echo =====================================================================
echo.
"venv\Scripts\python.exe" run.py --debug

if errorlevel 1 goto :fail
exit /b 0

:fail
echo.
echo [ERROR] The application encountered an error and stopped.
pause
exit /b 1
