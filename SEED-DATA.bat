@echo off
title AU Payroll - Seed Sample Data
color 0A

echo.
echo ============================================================
echo       AU PAYROLL PLATFORM - SAMPLE DATA SEEDER
echo ============================================================
echo.
echo  This will insert 100+ sample records into all tables:
echo    - 100 Employees (Australian names, real addresses)
echo    - 300+ Timesheets (with hours, overtime, leave)
echo    - 50  Leave Requests
echo    - 20  User login accounts
echo.
echo  Make sure docker compose up is running first!
echo.
pause

:: Navigate to script folder
cd /d "%~dp0"

echo.
echo [1/3] Checking Python installation...
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Python not found.
    echo  Download from: https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during install
    echo.
    pause
    exit /b 1
)
python --version
echo  Python found OK
echo.

echo [2/3] Installing required packages...
pip install requests --quiet
if %errorlevel% neq 0 (
    echo  Warning: pip install had issues, trying to continue...
)
echo  Packages ready
echo.

echo [3/3] Running data seeder...
echo.
python seed_data.py

echo.
if %errorlevel% equ 0 (
    echo ============================================================
    echo   SUCCESS! Sample data loaded.
    echo   Open http://localhost:3000 to see your data
    echo ============================================================
) else (
    echo ============================================================
    echo   Something went wrong. Check the error above.
    echo   Make sure: docker compose up is running
    echo ============================================================
)
echo.
pause
