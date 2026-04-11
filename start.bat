@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:: AI Wife App - Windows One-click Startup

cd /d "%~dp0"
set "PROJECT_DIR=%cd%"

echo.
echo  AI Wife App Starting...
echo ================================================

:: -- 1. SearXNG --
echo [1/3] SearXNG...
where docker >nul 2>&1
if errorlevel 1 (
    echo   ! Docker not found - SearXNG skipped
    goto :voicebox
)

docker ps --format "{{.Names}}" 2>nul | findstr /r "^searxng$" >nul 2>&1
if not errorlevel 1 (
    echo   Already running
    goto :voicebox
)

docker ps -a --format "{{.Names}}" 2>nul | findstr /r "^searxng$" >nul 2>&1
if not errorlevel 1 (
    docker start searxng >nul 2>&1
    echo   Restarted
    goto :voicebox
)

docker run -d --name searxng -p 8080:8080 searxng/searxng:latest >nul 2>&1
timeout /t 3 /nobreak >nul
echo   Created and started

:voicebox
:: -- 2. Voicebox --
echo [2/3] Voicebox TTS...

curl -s http://localhost:17493/profiles >nul 2>&1
if not errorlevel 1 (
    echo   Already running
    goto :mainserver
)

set "VB_PATH="
if defined VOICEBOX_PATH (
    set "VB_PATH=%VOICEBOX_PATH%"
) else if exist "%USERPROFILE%\voicebox\backend\venv\Scripts\python.exe" (
    set "VB_PATH=%USERPROFILE%\voicebox"
) else if exist "%USERPROFILE%\voicebox\backend\venv\bin\python.exe" (
    set "VB_PATH=%USERPROFILE%\voicebox"
) else (
    echo   ! Voicebox not found. TTS will be unavailable.
    goto :mainserver
)

echo   Starting from: %VB_PATH%
if not exist "%PROJECT_DIR%\logs" mkdir "%PROJECT_DIR%\logs"
:: Detect Voicebox Python (supports both layouts)
set "VB_PY="
if exist "%VB_PATH%\backend\venv\Scripts\python.exe" set "VB_PY=%VB_PATH%\backend\venv\Scripts\python.exe"
if exist "%VB_PATH%\backend\venv\bin\python.exe" set "VB_PY=%VB_PATH%\backend\venv\bin\python.exe"
start "voicebox" /B "%VB_PY%" -m backend.main --port 17493 > "%PROJECT_DIR%\logs\voicebox.log" 2>&1
echo   Started.

:mainserver
:: -- 3. Main Server --
echo [3/3] AI Wife App Server...
cd /d "%PROJECT_DIR%\server"

:: Detect Python in .venv (supports both Windows Scripts\ and MSYS2 bin\ layouts)
set "PYTHON="
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"
if exist ".venv\bin\python.exe" set "PYTHON=.venv\bin\python.exe"

if not defined PYTHON (
    echo   No .venv found. Run setup.bat first!
    echo   Attempting to create one now...
    python -m venv .venv
    if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"
    if exist ".venv\bin\python.exe" set "PYTHON=.venv\bin\python.exe"
    if not defined PYTHON (
        echo   ERROR: Cannot create venv. Check your Python installation.
        pause
        exit /b 1
    )
    %PYTHON% -m pip install --upgrade pip setuptools wheel
    %PYTHON% -m pip install -r requirements.txt
)

:: Create missing directories
if not exist "output\audio" mkdir "output\audio"
if not exist "output\vrm" mkdir "output\vrm"
if not exist "..\assets\audio_extracted" mkdir "..\assets\audio_extracted"

echo ================================================
echo.
echo  All services started!
echo    Web UI:    http://localhost:8000
echo    Voicebox:  http://localhost:17493
echo    SearXNG:   http://localhost:8080
echo.
echo    Press Ctrl+C to stop server
echo ================================================

start "" /B cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"

%PYTHON% main.py 2>&1

endlocal
