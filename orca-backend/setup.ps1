# ==========================================================================
# FloatChat/ORCA Backend Setup & Runner (Windows / PowerShell 5.1+)
#
# Usage:
#   .\setup.ps1             # interactive menu (setup / run / test / smoke)
#   .\setup.ps1 -Install    # create venv + install requirements
#   .\setup.ps1 -Env        # create .env from .env.example (if absent)
#   .\setup.ps1 -Migrate    # alembic upgrade head (needs reachable DB)
#   .\setup.ps1 -Run        # launch uvicorn
#   .\setup.ps1 -Test       # run the full pytest suite (415 pass / 2 skip)
#   .\setup.ps1 -Smoke      # hit health/ready/contract/mcp-tools endpoints
#
# Repository layout facts baked in:
#   - API lives in $RepoRoot\apps\api; PYTHONPATH is set to it when running.
#   - ONE unified venv lives at $RepoRoot\venv and ONE unified .env lives at
#     $RepoRoot\.env (moved from apps\api\... on 2026-09-07).  config.py
#     resolves the repo-root .env by absolute path, so CWD no longer matters.
#   - The venv MUST be invoked by ABSOLUTE path in PowerShell; a relative
#     `venv\Scripts\python.exe` fails with "The module 'apps' could not be
#     loaded". Use the absolute path below.
#   - Non-DB pytest needs $env:POSTGIS_DATABASE_URL="".
#   - Migrations read DATABASE_URL from the repo-root .env via app settings
#     (migrations/env.py falls back to app.config when the env var is unset).
# ==========================================================================

[CmdletBinding()]
param(
    [switch]$Install,
    [switch]$Env,
    [switch]$Migrate,
    [switch]$Run,
    [switch]$Test,
    [switch]$Smoke,
    [switch]$All
)

$ErrorActionPreference = 'Stop'

$RepoRoot   = (Resolve-Path (Join-Path $PSScriptRoot '.')).Path
$ApiDir     = Join-Path $RepoRoot 'apps\api'
$TestsDir   = Join-Path $RepoRoot 'tests'
$VenvPy     = Join-Path $RepoRoot 'venv\Scripts\python.exe'
$EnvFile    = Join-Path $RepoRoot '.env'
$EnvExample = Join-Path $RepoRoot '.env.example'
$ReqFile    = Join-Path $RepoRoot 'requirements.txt'

Write-Host ''
Write-Host 'FloatChat/ORCA Backend' -ForegroundColor Cyan
Write-Host ('Repo:  ' + $RepoRoot) -ForegroundColor Gray
Write-Host ('API:   ' + $ApiDir)   -ForegroundColor Gray
Write-Host ''

# --------------------------------------------------------------------------
function Require-Venv {
    if (-not (Test-Path -LiteralPath $VenvPy)) {
        throw "Venv not found at '$VenvPy'. Run '.\setup.ps1 -Install' first."
    }
}

function Set-PyEnv {
    # Must be called from the repo root so `tests` resolves and imports work.
    $env:PYTHONPATH = $ApiDir
    $env:POSTGIS_DATABASE_URL = ''
}

# --------------------------------------------------------------------------
if ($Install -or $All) {
    Write-Host '==> [1/6] Creating virtual environment' -ForegroundColor Green
    if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot 'venv'))) {
        python -m venv (Join-Path $RepoRoot 'venv')
    } else {
        Write-Host '       venv already exists - skipping' -ForegroundColor Gray
    }

    Write-Host '==> [2/6] Upgrading pip + installing requirements' -ForegroundColor Green
    & $VenvPy -m pip install --upgrade pip
    if (-not $?) { throw 'pip upgrade failed' }
    & $VenvPy -m pip install -r $ReqFile
    if (-not $?) { throw 'pip install failed' }
}

if ($Env -or $All) {
    Write-Host '==> [3/6] Bootstrapping .env from .env.example' -ForegroundColor Green
    if (-not (Test-Path -LiteralPath $EnvFile)) {
        Copy-Item -LiteralPath $EnvExample -Destination $EnvFile
        Write-Host "       Created '$EnvFile'. Edit it to set DATABASE_URL + any API keys." -ForegroundColor Yellow
    } else {
        Write-Host '       .env already exists - keeping it (secrets preserved)' -ForegroundColor Gray
    }
}

if ($Migrate -or $All) {
    Write-Host '==> [4/6] Applying DB migrations (alembic upgrade head)' -ForegroundColor Green
    Require-Venv
    Push-Location $ApiDir
    $env:PYTHONPATH = $ApiDir
    & $VenvPy -m alembic upgrade head
    $ok = $?
    Pop-Location
    if (-not $ok) {
        Write-Host '       Migration failed. Ensure DATABASE_URL in .env points to a reachable' -ForegroundColor Yellow
        Write-Host '       PostgreSQL 16+ with PostGIS and pgvector (e.g. Supabase).' -ForegroundColor Yellow
    }
}

if ($Run -or $All) {
    Write-Host '==> [5/6] Starting API (uvicorn app.main:app)' -ForegroundColor Green
    Require-Venv
    Push-Location $ApiDir
    $env:PYTHONPATH = $ApiDir
    Write-Host '       Press Ctrl+C to stop. Health: http://localhost:8000/api/v1/health' -ForegroundColor Gray
    & $VenvPy -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    Pop-Location
}

if ($Test -or $All) {
    Write-Host '==> [6/6] Running full test suite (pytest)' -ForegroundColor Green
    Require-Venv
    Set-PyEnv
    Push-Location $RepoRoot
    & $VenvPy -m pytest $TestsDir -q
    Pop-Location
    if (-not $?) { throw 'pytest failed' }
}

if ($Smoke) {
    Write-Host '==> Smoke-testing a running API on :8000' -ForegroundColor Green
    $base = 'http://localhost:8000'
    foreach ($path in @('api/v1/health','api/v1/ready','api/v1/contract','api/v1/mcp/tools')) {
        try {
            $r = Invoke-WebRequest -Uri "$base/$path" -UseBasicParsing -TimeoutSec 15
            Write-Host ("  [{0}] {1} -> HTTP {2}" -f $r.StatusCode, $path, $r.StatusCode) -ForegroundColor Green
            Write-Host ('        ' + $r.Content.Substring(0, [Math]::Min(160, $r.Content.Length)) + '...') -ForegroundColor Gray
        } catch {
            Write-Host ("  [ERR] {0} -> {1}" -f $path, $_.Exception.Message) -ForegroundColor Red
        }
    }
}

if (-not ($Install -or $Env -or $Migrate -or $Run -or $Test -or $Smoke -or $All)) {
    Write-Host 'Choose an action:' -ForegroundColor Cyan
    Write-Host '  1) Full setup (install + env + migrate + run + test)' -ForegroundColor Gray
    Write-Host '  2) Install only (venv + requirements)' -ForegroundColor Gray
    Write-Host '  3) Run tests (pytest)' -ForegroundColor Gray
    Write-Host '  4) Start the API' -ForegroundColor Gray
    Write-Host '  5) Smoke-test an already-running API' -ForegroundColor Gray
    $choice = Read-Host 'Enter 1-5'
    switch ($choice) {
        '1' { & $PSScriptRoot\setup.ps1 -All }
        '2' { & $PSScriptRoot\setup.ps1 -Install -Env }
        '3' { & $PSScriptRoot\setup.ps1 -Test }
        '4' { & $PSScriptRoot\setup.ps1 -Run }
        '5' { & $PSScriptRoot\setup.ps1 -Smoke }
        default { Write-Host 'Invalid choice' -ForegroundColor Red }
    }
}