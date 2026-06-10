<#
.SYNOPSIS
    KDP Translator — Windows Installer

.DESCRIPTION
    Installs the KDP Translator project on Windows:
      1. Verifies Python 3.12+ is installed.
      2. Creates a Python virtual environment in .venv.
      3. Activates the virtual environment and installs dependencies.
      4. Creates .env from .env.example (if not exist).
      5. Creates run.bat for easy launching.

.NOTES
    Author : KDP Translator Team
    Requires: PowerShell 5.1+ or PowerShell Core 7+
    Platform: Windows
#>

$ErrorActionPreference = 'Stop'
$Host.UI.RawUI.WindowTitle = 'KDP Translator - Installing...'

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

function Write-Step ($Message) {
    Write-Host "  >> $Message" -ForegroundColor Cyan
}

function Write-Success ($Message) {
    Write-Host "  >> $Message" -ForegroundColor Green
}

function Write-Warning ($Message) {
    Write-Host "  >> $Message" -ForegroundColor Yellow
}

function Write-Error ($Message) {
    Write-Host "  >> ERROR: $Message" -ForegroundColor Red
}

# ---------------------------------------------------------------------------
# 1. Check Python 3.12+
# ---------------------------------------------------------------------------

Write-Step 'Checking Python installation...'

$pythonCmd = $null
$pythonVersion = $null

# Try python first, then python3
foreach ($cmd in @('python', 'python3')) {
    try {
        $versionOutput = & $cmd --version 2>&1
        if ($LASTEXITCODE -eq 0 -and $versionOutput -match 'Python (\d+)\.(\d+)') {
            $pythonCmd = $cmd
            $pythonVersion = [Version]"$($Matches.1).$($Matches.2)"
            break
        }
    } catch {
        continue
    }
}

if (-not $pythonCmd) {
    Write-Error 'Python is not installed or not found on PATH.'
    Write-Host ''
    Write-Host '  Download Python 3.12+ from: https://www.python.org/downloads/'
    Write-Host '  Make sure to check "Add Python to PATH" during installation.'
    Write-Host ''
    pause
    exit 1
}

if ($pythonVersion -lt [Version]"3.12") {
    Write-Error "Python 3.12+ is required, but found Python $pythonVersion."
    Write-Host ''
    Write-Host '  Please upgrade Python from: https://www.python.org/downloads/'
    Write-Host ''
    pause
    exit 1
}

Write-Success "Found $pythonCmd version $pythonVersion"

# ---------------------------------------------------------------------------
# 2. Determine project root (script location)
# ---------------------------------------------------------------------------

$ProjectRoot = Split-Path -Parent $PSCommandPath
Set-Location $ProjectRoot

Write-Step "Project root: $ProjectRoot"

# ---------------------------------------------------------------------------
# 3. Create virtual environment
# ---------------------------------------------------------------------------

$VenvDir = Join-Path $ProjectRoot '.venv'

if (Test-Path $VenvDir) {
    Write-Step 'Virtual environment already exists — skipping creation.'
} else {
    Write-Step 'Creating virtual environment...'
    try {
        & $pythonCmd -m venv $VenvDir
        if ($LASTEXITCODE -ne 0) { throw "venv creation failed with exit code $LASTEXITCODE" }
        Write-Success 'Virtual environment created.'
    } catch {
        Write-Error "Failed to create virtual environment: $_"
        pause
        exit 1
    }
}

# ---------------------------------------------------------------------------
# 4. Activate virtual environment & install dependencies
# ---------------------------------------------------------------------------

Write-Step 'Activating virtual environment...'

# Determine the activate script path
$ActivateScript = Join-Path $VenvDir 'Scripts' 'Activate.ps1'
if (-not (Test-Path $ActivateScript)) {
    Write-Error "Activation script not found at: $ActivateScript"
    pause
    exit 1
}

# In PowerShell we can't simply dot-source and continue — use the full python/pip paths
$PythonExe = Join-Path $VenvDir 'Scripts' 'python.exe'
$PipExe    = Join-Path $VenvDir 'Scripts' 'pip.exe'

if (-not (Test-Path $PythonExe)) {
    Write-Error "Python executable not found in virtual environment: $PythonExe"
    pause
    exit 1
}

Write-Success "Virtual environment Python: $PythonExe"

# Upgrade pip
Write-Step 'Upgrading pip...'
try {
    & $PythonExe -m pip install --upgrade pip --quiet
    Write-Success 'pip upgraded.'
} catch {
    Write-Warning "Could not upgrade pip: $_"
}

# Install requirements
$Requirements = Join-Path $ProjectRoot 'requirements.txt'
if (-not (Test-Path $Requirements)) {
    Write-Error "requirements.txt not found at: $Requirements"
    pause
    exit 1
}

Write-Step 'Installing dependencies from requirements.txt...'
try {
    & $PythonExe -m pip install -r $Requirements
    if ($LASTEXITCODE -ne 0) { throw "pip install failed with exit code $LASTEXITCODE" }
    Write-Success 'All dependencies installed.'
} catch {
    Write-Error "Failed to install dependencies: $_"
    pause
    exit 1
}

# ---------------------------------------------------------------------------
# 5. Create .env from .env.example (if not exists)
# ---------------------------------------------------------------------------

$EnvFile        = Join-Path $ProjectRoot '.env'
$EnvExampleFile = Join-Path $ProjectRoot '.env.example'

if (Test-Path $EnvFile) {
    Write-Step '.env already exists — skipping.'
} else {
    if (Test-Path $EnvExampleFile) {
        Write-Step 'Creating .env from .env.example...'
        try {
            Copy-Item -Path $EnvExampleFile -Destination $EnvFile
            Write-Success '.env created. Edit it to set your API key.'
        } catch {
            Write-Warning "Could not copy .env.example: $_"
        }
    } else {
        Write-Warning '.env.example not found — .env not created.'
    }
}

# ---------------------------------------------------------------------------
# 6. Create run.bat
# ---------------------------------------------------------------------------

$RunBat = Join-Path $ProjectRoot 'run.bat'

if (-not (Test-Path $RunBat)) {
    Write-Step 'Creating run.bat...'
    $RunBatContent = @'
@echo off
REM KDP Translator Launcher
REM =========================

set "PROJECT_ROOT=%~dp0"
set "VENV_DIR=%PROJECT_ROOT%.venv"

if not exist "%VENV_DIR%" (
    echo.
    echo [ERROR] Virtual environment not found.
    echo         Run install.ps1 first to set up the project.
    echo.
    pause
    exit /b 1
)

echo Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"

echo.
echo Starting KDP Translator...
echo.
flet run "%PROJECT_ROOT%app\main.py"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [INFO] Flet not found, trying python -m app.main ...
    python -m app.main
)
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Failed to start KDP Translator.
    pause
    exit /b 1
)
'@
    try {
        $RunBatContent | Set-Content -Path $RunBat -Encoding ASCII
        Write-Success 'run.bat created.'
    } catch {
        Write-Warning "Could not create run.bat: $_"
    }
}

# ---------------------------------------------------------------------------
# 7. Success
# ---------------------------------------------------------------------------

Write-Host ''
Write-Host '╔══════════════════════════════════════════════════════╗' -ForegroundColor Green
Write-Host '║       KDP Translator — Installation Complete!       ║' -ForegroundColor Green
Write-Host '╚══════════════════════════════════════════════════════╝' -ForegroundColor Green
Write-Host ''

Write-Host '  To launch the application:' -ForegroundColor White
Write-Host ''
Write-Host '    run.bat' -ForegroundColor Yellow
Write-Host ''
Write-Host '  Or manually:' -ForegroundColor White
Write-Host ''
Write-Host '    .venv\Scripts\activate' -ForegroundColor Yellow
Write-Host '    flet run app\main.py' -ForegroundColor Yellow
Write-Host ''
Write-Host '  Don'\''t forget to edit .env with your API key!' -ForegroundColor White
Write-Host '  (The app will work without one using the Mock provider.)' -ForegroundColor White
Write-Host ''

pause
