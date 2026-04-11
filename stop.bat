@echo off
chcp 65001 >nul 2>&1

echo.
echo  Stopping AI Wife App...
echo ================================================

echo [1/3] Stopping main server...
wmic process where "commandline like '%%main.py%%' and commandline like '%%python%%'" call terminate >nul 2>&1
echo   Done

echo [2/3] Stopping Voicebox TTS...
wmic process where "commandline like '%%backend.main%%' and commandline like '%%17493%%'" call terminate >nul 2>&1
echo   Done

echo [3/3] Stopping SearXNG...
where docker >nul 2>&1
if not errorlevel 1 (
    docker stop searxng >nul 2>&1
    echo   Done
) else (
    echo   Docker not found, skipped
)

echo ================================================
echo  All services stopped.
echo.
