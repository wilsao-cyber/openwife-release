@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion
title AI Wife

cd /d "%~dp0"
set "PROJECT_DIR=%cd%"

:: Already running? Just open setup
curl -s http://localhost:8000/api/health >nul 2>&1
if not errorlevel 1 (
    start "" "http://localhost:8000/setup"
    exit /b 0
)

:: Find Python
cd /d "%PROJECT_DIR%\server"
set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if exist ".venv\bin\python.exe" set "PY=.venv\bin\python.exe"

:: No venv? First-time setup
if not defined PY (
    echo.
    echo  AI Wife - First Time Setup
    echo ============================================
    set "SYS_PY="
    :: Try common Python install locations
    for %%V in (313 312 311 310) do (
        if not defined SYS_PY (
            if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
                set "SYS_PY=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
            )
        )
    )
    :: Try PATH
    if not defined SYS_PY (
        where python >nul 2>&1
        if not errorlevel 1 (
            for /f "tokens=*" %%a in ('python -c "import sys; print(sys.executable)"') do set "SYS_PY=%%a"
        )
    )
    :: Try py launcher
    if not defined SYS_PY (
        where py >nul 2>&1
        if not errorlevel 1 (
            for /f "tokens=*" %%a in ('py -3 -c "import sys; print(sys.executable)"') do set "SYS_PY=%%a"
        )
    )
    if not defined SYS_PY (
        echo ERROR: Python not found.
        echo Please install Python 3.10+ from https://www.python.org/downloads/
        echo Make sure to check "Add Python to PATH" during installation.
        pause
        exit /b 1
    )
    echo Using: !SYS_PY!
    "!SYS_PY!" -m venv .venv
    if errorlevel 1 ( echo ERROR: venv failed. & pause & exit /b 1 )
    if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
    if exist ".venv\bin\python.exe" set "PY=.venv\bin\python.exe"
    !PY! -m pip install --upgrade pip setuptools wheel --trusted-host pypi.org --trusted-host files.pythonhosted.org -q
    !PY! -m pip install -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org
    if errorlevel 1 ( echo ERROR: Install failed. & pause & exit /b 1 )
    echo  Setup complete!
    echo.
)

:: Quick dep check
%PY% -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo Fixing missing deps...
    %PY% -m pip install -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org -q
)

:: Create dirs
if not exist "output\audio" mkdir "output\audio"
if not exist "output\vrm" mkdir "output\vrm"
if not exist "output\screenshots" mkdir "output\screenshots"
if not exist "output\media" mkdir "output\media"
if not exist "%PROJECT_DIR%\assets\audio_extracted\bgm\custom" mkdir "%PROJECT_DIR%\assets\audio_extracted\bgm\custom"
if not exist "%PROJECT_DIR%\logs" mkdir "%PROJECT_DIR%\logs"

:: SearXNG Docker (silent)
where docker >nul 2>&1
if not errorlevel 1 (
    docker ps --format "{{.Names}}" 2>nul | findstr /r "^searxng$" >nul 2>&1
    if errorlevel 1 (
        docker ps -a --format "{{.Names}}" 2>nul | findstr /r "^searxng$" >nul 2>&1
        if not errorlevel 1 docker start searxng >nul 2>&1
    )
)

:: Wait for server then open browser (background)
start "" /B "%PROJECT_DIR%\_wait_open.bat"

:: Start server
echo.
echo  AI Wife Server starting...
echo  Setup UI will open automatically.
echo  Press Ctrl+C to stop.
echo.
%PY% main.py

echo.
echo Server stopped.
pause
endlocal
