@echo off
title AU Payroll Platform - Starting...
color 0A

echo.
echo ============================================================
echo           🦘  AU PAYROLL PLATFORM LAUNCHER
echo ============================================================
echo.

:: ── Check Docker is running ──────────────────────────────────
echo [1/5] Checking Docker Desktop...
docker info > nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  Docker Desktop is not running. Starting it now...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo  Waiting for Docker to start - please wait 30 seconds...
    timeout /t 30 /nobreak > nul
    docker info > nul 2>&1
    if %errorlevel% neq 0 (
        echo.
        echo  ERROR: Docker still not ready.
        echo  Please start Docker Desktop manually and try again.
        echo.
        pause
        exit /b 1
    )
)
echo  Docker is running OK
echo.

:: ── Navigate to project folder ────────────────────────────────
echo [2/5] Navigating to project folder...
cd /d "%~dp0"
echo  Folder: %~dp0
echo.

:: ── Stop any existing containers ─────────────────────────────
echo [3/5] Stopping any existing containers...
docker compose down > nul 2>&1
echo  Done
echo.

:: ── Start all containers in detached (headless) mode ─────────
echo [4/5] Starting all services in background...
echo  This may take 20-30 seconds on first run after a break...
echo.
docker compose up -d
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Failed to start containers.
    echo  Try running: docker compose up --build
    echo.
    pause
    exit /b 1
)
echo.

:: ── Wait for API Gateway to be ready ─────────────────────────
echo [5/5] Waiting for services to be ready...
echo.
set /a attempts=0

:WAIT_LOOP
set /a attempts+=1
if %attempts% gtr 30 (
    echo  Services took too long to start.
    echo  Check logs with: docker compose logs
    echo  Opening browser anyway...
    goto OPEN_BROWSER
)

curl -s http://localhost:8000/api/health > nul 2>&1
if %errorlevel% equ 0 (
    goto SERVICES_READY
)

echo  Waiting... attempt %attempts% of 30
timeout /t 3 /nobreak > nul
goto WAIT_LOOP

:SERVICES_READY
echo.
echo ============================================================
echo   ALL SERVICES ARE UP AND RUNNING!
echo ============================================================
echo.
echo   API Gateway  :  http://localhost:8000
echo   Frontend     :  http://localhost:3000
echo   Employee Svc :  http://localhost:8001/docs
echo   Payroll Svc  :  http://localhost:8003/docs
echo   Compliance   :  http://localhost:8004/docs
echo.
echo   Login with:
echo     Email    : admin@payroll.com.au
echo     Password : Admin1234!
echo.

:: ── Seed admin if not already seeded ─────────────────────────
echo  Seeding admin account (safe to run multiple times)...
curl -s -X POST http://localhost:8000/api/auth/seed-admin > nul 2>&1
echo  Admin account ready
echo.

:OPEN_BROWSER
:: ── Wait a moment then open browser ──────────────────────────
echo  Opening browser in 3 seconds...
timeout /t 3 /nobreak > nul
start "" http://localhost:3000

echo.
echo ============================================================
echo   PAYROLL PLATFORM IS RUNNING IN THE BACKGROUND
echo ============================================================
echo.
echo   To VIEW logs    : docker compose logs -f
echo   To STOP         : docker compose down
echo   To RESTART      : run this batch file again
echo.
echo   This window can be closed safely.
echo   Services will keep running in the background.
echo.
pause