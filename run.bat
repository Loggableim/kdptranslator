@echo off
REM KDP Translator Launcher for Windows
REM ======================================
REM
REM USAGE:  Double-click run.bat or execute from the command line.

setlocal enabledelayedexpansion

set "PROJECT_ROOT=%~dp0"
set "VENV_DIR=%PROJECT_ROOT%.venv"

REM ---------------------------------------------------------------
REM Check that the virtual environment exists
REM ---------------------------------------------------------------
if not exist "%VENV_DIR%" (
    echo.
    echo [ERROR] Virtual environment not found at: %VENV_DIR%
    echo.
    echo         Please run install.ps1 first to set up the project:
    echo.
    echo             PowerShell -ExecutionPolicy Bypass -File install.ps1
    echo.
    pause
    exit /b 1
)

REM ---------------------------------------------------------------
REM Check for Python inside the venv
REM ---------------------------------------------------------------
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo.
    echo [ERROR] Python not found inside the virtual environment.
    echo         The venv may be corrupted. Delete .venv and re-run install.ps1.
    echo.
    pause
    exit /b 1
)

REM ---------------------------------------------------------------
REM Activate the virtual environment
REM ---------------------------------------------------------------
echo Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"

if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

REM ---------------------------------------------------------------
REM Change to the project root directory
REM ---------------------------------------------------------------
cd /d "%PROJECT_ROOT%"

REM ---------------------------------------------------------------
REM Launch the application
REM ---------------------------------------------------------------
echo.
echo Starting KDP Translator...
echo.

REM Try flet run first (preferred method)
flet run "%PROJECT_ROOT%app\main.py"

if errorlevel 1 (
    echo.
    echo [INFO] 'flet' command not found or failed — falling back to 'python -m app.main'...
    echo.
    python -m app.main
)

if errorlevel 1 (
    echo.
    echo [ERROR] KDP Translator failed to start.
    echo         Check that all dependencies are installed.
    echo.
    pause
    exit /b 1
)

REM ---------------------------------------------------------------
REM If we get here, the app exited normally
REM ---------------------------------------------------------------
echo.
echo KDP Translator closed.
pause
