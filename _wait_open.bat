@echo off
:: Wait for server to be ready, then open browser
for /L %%i in (1,1,30) do (
    timeout /t 1 /nobreak >nul
    curl -s http://localhost:8000/api/health >nul 2>&1
    if not errorlevel 1 (
        start "" "http://localhost:8000/setup"
        exit /b 0
    )
)
